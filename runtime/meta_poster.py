#!/usr/bin/env python3
import json, sys, os, logging, time, urllib.parse, random, glob, shutil
from datetime import datetime, timedelta
import requests

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    # Windows dev environment — fcntl unavailable, skip flock-based locking
    HAS_FCNTL = False

import notify

# Edge prod default: /opt/meta-poster-upn  (mirrors goldennummbers' /opt/meta-poster)
# Windows dev: script directory  (so a local config.json next to this file is found)
# Override:    META_POSTER_BASE env var
_DEFAULT_BASE = (os.path.dirname(os.path.abspath(__file__))
                 if os.name == 'nt' else '/opt/meta-poster-upn')
BASE_DIR  = os.environ.get('META_POSTER_BASE', _DEFAULT_BASE)
CONFIG    = os.environ.get('META_POSTER_CONFIG', f'{BASE_DIR}/config.json')
APPROVED  = f'{BASE_DIR}/approved'
ARCHIVE   = f'{BASE_DIR}/archive'
LOG       = f'{BASE_DIR}/logs/poster.log'
BREAKER   = f'{BASE_DIR}/CIRCUIT_BREAKER.flag'
BREAKER_ALERT_SENT = f'{BASE_DIR}/CIRCUIT_BREAKER.alert_sent'
RUN_LOCK  = f'{BASE_DIR}/meta_poster.lock'
LAST_POST_FILE = f'{BASE_DIR}/last_post.json'

BRAND_TAG = '[uaepremiumnumbers]'  # email subject prefix

os.makedirs(f'{BASE_DIR}/logs', exist_ok=True)
os.makedirs(APPROVED, exist_ok=True)
os.makedirs(ARCHIVE, exist_ok=True)

