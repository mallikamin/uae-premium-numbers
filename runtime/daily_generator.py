#!/usr/bin/env python3
"""Daily generator for the uae-premium-numbers Meta poster.

Adapted from goldennummbers/runtime/daily_generator.py (~830 lines). Same
core orchestration; UPN-specific changes:
  - Mix is 5 singles + 10 grids (inverted from GN's 10 + 5).
  - Cards push to uaepremiumnumbers.com/cards/ via the UPN GitHub Pages repo.
  - Brand variants for grids: uaepremiumnumbers / premium_etisalat / golden_numbers_uae.
  - Captions are plan-led (Etisalat plan first, number second).
  - ID prefix is upn-NNN.
  - Dedupe excludes both UPN's own archive AND goldennummbers' archive,
    so the two brands never post the same number on the same week.

Runs 3x/day on loom-edge (cron 02:00 / 10:00 / 18:00 PKT) — runway guard
ensures only ONE actually generates per ~24h cycle.

Each run:
  1. Refuses if CIRCUIT_BREAKER.flag or BATCH_PAUSE.flag is set.
  2. Refuses if the queue tail extends >RUNWAY_HOURS into the future.
  3. Refreshes the Google Sheet of available numbers (same SHEETS list as GN).
  4. Builds the exclusion set: digits already archived/queued for UPN OR GN.
  5. Picks 5 singles from unused + 10 grids from top-200 pool (with replacement).
  6. Renders 5 singles + 10 grids via make_card.py / make_grid_card.py.
     Pushes them to site_repo/cards/YYYY-MM/ as one git commit.
  7. Writes 15 JSON posts into approved/, slot times shuffled so singles +
     grids interleave across the day. INTERVAL_MIN × POSTS_PER_DAY = 24h.
  8. Updates batch_state.json (pause+ping for batches 1–3, auto-roll for 4+).
  9. Emails a daily plan summary.
"""
from __future__ import annotations
import csv, io, json, math, os, re, subprocess, sys, urllib.request, logging, glob, random, hashlib
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import notify
from make_card import render_card
from make_grid_card import render_grid_card, BRAND_VARIANTS
from score_numbers import fetch_all_rows, score_number, format_display

# Edge prod default mirrors meta_poster.py's path scheme.
_DEFAULT_BASE = (os.path.dirname(os.path.abspath(__file__))
                 if os.name == 'nt' else '/opt/meta-poster-upn')
BASE_DIR    = os.environ.get('META_POSTER_BASE', _DEFAULT_BASE)
APPROVED    = f'{BASE_DIR}/approved'
ARCHIVE     = f'{BASE_DIR}/archive'
SITE_REPO   = f'{BASE_DIR}/site_repo'
CARDS_TREE  = f'{SITE_REPO}/cards'
STATE_FILE  = f'{BASE_DIR}/batch_state.json'
BREAKER     = f'{BASE_DIR}/CIRCUIT_BREAKER.flag'
PAUSE_FLAG  = f'{BASE_DIR}/BATCH_PAUSE.flag'
LOG         = f'{BASE_DIR}/logs/generator.log'

# Goldennummbers paths — read-only here, used to build cross-brand dedupe set.
# We never write into GN's directories; we just glob *.json to learn what
# numbers GN has already used, so UPN can skip them.
GN_BASE     = '/opt/meta-poster' if os.name != 'nt' else None
GN_DEDUP_PATHS = (
    [f'{GN_BASE}/archive', f'{GN_BASE}/approved'] if GN_BASE else []
)

CARDS_PUBLIC_BASE = "https://uaepremiumnumbers.com/cards"
WA_DISPLAY = "+971 56 699 9377"
LINK_BASE = "https://uaepremiumnumbers.com/choose-number/"
ID_PREFIX = "upn"             # post IDs are upn-001, upn-002, ...
BRAND_NAME = "uae-premium-numbers"
PAUSE_AFTER_BATCH_LIMIT = 3   # pause+ping for batches 1–3, auto-roll for 4+
POSTS_PER_DAY = 15
SINGLE_PER_DAY = 5            # ↓ from 10 — UPN tilts toward grids
GRID_PER_DAY = 10             # ↑ from 5  — grids are now the bulk
GRID_NUMBERS_PER_CARD = 6     # each grid shows 6 numbers
GRID_FROM_PRICE = 188         # AED — matches Probiz, our entry price for Etisalat Post Paid plans
INTERVAL_MIN = 96             # 24h / POSTS_PER_DAY = 96 min between slots
RUNWAY_HOURS = 12             # runway guard: skip if queue tail >12h ahead
BATCH_DAYS_AFTER_FIRST = 10   # batch 1 was 1 day; batch 2+ are 10 days
GOLD_PER_DAY = 3              # of 5 singles → 60% Gold (3 Gold + 2 Silver)

os.makedirs(f'{BASE_DIR}/logs', exist_ok=True)
logging.basicConfig(filename=LOG, level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')


# --------- caption building ---------
# Captions are deterministic per-number: the same digits always render the
# same caption (idempotent if regenerated). Across a batch the variants
# spread out so the feed doesn't read as templated.

PREFIX_NOTE = {
    "050": "the original Etisalat code, prestige and recognition",
    "052": "premium combinations, modern and sharp",
    "054": "Etisalat batch, broadly available",
    "055": "Etisalat newer batch",
    "056": "premium combinations available",
    "058": "newest Etisalat batch, freshest options",
}

ETISALAT_PREFIXES = {"050", "054", "055", "058"}


def humanize_reasons(reasons):
    out = []
    for r in reasons:
        rl = r.lower()
        if "palindrome" in rl:
            out.append("Palindrome — reads the same forward and back")
        elif "quadruple ending" in rl or "quintuple ending" in rl:
            m = re.search(r"ending (\d+)", r)
            tail = m.group(1) if m else ""
            out.append(f"Quadruple ending {tail}")
        elif "triple ending" in rl:
            m = re.search(r"ending (\d+)", r)
            tail = m.group(1) if m else ""
            out.append(f"Triple {tail} ending")
        elif "sequence" in rl:
            out.append("Sequential digit run — clean visual rhythm")
        elif "repeated block" in rl:
            out.append("Repeated digit block — easy to remember")
        elif "contains 786" in rl:
            out.append("Contains 786 — auspicious sequence")
        elif "x 7s" in rl:
            m = re.search(r"(\d+)x 7s", r)
            n = m.group(1) if m else ""
            out.append(f"{n} sevens for memorability")
        elif "x 8s" in rl:
            m = re.search(r"(\d+)x 8s", r)
            n = m.group(1) if m else ""
            out.append(f"{n} eights — prosperity in numerology")
    return out


def _seed(digits):
    return int(hashlib.md5(digits.encode()).hexdigest()[:8], 16)


def _pick(variants, digits, salt=0):
    return variants[(_seed(digits) + salt) % len(variants)]


# --- FB variation pools ---

FB_OPENERS = [
    "Etisalat Postpaid from AED 188/mo · paired with premium {disp} ({tier_lc} tier).",
    "AED 188 Etisalat plan + premium number {disp} — {tier} tier, available today.",
    "Today's bundle: Etisalat Postpaid + {disp} ({tier_lc} tier).",
    "Pick your Etisalat plan from AED 188 and pair it with {disp} — {tier} tier.",
    "Etisalat 188 plan available · with premium number {disp} ({tier_lc}).",
    "Bundle of the day: {disp} ({tier} tier) on Etisalat Postpaid (from AED 188).",
    "Premium UAE number {disp} ({tier_lc}) · ready on any Etisalat plan from AED 188.",
]

FB_CTAS = [
    "To reserve, call or WhatsApp {wa}.",
    "First to call gets it. WhatsApp {wa}.",
    "Lock it in via WhatsApp {wa}.",
    "Numbers move fast — call or WhatsApp {wa}.",
    "Book over WhatsApp: {wa}.",
    "Reserve by phone or WhatsApp: {wa}.",
]

FB_LINK_LINES = [
    "Or reserve online: {link}",
    "Online: {link}",
    "Site link: {link}",
    "Browse / reserve: {link}",
]


def fb_caption(p, human):
    digits = p["digits"]
    disp = p["display"]
    tier = p["category"]
    tier_lc = tier.lower()
    prefix = digits[:3]
    link = f"{LINK_BASE}?n={digits}"

    opener = _pick(FB_OPENERS, digits, 0).format(disp=disp, tier=tier, tier_lc=tier_lc)
    cta = _pick(FB_CTAS, digits, 1).format(wa=WA_DISPLAY)
    link_line = _pick(FB_LINK_LINES, digits, 2).format(link=link)

    if human:
        # Rotate which 2-3 reasons surface so the same patterns don't always lead.
        offset = _seed(digits) % len(human)
        rotated = human[offset:] + human[:offset]
        bullets = "\n".join(f"• {h}" for h in rotated[:3])
    else:
        bullets = f"• {tier} tier number"

    prefix_line = f"• {prefix} prefix — {PREFIX_NOTE.get(prefix, 'available now')}"

    return (
        f"{opener}\n\n"
        f"{bullets}\n{prefix_line}\n\n"
        f"{cta}\n"
        f"{link_line}"
    )


# --- IG variation pools ---

IG_OPENERS = [
    "📱 Etisalat 188 plan + {disp}",
    "🆕 Etisalat Postpaid · {disp}",
    "Available today: {disp} on Etisalat Postpaid",
    "On the board: {disp} · plans from AED 188",
    "Etisalat Postpaid bundle — {disp}",
    "{disp} 📲 paired with Etisalat 188 plan",
]

IG_HOOKS = [
    "{tier} tier · {feature}",
    "{feature} · {tier} tier",
    "{tier} tier — {feature}",
]

IG_CTAS = [
    "Call or WhatsApp {wa} · link in bio.",
    "DM us, or WhatsApp {wa}.",
    "WhatsApp {wa} to reserve.",
    "Reserve via {wa} or the link in bio.",
    "{wa} on WhatsApp — first to call wins.",
]

IG_TAGS_CORE = ["#UAEPremiumNumbers", "#EtisalatPostpaid", "#UAE"]
IG_TAGS_GEO = [
    "#Dubai", "#AbuDhabi", "#Sharjah", "#Ajman", "#RAK",
    "#UAELife", "#DubaiLife", "#MyDubai", "#AbuDhabiLife",
]
IG_TAGS_TYPE = [
    "#VanityNumber", "#PhoneNumber", "#LuckyNumber", "#PremiumNumber",
    "#SpecialNumber", "#VIPNumber", "#BusinessNumber", "#PostpaidPlan",
    "#UAENumbers", "#MobileNumber", "#EtisalatPlans", "#UAEMobile",
]
IG_TAGS_NETWORK_E = ["#EtisalatNumber", "#Etisalat", "#etisalatuae"]
# NOTE: goldennummbers is an Etisalat-positioned brand. NEVER reintroduce
# Du-branded tags (e.g. #DuNumber, #DuUAE) — see
# memory/project-goldennummbers-etisalat-positioning.md.


def _build_ig_hashtags(digits):
    rng = random.Random(_seed(digits))
    prefix = digits[:3]

    tags = list(IG_TAGS_CORE)
    tags.append(f"#{prefix}")
    tags.extend(rng.sample(IG_TAGS_GEO, k=2))
    tags.extend(rng.sample(IG_TAGS_TYPE, k=3))

    if prefix in ETISALAT_PREFIXES:
        tags.extend(rng.sample(IG_TAGS_NETWORK_E, k=min(2, len(IG_TAGS_NETWORK_E))))
    else:
        # Non-Etisalat prefix — stay silent on carrier; backfill with extra
        # geo/type tags so the tag count stays roughly the same (~10).
        existing = set(tags)
        extras = [t for t in IG_TAGS_TYPE + IG_TAGS_GEO if t not in existing]
        rng.shuffle(extras)
        tags.extend(extras[:2])

    rng.shuffle(tags)
    return " ".join(tags)


# --------- grid caption builders (5 grids/day, mixed in with 10 singles) ---------
# Grid posts are 6-number multi-card showcases. Captions match Probiz's keyword
# stack ("ETISALAT", "Post Paid Plans") so we surface in the same searches.

GRID_FB_OPENERS = [
    "✨ Etisalat Postpaid · Premium UAE Numbers · From AED 188/mo",
    "Etisalat 188 plan paired with hand-picked premium numbers",
    "📲 Premium ETISALAT Numbers + Postpaid Plans — Available Today",
    "Etisalat Postpaid · Choose from these premium numbers",
    "Hand-Picked ETISALAT Numbers · Plans from AED 188",
    "ETISALAT Plans + Premium Numbers · Same-Day Delivery",
]

GRID_FB_CTAS = [
    "Order on WhatsApp or Call: {wa}",
    "Reserve via WhatsApp or Call {wa}",
    "WhatsApp or Call {wa} to book yours",
    "Numbers move fast — Call or WhatsApp {wa}",
    "First to call gets it — WhatsApp {wa}",
]

GRID_IG_OPENERS = [
    "🪙 Etisalat Postpaid · Premium UAE Numbers",
    "📱 Etisalat Plans + Premium ETISALAT Numbers",
    "✨ AED 188/mo · Hand-Picked ETISALAT Numbers",
    "📲 Premium Etisalat Numbers · Postpaid Plans Available",
    "🆕 Etisalat 188 plan + choose from these premium numbers",
]

GRID_IG_HASHTAGS = (
    "#UAEPremiumNumbers #EtisalatPlans #EtisalatPostpaid #PremiumNumber "
    "#PostpaidPlan #VIPNumber #UAE #Dubai #AbuDhabi #Sharjah #Ajman "
    "#UAENumbers #MobileNumber #VanityNumber #Etisalat #etisalatuae"
)


def grid_caption_fb(grid_id: str, numbers_display: list[str], brand_variant: str) -> str:
    """FB caption for grid posts. Includes ETISALAT + Post Paid Plans keywords."""
    rng = random.Random(grid_id)
    opener = rng.choice(GRID_FB_OPENERS)
    cta = rng.choice(GRID_FB_CTAS).format(wa=WA_DISPLAY)
    number_lines = "\n".join(f"• {n}" for n in numbers_display[:8])
    return (
        f"{opener}\n\n"
        f"{number_lines}\n\n"
        f"✓ Post Paid Plans Available\n"
        f"✓ Premium ETISALAT Numbers — Hand-picked\n"
        f"✓ Free UAE Delivery — Instant Activation\n"
        f"✓ Starting from {GRID_FROM_PRICE} AED\n\n"
        f"{cta}\n"
        f"uaepremiumnumbers.com"
    )


def grid_caption_ig(grid_id: str, numbers_display: list[str], brand_variant: str) -> str:
    """IG caption — opener + numbers + key bullets + tag stack."""
    rng = random.Random(grid_id + "-ig")
    opener = rng.choice(GRID_IG_OPENERS)
    cta = rng.choice(GRID_FB_CTAS).format(wa=WA_DISPLAY)
    number_lines = "\n".join(f"• {n}" for n in numbers_display[:8])
    return (
        f"{opener}\n"
        f"Post Paid Plans · Starting from {GRID_FROM_PRICE} AED\n\n"
        f"{number_lines}\n\n"
        f"✓ Premium ETISALAT Numbers\n"
        f"✓ Free UAE Delivery\n\n"
        f"{cta}\n\n"
        f"{GRID_IG_HASHTAGS}"
    )


def pick_grid_numbers(all_rows: list[dict], count: int, numbers_per_card: int,
                      seed_str: str) -> list[list[str]]:
    """Pick `count` grids, each with `numbers_per_card` unique numbers.
    Across grids, numbers can repeat (user instruction 2026-05-08: 'doesn't matter if
    duplicates happen, post as much as you can'). Pool is top-200 scored numbers from
    full sheet — NO exclusion against the `used` set, so previously-posted numbers
    can appear again in grids."""
    rng = random.Random(f"{seed_str}-grid")
    scored = []
    for r in all_rows:
        s, _ = score_number(r["digits"], r["category"])
        scored.append({"digits": r["digits"], "category": r["category"], "score": s})
    scored.sort(key=lambda x: -x["score"])
    pool_size = max(200, count * numbers_per_card * 6)
    pool = scored[:pool_size]
    out = []
    for _ in range(count):
        sample = rng.sample(pool, k=numbers_per_card)
        out.append([x["digits"] for x in sample])
    return out


def pick_brand_variants_for_day(count: int, seed_str: str) -> list[str]:
    """Weighted random pick of brand variants for the day's grids.
    Default weights V1:V2:V3 = 2:2:1 → over time ~40%/40%/20%."""
    rng = random.Random(f"{seed_str}-brand")
    variants = list(BRAND_VARIANTS.keys())
    weights = [BRAND_VARIANTS[v].get("weight", 1) for v in variants]
    return rng.choices(variants, weights=weights, k=count)


def build_grid_post_json(post_id: str, digits_list: list[str], brand_variant: str,
                          sched_at_iso: str, image_url: str) -> dict:
    """JSON envelope for a grid post — mirrors build_post_json structure but
    carries digits_list + brand_variant + type='grid' for downstream identification."""
    numbers_display = [format_display(d) for d in digits_list]
    return {
        "id": post_id,
        "brand": "uae-premium-numbers",
        "type": "grid",
        "scheduled_at": sched_at_iso,
        "scheduled_date": sched_at_iso[:10],
        "platforms": ["facebook", "instagram"],
        "caption_fb": grid_caption_fb(post_id, numbers_display, brand_variant),
        "caption_ig": grid_caption_ig(post_id, numbers_display, brand_variant),
        "image_url": image_url,
        "link": LINK_BASE,
        "status": "approved",
        "digits_list": digits_list,
        "brand_variant": brand_variant,
        "from_price": GRID_FROM_PRICE,
    }


def ig_caption(p, human):
    digits = p["digits"]
    disp = p["display"]
    tier = p["category"]
    medal = "🥇" if tier == "Gold" else "🥈"

    opener = _pick(IG_OPENERS, digits, 10).format(disp=disp)

    if human:
        offset = _seed(digits) % len(human)
        rotated = human[offset:] + human[:offset]
        feature = " · ".join(rotated[:2])
    else:
        feature = f"{tier} tier number"

    hook = _pick(IG_HOOKS, digits, 11).format(tier=tier, feature=feature)
    cta = _pick(IG_CTAS, digits, 12).format(wa=WA_DISPLAY)
    tags = _build_ig_hashtags(digits)

    return f"{opener}\n{medal} {hook}\n\n{cta}\n\n{tags}"


# --------- showcase pick: stratified random within each tier ---------

def _stratified_sample(pool, n_want, rng):
    """Quartile-stratified sample so a batch shows top, upper-mid, mid, and a touch of low."""
    if not pool:
        return []
    if len(pool) <= n_want:
        return list(pool)

    s = sorted(pool, key=lambda x: x["score"], reverse=True)
    n = len(s)
    q1 = max(1, n // 4)
    q2 = max(q1 + 1, n // 2)
    q3 = max(q2 + 1, 3 * n // 4)
    buckets = [s[:q1], s[q1:q2], s[q2:q3], s[q3:]]
    weights = [0.33, 0.33, 0.27, 0.07]  # top / upper / mid / low

    quotas = []
    cum = 0
    for w in weights[:-1]:
        q = round(n_want * w)
        quotas.append(q)
        cum += q
    quotas.append(max(0, n_want - cum))

    picks = []
    seen = set()
    for bucket, q in zip(buckets, quotas):
        avail = [x for x in bucket if x["digits"] not in seen]
        rng.shuffle(avail)
        for x in avail[:q]:
            picks.append(x)
            seen.add(x["digits"])

    if len(picks) < n_want:
        rest = [x for x in s if x["digits"] not in seen]
        rng.shuffle(rest)
        for x in rest:
            if len(picks) >= n_want:
                break
            picks.append(x)
    return picks


def pick_showcase(scored, target_count, seed_str):
    """Showcase mix: GOLD_PER_DAY Gold + remainder Silver, each tier stratified by
    score quartile. Seeded by date so a given day is reproducible if re-fired.
    Ratio is computed against SINGLE_PER_DAY (post-grid split): 6 Gold / 4 Silver = 60% Gold."""
    rng = random.Random(seed_str)

    gold_target = max(1, round(target_count * GOLD_PER_DAY / SINGLE_PER_DAY))
    silver_target = target_count - gold_target

    gold_pool = [x for x in scored if x["category"] == "Gold"]
    silver_pool = [x for x in scored if x["category"] == "Silver"]

    picks = []
    picks += _stratified_sample(gold_pool, gold_target, rng)
    picks += _stratified_sample(silver_pool, silver_target, rng)

    if len(picks) < target_count:
        seen = {p["digits"] for p in picks}
        rest = [x for x in scored if x["digits"] not in seen]
        rng.shuffle(rest)
        for x in rest:
            if len(picks) >= target_count:
                break
            picks.append(x)

    rng.shuffle(picks)  # don't always lead the day with the highest-scoring pick
    return picks[:target_count]


# --------- state ---------

def load_state():
    if not os.path.exists(STATE_FILE):
        return {
            "batch": 1,
            "batch_day": 1,
            "batch_size_days": 1,
            "next_post_id": 16,
            "last_completion_email_for_batch": 0,
            "history": [],
        }
    with open(STATE_FILE) as f:
        return json.load(f)


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# --------- exclusion / dedup ---------

def load_used_digits():
    """Build the dedupe set so UPN never posts a number that has already
    been queued or posted — by UPN OR by goldennummbers.

    Sources scanned:
      • UPN's own archive/   (posted)
      • UPN's own approved/  (currently scheduled)
      • GN's archive/  + approved/  via GN_DEDUP_PATHS  (cross-brand)

    Both fields are honored:
      • 'digits'      — present on single-number posts
      • 'digits_list' — present on grid posts (6+ numbers per card)
    Including digits_list means a number GN used in a grid still gets
    excluded from UPN's single-pick pool. Tighter than GN's own dedupe
    (which only checks 'digits'), but appropriate for UPN since duplicating
    GN's content would defeat the whole separate-brand point.
    """
    used: set[str] = set()
    patterns = [f"{ARCHIVE}/*.json", f"{APPROVED}/*.json"]
    for gn_dir in GN_DEDUP_PATHS:
        patterns.append(f"{gn_dir}/*.json")

    for pattern in patterns:
        for path in glob.glob(pattern):
            try:
                with open(path) as f:
                    p = json.load(f)
            except Exception as e:
                logging.warning(f"Could not parse {path}: {e}")
                continue
            d = p.get("digits") or ""
            if d:
                used.add(d)
            for gd in (p.get("digits_list") or []):
                if gd:
                    used.add(gd)
    return used


# --------- card generation + git push ---------

def write_card(digits, tier, target_dir):
    os.makedirs(target_dir, exist_ok=True)
    path = os.path.join(target_dir, f"{digits}.jpg")
    render_card(digits, tier, [], path)
    return path


def git_run(*args):
    cmd = ["git", "-C", SITE_REPO] + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


def push_cards(month_dir, count):
    git_run("pull", "--rebase", "--autostash")
    git_run("add", "cards/")
    msg = f"Daily card drop ({count} cards) — {date.today().isoformat()}"
    git_run("commit", "-m", msg)
    git_run("push")


# --------- post JSON writing ---------

def _latest_scheduled_at():
    """Latest scheduled_at across approved/ + archive/, or None."""
    latest = None
    for path in glob.glob(f"{APPROVED}/*.json") + glob.glob(f"{ARCHIVE}/*.json"):
        try:
            with open(path) as f:
                p = json.load(f)
            sa = p.get("scheduled_at")
            if sa and (latest is None or sa > latest):
                latest = sa
        except Exception:
            continue
    return latest


def slot_times_for(fallback_date):
    """POSTS_PER_DAY slots spaced INTERVAL_MIN apart, anchored to the queue tail.

    Anchor = (latest scheduled_at across approved/+archive/) + INTERVAL_MIN.
    Fresh deploy with empty queue: anchor = fallback_date 09:00 PKT.
    Anchor in the past (downtime, skipped cron, manual edit): advance by
    whole intervals into the future — skips missed slots rather than
    bursting them on the next run.
    """
    interval = timedelta(minutes=INTERVAL_MIN)
    latest = _latest_scheduled_at()
    if latest:
        anchor = datetime.strptime(latest, "%Y-%m-%dT%H:%M:%S") + interval
    else:
        anchor = datetime(fallback_date.year, fallback_date.month, fallback_date.day, 9, 0, 0)

    now = datetime.now()
    if anchor < now:
        skip = math.ceil((now - anchor).total_seconds() / (INTERVAL_MIN * 60))
        anchor += interval * skip

    return [anchor + interval * i for i in range(POSTS_PER_DAY)]


def build_post_json(post_id, p, sched_at_iso, image_url, link, human):
    return {
        "id": post_id,
        "brand": "uae-premium-numbers",
        "scheduled_at": sched_at_iso,
        "scheduled_date": sched_at_iso[:10],
        "platforms": ["facebook", "instagram"],
        "caption_fb": fb_caption(p, human),
        "caption_ig": ig_caption(p, human),
        "image_url": image_url,
        "link": link,
        "status": "approved",
        "tier": p["category"],
        "digits": p["digits"],
    }


# --------- main ---------

def short_circuit(reason):
    logging.warning(reason)
    print(reason)
    sys.exit(0)


def main(force=False):
    if os.path.exists(BREAKER):
        short_circuit("Circuit breaker active — generator skipping run.")
    if os.path.exists(PAUSE_FLAG):
        short_circuit("Batch pause flag active — generator skipping run.")

    state = load_state()

    # Step 1: handle batch transition (current batch already complete?)
    if state["batch_day"] >= state["batch_size_days"]:
        # Hold transition if any posts are still pending in approved/ — we
        # don't want to declare a batch done while it's still firing.
        pending = glob.glob(f"{APPROVED}/*.json")
        if pending:
            short_circuit(f"Batch {state['batch']} marked done in state but "
                          f"{len(pending)} posts still pending in approved/. Holding.")

        # First time we detect completion → send email, set pause flag (for
        # batches 1–3), and exit. Clearing the pause flag and re-running
        # falls through to the roll-forward block below.
        if state["last_completion_email_for_batch"] < state["batch"]:
            body = (f"Batch {state['batch']} is complete.\n\n"
                    f"Days run: {state['batch_day']}/{state['batch_size_days']}\n"
                    f"Next post ID would be: gn-{state['next_post_id']:03d}\n\n")
            if state["batch"] <= PAUSE_AFTER_BATCH_LIMIT:
                body += ("Per the trust-build policy, the generator is now PAUSED.\n"
                         "Review the posted batch on FB + IG. To resume, on loom-edge run:\n"
                         f"  rm {PAUSE_FLAG}\n")
            else:
                body += "Auto-rolling into the next batch.\n"
            notify.send_email(f"[uaepremiumnumbers] Batch {state['batch']} complete", body)
            state["last_completion_email_for_batch"] = state["batch"]
            save_state(state)

            if state["batch"] <= PAUSE_AFTER_BATCH_LIMIT:
                with open(PAUSE_FLAG, "w") as f:
                    f.write(f"Auto-paused after batch {state['batch']} at "
                            f"{datetime.now().isoformat(timespec='seconds')}\n")
                short_circuit(f"Batch {state['batch']} complete; pause flag set; awaiting review.")

        # Either auto-rolling (batch > 3) or the user just cleared the pause
        # flag and we're resuming. Roll forward into the next batch.
        prev = state["batch"]
        state["batch"] += 1
        state["batch_day"] = 0
        state["batch_size_days"] = BATCH_DAYS_AFTER_FIRST
        save_state(state)
        logging.info(f"Advanced from batch {prev} to batch {state['batch']}.")

    # Step 1.5: idempotent runway guard. Skip if the queue tail is more
    # than RUNWAY_HOURS in the future — there's already enough runway,
    # and a re-run would just duplicate slots. Cron fires daily at 23:30:
    # by then the tail is ~22h ahead immediately post-gen, drops below
    # the 12h threshold ~10h later, so the next nightly cron always runs.
    # --force bypasses this guard (used for one-shot manual top-ups).
    if not force:
        latest_at = _latest_scheduled_at()
        if latest_at:
            latest_dt = datetime.strptime(latest_at, "%Y-%m-%dT%H:%M:%S")
            if latest_dt - datetime.now() > timedelta(hours=RUNWAY_HOURS):
                short_circuit(
                    f"Queue tail at {latest_at} is >{RUNWAY_HOURS}h ahead; "
                    f"skipping run (idempotent guard; pass --force to override)."
                )

    # Step 1.6: compute slot times (anchored to queue tail) and derive
    # target_date from the first slot — this is the calendar day the new
    # batch first fires on, used for card subdir, RNG seed, and email.
    fallback_date = (datetime.now() + timedelta(days=1)).date()
    slots = slot_times_for(fallback_date)
    target_date = slots[0].date()
    month_subdir = target_date.strftime("%Y-%m")
    month_dir_fs = os.path.join(CARDS_TREE, month_subdir)

    # Step 2: build candidate list from sheet
    rows = fetch_all_rows()
    used = load_used_digits()
    logging.info(f"Sheet rows (union): {len(rows)}; used digits: {len(used)}")

    scored = []
    for r in rows:
        if r["digits"] in used:
            continue
        s, why = score_number(r["digits"], r["category"])
        scored.append({
            **r,
            "display": format_display(r["digits"]),
            "score": s,
            "reasons": why,
        })
    scored.sort(key=lambda x: x["score"], reverse=True)

    if not scored:
        notify.send_email(
            "[uaepremiumnumbers] Sheet exhausted — no candidates left",
            "The Google Sheet has no Available Gold/Silver numbers we haven't already posted.\n"
            "Add fresh stock or end the campaign."
        )
        short_circuit("No candidates available; sheet may be exhausted.")

    # Step 2.5: pick singles (10) and grids (5) — singles dedup against `used`,
    # grids draw from full sheet (duplicates with already-posted OK per user instruction)
    singles = pick_showcase(scored, SINGLE_PER_DAY, target_date.isoformat())
    if len(singles) < SINGLE_PER_DAY:
        logging.warning(f"Only {len(singles)} unique single candidates available (wanted {SINGLE_PER_DAY}).")

    grid_number_sets = pick_grid_numbers(rows, GRID_PER_DAY, GRID_NUMBERS_PER_CARD, target_date.isoformat())
    grid_brand_variants = pick_brand_variants_for_day(GRID_PER_DAY, target_date.isoformat())

    total_picked = len(singles) + len(grid_number_sets)
    if total_picked < POSTS_PER_DAY:
        logging.warning(f"Only {total_picked} total picks (wanted {POSTS_PER_DAY}).")

    # Step 3a: render single cards into site_repo/cards/YYYY-MM/
    for p in singles:
        write_card(p["digits"], p["category"], month_dir_fs)

    # Pre-allocate post IDs: singles get [next_post_id .. +SINGLE_PER_DAY),
    # grids get the contiguous block immediately after.
    base_id = state["next_post_id"]
    single_ids = [f"upn-{base_id + i:03d}" for i in range(len(singles))]
    grid_ids   = [f"upn-{base_id + len(singles) + i:03d}" for i in range(len(grid_number_sets))]
    final_next_id = base_id + len(singles) + len(grid_number_sets)

    # Step 3b: render grid cards into site_repo/cards/YYYY-MM/grids/
    grid_dir_fs = os.path.join(month_dir_fs, "grids")
    os.makedirs(grid_dir_fs, exist_ok=True)
    grid_payloads: list[tuple[str, list[str], str, str]] = []
    for i, (digits_list, brand_variant) in enumerate(zip(grid_number_sets, grid_brand_variants)):
        grid_post_id = grid_ids[i]
        grid_filename = f"{grid_post_id}.jpg"
        grid_out_path = os.path.join(grid_dir_fs, grid_filename)
        render_grid_card(
            numbers=digits_list,
            brand_variant=brand_variant,
            from_price=GRID_FROM_PRICE,
            out_path=grid_out_path,
        )
        grid_payloads.append((grid_post_id, digits_list, brand_variant, grid_filename))

    push_cards(month_dir_fs, count=total_picked)
    logging.info(f"Pushed {len(singles)} singles + {len(grid_payloads)} grids to {month_subdir}/")

    # Step 4: build combined list of (id, kind, payload) and shuffle SLOT assignment
    # so grids and singles interleave through the day. IDs are fixed; only slot times move.
    combined: list[tuple[str, str, object]] = []
    for sid, p in zip(single_ids, singles):
        combined.append((sid, "single", p))
    for entry in grid_payloads:
        combined.append((entry[0], "grid", entry))

    slot_rng = random.Random(f"{target_date.isoformat()}-slots")
    slot_indices = list(range(min(POSTS_PER_DAY, len(combined))))
    slot_rng.shuffle(slot_indices)

    rows_for_email = []
    for i, (post_id, kind, payload) in enumerate(combined[:POSTS_PER_DAY]):
        slot_idx = slot_indices[i]
        sched_at = slots[slot_idx].strftime("%Y-%m-%dT%H:%M:%S")

        if kind == "single":
            human = humanize_reasons(payload["reasons"])
            digits = payload["digits"]
            image_url = f"{CARDS_PUBLIC_BASE}/{month_subdir}/{digits}.jpg"
            link = f"{LINK_BASE}?n={digits}"
            post = build_post_json(post_id, payload, sched_at, image_url, link, human)
            label = payload["display"]
            tier = payload["category"]
        else:
            _, digits_list, brand_variant, grid_filename = payload
            image_url = f"{CARDS_PUBLIC_BASE}/{month_subdir}/grids/{grid_filename}"
            post = build_grid_post_json(post_id, digits_list, brand_variant, sched_at, image_url)
            label = f"GRID[{brand_variant}] · {len(digits_list)} numbers"
            tier = "Grid"

        with open(os.path.join(APPROVED, f"{post_id}.json"), "w", encoding="utf-8") as f:
            json.dump(post, f, indent=2, ensure_ascii=False)
        rows_for_email.append((post_id, sched_at, label, tier))

    next_id = final_next_id
    # Sort the email summary by slot time for readability
    rows_for_email.sort(key=lambda r: r[1])

    # Step 5: update state
    state["batch_day"] += 1
    state["next_post_id"] = next_id
    state["history"] = (state.get("history") or [])[-30:]  # keep last 30 days
    state["history"].append({
        "date": target_date.isoformat(),
        "batch": state["batch"],
        "batch_day": state["batch_day"],
        "count": len(rows_for_email),
        "singles": sum(1 for _, _, lbl, _ in rows_for_email if not lbl.startswith("GRID")),
        "grids": sum(1 for _, _, lbl, _ in rows_for_email if lbl.startswith("GRID")),
        "first_id": rows_for_email[0][0] if rows_for_email else "",
        "last_id":  rows_for_email[-1][0] if rows_for_email else "",
    })
    save_state(state)

    # Step 6: email summary (wider columns to accommodate grid labels)
    grid_count = sum(1 for _, _, label, _ in rows_for_email if label.startswith("GRID"))
    single_count = len(rows_for_email) - grid_count
    table_lines = [f"{'ID':<10} {'Time':<19} {'Detail':<40} {'Tier':<6}"]
    for pid, t, disp, tier in rows_for_email:
        table_lines.append(f"{pid:<10} {t:<19} {disp:<40} {tier:<6}")
    body = (
        f"Next batch — first slot {target_date.isoformat()}\n\n"
        f"Batch {state['batch']} — Day {state['batch_day']}/{state['batch_size_days']}\n"
        f"{len(rows_for_email)} posts queued ({single_count} singles + {grid_count} grids, "
        f"FB + IG, every {INTERVAL_MIN} min PKT).\n"
        f"First: {slots[0].strftime('%Y-%m-%d %H:%M')}  ·  "
        f"Last: {slots[-1].strftime('%Y-%m-%d %H:%M')}\n\n"
        + "\n".join(table_lines)
        + f"\n\nCards pushed to {CARDS_PUBLIC_BASE}/{month_subdir}/\n"
        f"Grids in {CARDS_PUBLIC_BASE}/{month_subdir}/grids/\n"
    )
    notify.send_email(
        f"[uaepremiumnumbers] Daily plan — {len(rows_for_email)} posts ({single_count}+{grid_count}G) "
        f"queued for {target_date.isoformat()}",
        body,
    )

    print(f"Generated {len(rows_for_email)} posts ({single_count} singles, {grid_count} grids) "
          f"for {target_date.isoformat()}")
    logging.info(f"Generated {single_count}S+{grid_count}G for {target_date.isoformat()} "
                 f"(batch {state['batch']} day {state['batch_day']})")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true",
                        help="Bypass the runway guard (still respects breaker/pause).")
    args = parser.parse_args()
    try:
        main(force=args.force)
    except Exception as e:
        logging.exception("daily_generator crashed")
        try:
            notify.send_email(
                "[uaepremiumnumbers] 🚨 daily_generator crashed",
                f"Exception: {e}\n\nSee {LOG} on loom-edge for traceback."
            )
        except Exception:
            pass
        raise