logging.basicConfig(filename=LOG, level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')

GRAPH = 'https://graph.facebook.com/v21.0'
RETRY_DELAY_MIN = 15
MAX_ATTEMPTS = 2  # original + 1 retry, then trip breaker

# Anti-spam guardrail: enforce a minimum gap between any two successful
# posts, regardless of how often this script is invoked. The cron itself
# is */15 min; this is a belt-and-braces floor for catch-up scenarios
# (manual runs after an outage, multiple past-due posts in the queue).
# Override with META_POSTER_MIN_GAP_SEC env var.
MIN_POST_GAP_SECONDS = int(os.environ.get('META_POSTER_MIN_GAP_SEC', 5 * 60))

# Network/DNS errors that justify auto-clearing a tripped breaker once
# connectivity is restored. Anything else (HTTP 4xx, real auth failure)
# stays tripped until human review.
TRANSIENT_BREAKER_MARKERS = (
    'temporary failure in name resolution',
    'nameresolutionerror',
    'failed to resolve',
    'connection refused',
    'no route to host',
    'connection reset',
    'connection aborted',
    'network is unreachable',
    'read timed out',
)

def load(path):
    # utf-8-sig tolerates a UTF-8 BOM that Windows PowerShell's
    # `Out-File -Encoding utf8` prepends. Plain UTF-8 still parses fine.
    with open(path, encoding='utf-8-sig') as f:
        return json.load(f)

def save(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def _send_breaker_email(reason: str, post_id: str = '') -> bool:
    """Send the breaker-trip email and record success in a sidecar so we
    don't re-spam, but DO retry on the next run if delivery failed (e.g.
    DNS down — common when the trip itself was a network blip)."""
    body = (
        f'The uae-premium-numbers Meta poster has been HALTED.\n\n'
        f'Reason: {reason}\n'
        f'Triggered: {datetime.now().isoformat(timespec="seconds")} (PKT)\n'
    )
    if post_id:
        body += f'Post ID: {post_id}\n'
    body += (
        f'\nAll scheduled posts will NOT fire until the breaker is cleared.\n\n'
        f'To investigate, on loom-edge:\n'
        f'  tail -50 {LOG}\n'
        f'  cat {BREAKER}\n'
        f'  ls {APPROVED}/\n\n'
        f'To resume after fixing the underlying issue:\n'
        f'  rm {BREAKER}\n'
    )
    ok, err = notify.send_email(
        f'{BRAND_TAG} CIRCUIT BREAKER TRIPPED — posting halted',
        body,
    )
    if ok:
        with open(BREAKER_ALERT_SENT, 'w') as f:
            f.write(datetime.now().isoformat(timespec='seconds') + '\n')
        logging.info('Breaker alert email delivered')
    else:
        logging.warning(f'Breaker alert email failed (will retry next run): {err}')
    return ok

def trip_breaker(reason: str, post_id: str = ''):
    """Stop all future cron firings until manually cleared."""
    msg = f'{datetime.now().isoformat(timespec="seconds")} {reason}'
    with open(BREAKER, 'w') as f:
        f.write(msg + '\n')
    if os.path.exists(BREAKER_ALERT_SENT):
        os.remove(BREAKER_ALERT_SENT)
    logging.error(f'CIRCUIT BREAKER TRIPPED: {reason}')
    _send_breaker_email(reason, post_id)

def check_breaker() -> bool:
    if not os.path.exists(BREAKER):
        if os.path.exists(BREAKER_ALERT_SENT):
            os.remove(BREAKER_ALERT_SENT)
        return False
    with open(BREAKER) as f:
        reason = f.read().strip()
    logging.warning(f'Circuit breaker active: {reason}. Skipping run.')
    print('Circuit breaker active. Run halted.')
    if not os.path.exists(BREAKER_ALERT_SENT):
        logging.info('Retrying breaker alert email (never delivered)')
        _send_breaker_email(reason)
    return True

def _is_transient_breaker(reason: str) -> bool:
    low = reason.lower()
    return any(m in low for m in TRANSIENT_BREAKER_MARKERS)

def auto_clear_if_transient(cfg) -> None:
    """If the breaker is tripped for a transient reason (DNS/network) AND a
    fresh token preflight passes now, auto-clear the breaker and email a
    recovery notice. After clearing, the normal */15 cron firings will
    catch up the queue at one post per firing, with the cooldown floor
    keeping pacing respectful (no spam after an outage)."""
    if not os.path.exists(BREAKER):
        return
    try:
        with open(BREAKER) as f:
            reason = f.read().strip()
    except Exception:
        return
    if not _is_transient_breaker(reason):
        return
    ok, err = preflight_token(cfg)
    if not ok:
        logging.info(f'Transient breaker but preflight still failing: {err}')
        return
    try:
        os.remove(BREAKER)
    except Exception as e:
        logging.error(f'failed to remove breaker file: {e}')
        return
    if os.path.exists(BREAKER_ALERT_SENT):
        try: os.remove(BREAKER_ALERT_SENT)
        except Exception: pass
    logging.info(f'Auto-cleared transient breaker. Original reason: {reason}')
    pending = len(glob.glob(f'{APPROVED}/*.json'))
    notify.send_email(
        f'{BRAND_TAG} ✅ Auto-recovered after transient network failure',
        f'The circuit breaker was auto-cleared because the original failure was a '
        f'transient network/DNS issue and the FB token now passes preflight.\n\n'
        f'Original reason:\n{reason}\n\n'
        f'Time: {datetime.now().isoformat(timespec="seconds")} (PKT)\n'
        f'Pending in approved/: {pending}\n\n'
        f'Catch-up plan: the cron fires every 15 min and posts the oldest due item, '
        f'with a {MIN_POST_GAP_SECONDS // 60}-min minimum gap between posts as a '
        f'rate-limit safeguard. Past-due posts will roll out one per firing — no spam.\n',
    )

def get_last_post_at() -> tuple[float, str]:
    try:
        with open(LAST_POST_FILE) as f:
            d = json.load(f)
        return float(d.get('ts', 0)), d.get('post_id', '')
    except FileNotFoundError:
        return 0.0, ''
    except Exception as e:
        logging.warning(f'last_post.json unreadable: {e}')
        return 0.0, ''

def set_last_post_at(post_id: str) -> None:
    """Atomic write of the post pacing timestamp."""
    payload = {
        'ts': time.time(),
        'iso': datetime.now().isoformat(timespec='seconds'),
        'post_id': post_id,
    }
    tmp = LAST_POST_FILE + '.tmp'
    try:
        with open(tmp, 'w') as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp, LAST_POST_FILE)
    except Exception as e:
        logging.warning(f'failed to persist last_post.json: {e}')

def check_cooldown() -> bool:
    """Return True if we should skip this run because we posted too recently."""
    last_ts, last_id = get_last_post_at()
    if last_ts <= 0:
        return False
    elapsed = time.time() - last_ts
    if elapsed >= MIN_POST_GAP_SECONDS:
        return False
    remaining = int(MIN_POST_GAP_SECONDS - elapsed)
    msg = (f'Post cooldown active: {remaining}s remaining since last post '
           f'({last_id} at {datetime.fromtimestamp(last_ts).isoformat(timespec="seconds")}). '
           f'Skipping run to respect API rate limits.')
    logging.info(msg)
    print(msg)
    return True

def preflight_token(cfg, attempts: int = 3, backoff: int = 6) -> tuple[bool, str]:
    """Verify the FB page token is still valid before any posting.

    Retries on transient errors (DNS blips, connection resets) so that a
    momentary network hiccup doesn't trip the breaker. A real token problem
    will return a stable HTTP error and break out on the first try.
    """
    last_err = ''
    for i in range(attempts):
        try:
            r = requests.get(
                f'{GRAPH}/{cfg["fb_page_id"]}',
                params={'access_token': cfg['fb_page_token'], 'fields': 'id,name'},
                timeout=15,
            )
            if r.status_code == 200:
                return True, ''
            # 4xx token problem — don't waste retries
            if 400 <= r.status_code < 500:
                return False, f'HTTP {r.status_code}: {r.text[:200]}'
            last_err = f'HTTP {r.status_code}: {r.text[:200]}'
        except requests.exceptions.RequestException as e:
            last_err = str(e)
        if i < attempts - 1:
            logging.warning(f'preflight attempt {i+1}/{attempts} failed: {last_err}; retrying in {backoff}s')
            time.sleep(backoff)
    return False, f'after {attempts} attempts: {last_err}'

def image_url(prompt):
    seed = random.randint(1000, 9999)
    encoded = urllib.parse.quote(prompt[:200])
    url = (f'https://image.pollinations.ai/prompt/{encoded}'
           f'?width=1080&height=1080&nologo=true&model=flux&seed={seed}')
    try:
        r = requests.get(url, timeout=60, stream=True)
        if r.status_code == 200:
            return url
    except Exception as e:
        logging.warning(f'Image failed: {e}')
    return None

def post_facebook(cfg, caption, link, img_url, video_url=None):
    if video_url:
        # FB Video post via file_url. Returns {id: <video_id>}; auto-published.
        r = requests.post(
            f'{GRAPH}/{cfg["fb_page_id"]}/videos',
            data={
                'file_url': video_url,
                'description': caption,
                'access_token': cfg['fb_page_token'],
            },
            timeout=60
        )
        return r
    if img_url:
        r = requests.post(
            f'{GRAPH}/{cfg["fb_page_id"]}/photos',
            data={'url': img_url, 'caption': caption, 'access_token': cfg['fb_page_token']},
            timeout=30
        )
    else:
        params = {'access_token': cfg['fb_page_token'], 'message': caption}
        if link:
            params['link'] = link
        r = requests.post(f'{GRAPH}/{cfg["fb_page_id"]}/feed', data=params, timeout=30)
    return r

def verify_ig_publish_after_error(cfg, expected_caption, max_wait_s=30, lookback=3):
    """Probe IG /media to see if a publish call that returned non-2xx actually
    went live anyway. Meta's rate limiter sometimes returns 403/4/2207051 on
    the same request that successfully publishes — without this verify step,
    a retry would create a duplicate post.

    Match on the first 80 chars of caption (each post's caption_ig contains a
    unique number list, so collisions are effectively impossible).

    Returns the matched media dict {id, permalink, timestamp} or None.
    """
    prefix = (expected_caption or '').strip()[:80]
    if not prefix or not cfg.get('ig_user_id'):
        return None
    url = f'{GRAPH}/{cfg["ig_user_id"]}/media'
    params = {
        'fields': 'id,caption,permalink,timestamp',
        'limit': lookback,
        'access_token': cfg['fb_page_token'],
    }
    deadline = time.time() + max_wait_s
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        try:
            r = requests.get(url, params=params, timeout=15)
            if r.status_code == 200:
                for m in r.json().get('data', []):
                    cap = (m.get('caption') or '').strip()
                    if cap[:80] == prefix:
                        logging.info(
                            f'IG verify-after-error: matched media {m.get("id")} '
                            f'(attempt {attempt})'
                        )
                        return m
        except Exception as e:
            logging.warning(f'IG verify probe error: {e}')
        time.sleep(5)
    return None


def post_instagram(cfg, caption, img_url, video_url=None):
    if video_url:
        # IG REELS: create REELS container -> poll status -> publish.
        # REELS processing can take 30-120s; we poll up to 150s.
        r = requests.post(
            f'{GRAPH}/{cfg["ig_user_id"]}/media',
            data={
                'media_type': 'REELS',
                'video_url': video_url,
                'caption': caption,
                'share_to_feed': 'true',
                'access_token': cfg['fb_page_token'],
            },
            timeout=30
        )
        if r.status_code not in (200, 201):
            logging.error(f'IG REELS container failed: {r.status_code} {r.text[:200]}')
            return r
        container_id = r.json().get('id')
        if not container_id:
            logging.error('IG REELS container: no id returned')
            return r
        for _ in range(30):  # 30 * 5s = 150s
            time.sleep(5)
            status_r = requests.get(
                f'{GRAPH}/{container_id}',
                params={'fields': 'status_code', 'access_token': cfg['fb_page_token']},
                timeout=15
            )
            sc = status_r.json().get('status_code')
            if sc == 'FINISHED':
                break
            if sc == 'ERROR':
                logging.error(f'IG REELS processing ERROR: {status_r.text[:200]}')
                return status_r
        pub = requests.post(
            f'{GRAPH}/{cfg["ig_user_id"]}/media_publish',
            data={'creation_id': container_id, 'access_token': cfg['fb_page_token']},
            timeout=30
        )
        return pub

    if not img_url:
        logging.warning('Instagram skipped — no image URL')
        return None

    r = requests.post(
        f'{GRAPH}/{cfg["ig_user_id"]}/media',
        data={
            'image_url': img_url,
            'caption': caption,
            'access_token': cfg['fb_page_token'],
        },
        timeout=30
    )
    if r.status_code not in (200, 201):
        logging.error(f'IG container failed: {r.status_code} {r.text[:200]}')
        return r

    container_id = r.json().get('id')
    if not container_id:
        logging.error('IG container: no id returned')
        return r

    for _ in range(6):
        time.sleep(5)
        status_r = requests.get(
            f'{GRAPH}/{container_id}',
            params={'fields': 'status_code', 'access_token': cfg['fb_page_token']},
            timeout=15
        )
        if status_r.json().get('status_code') == 'FINISHED':
            break

    pub = requests.post(
        f'{GRAPH}/{cfg["ig_user_id"]}/media_publish',
        data={'creation_id': container_id, 'access_token': cfg['fb_page_token']},
        timeout=30
    )
    return pub

def find_due_post(now_dt):
    """Return the oldest due post.

    Effective due time = retry_at if set, else scheduled_at, else
    legacy scheduled_date + slot ('AM'=09:00, 'PM'=18:00).
    """
    now_iso = now_dt.strftime('%Y-%m-%dT%H:%M:%S')
    candidates = []
    for path in glob.glob(f'{APPROVED}/*.json'):
        try:
            post = load(path)
        except Exception as e:
            logging.error(f'Bad JSON {path}: {e}')
            continue

        retry_at = post.get('retry_at')
        if retry_at:
            effective_at = retry_at
        else:
            sched_at = post.get('scheduled_at')
            if not sched_at:
                sched_date = post.get('scheduled_date')
                if not sched_date:
                    continue
                slot = post.get('slot', 'AM')
                slot_time = '09:00:00' if slot == 'AM' else '18:00:00'
                sched_at = f'{sched_date}T{slot_time}'
            effective_at = sched_at

        if effective_at > now_iso:
            continue
        candidates.append((effective_at, path, post))

    if not candidates:
        return None, None
    candidates.sort(key=lambda x: x[0])
    _, path, post = candidates[0]
    return path, post

def find_next_due():
    """Scan approved/ for the next scheduled post (oldest effective time).
    Called from email_post_success AFTER the just-posted file is moved to
    archive/, so it naturally returns the *next* one."""
    candidates = []
    for path in glob.glob(f'{APPROVED}/*.json'):
        try:
            p = load(path)
        except Exception:
            continue
        when = p.get('retry_at') or p.get('scheduled_at')
        if not when:
            continue
        candidates.append((when, p))
    if not candidates:
        return None, None
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1], candidates[0][0]


def _humanize_delta(target_iso, now_dt):
    try:
        target = datetime.fromisoformat(target_iso)
    except Exception:
        return ''
    secs = int((target - now_dt).total_seconds())
    if secs <= 0:
        return 'overdue'
    if secs < 3600:
        return f'in {secs // 60}m'
    if secs < 86400:
        h, m = divmod(secs, 3600)
        return f'in {h}h {m // 60}m'
    d, h = divmod(secs // 3600, 24)
    return f'in {d}d {h}h'


# Whether this brand has a YouTube poster cron deployed alongside meta_poster.
# Detected at import-time by the presence of youtube_config.json next to this
# script. UPN starts as FB-only, so the file's absent and the marker returns
# empty — the success email omits the YT line entirely. When YT comes online
# (drop a youtube_config.json in BASE_DIR), the marker self-enables.
HAS_YOUTUBE = os.path.exists(f'{BASE_DIR}/youtube_config.json')


def _yt_status_marker(post: dict) -> str:
    """Inline YT status for the per-post email. YT runs on a separate cron
    (5,35 min) so at the meta_poster email moment, YT for this exact post
    has almost always NOT fired yet — show ⏳ with the next-tick window so
    the recipient knows it's queued, not skipped. Returns '' when the brand
    has no YT pipeline (UPN until we deploy youtube_shorts_poster.py)."""
    if not HAS_YOUTUBE:
        return ''
    if post.get('posted_youtube'):
        vid = post.get('youtube_video_id', '')
        return f'YT ✅ youtu.be/{vid}' if vid else 'YT ✅'
    if 'youtube' in (post.get('skip_platforms') or []):
        return 'YT ⊘ skipped'
    return 'YT ⏳ queued (next :05 or :35 cron tick, 5/day cap)'


def email_post_success(post):
    is_grid = post.get('type') == 'grid'
    digits_list = post.get('digits_list') or []
    digits = post.get('digits', '')
    tier = post.get('tier', '')
    sched = post.get('scheduled_at', '?')
    plats = []
    if post.get('posted_fb'): plats.append('FB ✅')
    if post.get('posted_ig'): plats.append('IG ✅')
    yt_marker = _yt_status_marker(post)
    if yt_marker:
        plats.append(yt_marker)

    now_dt = datetime.now()
    nxt, nxt_when = find_next_due()
    if nxt:
        next_line = (f'Next:   {nxt["id"]} at {nxt_when} '
                     f'({_humanize_delta(nxt_when, now_dt)})')
    else:
        next_line = 'Next:   queue empty — daily generator runs at 23:30 PKT'

    if is_grid and digits_list:
        numbers_block = '\n'.join(f'         • {d}' for d in digits_list)
        body = (
            f'Posted {post["id"]}  (grid · {len(digits_list)} numbers)\n\n'
            f'Numbers:\n{numbers_block}\n'
            f'Time:    {now_dt.isoformat(timespec="seconds")} (PKT)\n'
            f'Sched:   {sched}\n'
            f'Out:     {" + ".join(plats)}\n'
            f'Card:    {post.get("image_url","")}\n'
            f'Link:    {post.get("link","")}\n'
            f'\n{next_line}\n'
        )
        subject_tag = f'grid · {len(digits_list)} nums'
        notify.send_email(f'{BRAND_TAG} ✅ {post["id"]} posted ({subject_tag})', body)
    else:
        body = (
            f'Posted {post["id"]}\n\n'
            f'Number: {digits}\n'
            f'Tier:   {tier}\n'
            f'Time:   {now_dt.isoformat(timespec="seconds")} (PKT)\n'
            f'Sched:  {sched}\n'
            f'Out:    {" + ".join(plats)}\n'
            f'Card:   {post.get("image_url","")}\n'
            f'Link:   {post.get("link","")}\n'
            f'\n{next_line}\n'
        )
        notify.send_email(f'{BRAND_TAG} ✅ {post["id"]} posted ({digits})', body)

def email_post_failure(post, fail_summary, retry_at):
    body = (
        f'Post {post["id"]} failed (attempt {post.get("failed_attempts",1)}/{MAX_ATTEMPTS}).\n\n'
        f'Number:   {post.get("digits","")}\n'
        f'Time:     {datetime.now().isoformat(timespec="seconds")} (PKT)\n'
        f'Failures: {fail_summary}\n'
        f'Retry at: {retry_at}\n\n'
        f'If the retry also fails the circuit breaker will trip and you\'ll get a separate alert.\n'
    )
    notify.send_email(
        f'{BRAND_TAG} ⚠️ {post["id"]} failed — auto-retry at {retry_at}',
        body,
    )

def main():
    if not os.path.exists(CONFIG):
        print(f'Missing: {CONFIG}')
        sys.exit(1)

    # Single-instance guard. IG container polling can take 30+ sec, so two
    # */15 cron firings can overlap and double-post the same JSON. fcntl
    # advisory lock — if another run holds it, exit cleanly.
    lock_fd = open(RUN_LOCK, 'w')
    if HAS_FCNTL:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            logging.info('Another meta_poster run is in progress; exiting')
            print('Another run in progress, exiting')
            return
    # Windows dev: no flock available — relies on cron not double-firing.
    # Acceptable since this branch never runs in production (edge is Linux).
    lock_fd.write(f'{os.getpid()} {datetime.now().isoformat(timespec="seconds")}\n')
    lock_fd.flush()

    cfg = load(CONFIG)

    # If the breaker is tripped for a transient (network/DNS) reason and the
    # FB token now passes a fresh preflight, auto-clear it and email
    # "recovered" — outages shouldn't require human babysitting.
    auto_clear_if_transient(cfg)

    if check_breaker():
        return

    ok, err = preflight_token(cfg)
    if not ok:
        trip_breaker(f'FB page token preflight failed: {err}')
        sys.exit(2)

    # Anti-spam floor: even after the breaker is clear and there are past-due
    # posts queued, never publish closer than MIN_POST_GAP_SECONDS apart.
    # Cron is */15 so this only matters for catch-up / manual runs.
    if check_cooldown():
        return

    now_dt = datetime.now()
    today = now_dt.strftime('%Y-%m-%d')

    path, post = find_due_post(now_dt)
    if not post:
        logging.info(f'Nothing due (now={now_dt.isoformat(timespec="seconds")})')
        print(f'Nothing due (now={now_dt.isoformat(timespec="seconds")})')
        return

    when = post.get('retry_at') or post.get('scheduled_at') or \
        f'{post.get("scheduled_date","?")} {post.get("slot","?")}'
    attempt_num = post.get('failed_attempts', 0) + 1
    logging.info(f'Processing {post["id"]} (due {when}, attempt {attempt_num}) from {os.path.basename(path)}')

    if post.get('image_url'):
        img = post['image_url']
    elif post.get('image_prompt'):
        img = image_url(post['image_prompt'])
    else:
        img = None
    platforms = post.get('platforms', ['facebook', 'instagram'])
    failures = []  # human-readable failure descriptions for the email

    video_url = post.get('video_url')

    if 'facebook' in platforms and not post.get('posted_fb'):
        r = post_facebook(cfg, post['caption_fb'], post.get('link'), img, video_url=video_url)
        # requests.Response is falsy on 4xx/5xx (Response.ok is False), so use
        # `is not None` to distinguish "got an error response" from "no response".
        if r is not None and r.status_code in (200, 201):
            post['posted_fb'] = True
            post['posted_fb_date'] = today
            try:
                resp_json = r.json()
                # /photos returns {id, post_id} where post_id = "{page_id}_{story_id}".
                # /feed   returns {id} = "{page_id}_{story_id}". Either is queryable.
                post['fb_post_id'] = resp_json.get('post_id') or resp_json.get('id')
                post['fb_posted_at_iso'] = datetime.now().isoformat(timespec='seconds')
            except Exception as e:
                logging.warning(f'FB OK but post_id parse failed: {e}')
            logging.info(f'FB OK: {post["id"]} fb_post_id={post.get("fb_post_id")}')
            print(f'FB posted: {post["id"]}')
        else:
            code = r.status_code if r is not None else 'no response'
            text = r.text[:200] if r is not None else ''
            logging.error(f'FB FAIL: {post["id"]} {code} {text}')
            print(f'FB failed: {post["id"]}', file=sys.stderr)
            failures.append(f'FB HTTP {code}: {text[:140]}')

    if 'instagram' in platforms and not post.get('posted_ig'):
        if not cfg.get('ig_user_id'):
            # IG account not yet linked to this FB Page (Bilal's 3-step linkage
            # pending). The default daily_generator post template includes
            # 'instagram' in platforms; until ig_user_id is wired in config.json,
            # we skip IG silently and the post is treated as FB-only success.
            # When IG becomes available, set ig_user_id in config and the same
            # platform list works without changes — IG starts posting on the
            # next run.
            logging.info(f'IG skip for {post["id"]} — ig_user_id not configured; FB-only')
        else:
            r = post_instagram(cfg, post['caption_ig'], img, video_url=video_url)
            if r is not None and r.status_code in (200, 201):
                post['posted_ig'] = True
                post['posted_ig_date'] = today
                try:
                    resp_json = r.json()
                    # media_publish returns {id} = ig_media_id, queryable for insights.
                    post['ig_media_id'] = resp_json.get('id')
                    post['ig_posted_at_iso'] = datetime.now().isoformat(timespec='seconds')
                except Exception as e:
                    logging.warning(f'IG OK but media_id parse failed: {e}')
                logging.info(f'IG OK: {post["id"]} ig_media_id={post.get("ig_media_id")}')
                print(f'IG posted: {post["id"]}')
            else:
                code = r.status_code if r is not None else 'no response'
                text = r.text[:200] if r is not None else ''
                # Meta API quirk: 403 / rate-limit responses sometimes fire on
                # a call that actually published. Verify against /media before
                # treating as failure — otherwise the retry creates a duplicate.
                # (See ERROR_LOG 2026-05-28 for the upn-172 incident.)
                verified = verify_ig_publish_after_error(cfg, post.get('caption_ig'))
                if verified:
                    post['posted_ig'] = True
                    post['posted_ig_date'] = today
                    post['ig_media_id'] = verified.get('id')
                    post['ig_permalink'] = verified.get('permalink')
                    post['ig_posted_at_iso'] = verified.get('timestamp')
                    post['_ig_publish_quirk'] = f'HTTP {code} but post went live'
                    logging.info(
                        f'IG OK (verified after HTTP {code}): {post["id"]} '
                        f'ig_media_id={verified.get("id")}'
                    )
                    print(f'IG posted (verified after error): {post["id"]}')
                else:
                    logging.error(f'IG FAIL: {post["id"]} {code} {text}')
                    print(f'IG failed: {post["id"]}', file=sys.stderr)
                    failures.append(f'IG HTTP {code}: {text[:140]}')

    fb_done = ('facebook' not in platforms) or post.get('posted_fb')
    # IG considered "done" if not requested, already posted, OR not configured
    # (latter covers the pre-Bilal-linkage state — see the IG branch above).
    ig_done = (
        ('instagram' not in platforms)
        or post.get('posted_ig')
        or not cfg.get('ig_user_id')
    )
    full_success = fb_done and ig_done

    # Mark "we posted to at least one platform" — start the cooldown clock
    # even on partial success so the next manual / cron firing respects pacing.
    if post.get('posted_fb') or post.get('posted_ig'):
        set_last_post_at(post.get('id', os.path.basename(path)))

    if full_success:
        # clear retry state, archive, notify success
        post.pop('retry_at', None)
        post.pop('failed_attempts', None)
        save(path, post)
        dest = os.path.join(ARCHIVE, os.path.basename(path))
        shutil.move(path, dest)
        logging.info(f'Archived: {os.path.basename(path)}')
        try:
            email_post_success(post)
        except Exception as e:
            logging.warning(f'success-email failed: {e}')
        return

    # something failed
    post['failed_attempts'] = post.get('failed_attempts', 0) + 1
    fail_summary = ' | '.join(failures) if failures else 'unknown'

    if post['failed_attempts'] >= MAX_ATTEMPTS:
        # second strike → halt everything
        post['status'] = 'halted'
        post.pop('retry_at', None)
        save(path, post)
        trip_breaker(
            f'Post {post["id"]} failed {post["failed_attempts"]} times. Last error: {fail_summary}',
            post_id=post['id'],
        )
        sys.exit(2)

    # first strike → schedule retry +15 min
    retry_at = (now_dt + timedelta(minutes=RETRY_DELAY_MIN)).strftime('%Y-%m-%dT%H:%M:%S')
    post['retry_at'] = retry_at
    save(path, post)
    logging.warning(f'{post["id"]} retry scheduled at {retry_at} ({fail_summary})')
    try:
        email_post_failure(post, fail_summary, retry_at)
    except Exception as e:
        logging.warning(f'failure-email failed: {e}')
    sys.exit(1)


if __name__ == '__main__':
    main()
