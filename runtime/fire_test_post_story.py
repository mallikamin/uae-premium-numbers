#!/usr/bin/env python3
"""One-shot: render + post ONE UPN number to FB+IG feed AND FB+IG story.

End-to-end validation of the post+story pipeline. Picks the top-scoring
available number not already used/queued, renders the 1:1 feed card and the
9:16 story card, pushes both to the CDN, then posts feed (FB+IG) and story
(FB+IG). Records the number in archive/ so the generator won't repost it.
Safe to run manually.
"""
import json, os, sys, glob, time, subprocess
import requests

BASE = "/opt/meta-poster-upn"
sys.path.insert(0, BASE)
from score_numbers import fetch_all_rows, score_number, format_display
from make_card import render_card, WA_DISPLAY
from make_story_card import render_story
import meta_poster as mp
import story as st

SITE_REPO = f"{BASE}/site_repo"
CARDS_PUBLIC = "https://uaepremiumnumbers.com/cards"
MONTH = time.strftime("%Y-%m")


def load(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def used_digits():
    used = set()
    for d in (f"{BASE}/archive", f"{BASE}/approved"):
        for path in glob.glob(f"{d}/*.json"):
            try:
                p = json.load(open(path))
            except Exception:
                continue
            if p.get("digits"):
                used.add(p["digits"])
            for g in (p.get("digits_list") or []):
                used.add(g)
    return used


def git(*args):
    r = subprocess.run(["git", "-C", SITE_REPO] + list(args),
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def cdn_live(url, tries=24, delay=10):
    for _ in range(tries):
        try:
            if requests.head(url, timeout=15).status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(delay)
    return False


def main():
    cfg = load(f"{BASE}/config.json")
    rows = fetch_all_rows()
    used = used_digits()
    scored = []
    for r in rows:
        if r["digits"] in used:
            continue
        s, _ = score_number(r["digits"], r["category"])
        scored.append((s, r))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        print("no unused numbers in sheet")
        sys.exit(1)
    pick = scored[0][1]
    digits, tier = pick["digits"], pick["category"]
    disp = format_display(digits)
    print(f"PICKED {disp} ({tier})")

    feed_fs = f"{SITE_REPO}/cards/{MONTH}/{digits}.jpg"
    story_fs = f"{SITE_REPO}/cards/{MONTH}/stories/{digits}.jpg"
    render_card(digits, tier, [], feed_fs)
    render_story(digits, tier, story_fs)
    feed_url = f"{CARDS_PUBLIC}/{MONTH}/{digits}.jpg"
    story_url = f"{CARDS_PUBLIC}/{MONTH}/stories/{digits}.jpg"

    git("pull", "--rebase", "--autostash")
    git("add", "cards/")
    git("commit", "-m", f"Test post+story: {digits}")
    git("push")
    print("PUSHED to CDN repo; waiting for cards to go live...")
    if not (cdn_live(feed_url) and cdn_live(story_url)):
        print("CDN cards not live in time")
        sys.exit(2)
    print("CDN LIVE")

    link = f"https://uaepremiumnumbers.com/choose-number/?n={digits}"
    cap_fb = (f"Etisalat Postpaid from AED 188/mo · premium {disp} ({tier} tier).\n\n"
              f"• {tier} tier number\n• {digits[:3]} prefix — premium combinations available\n\n"
              f"To reserve, call or WhatsApp {WA_DISPLAY}.\nOr reserve online: {link}")
    cap_ig = (f"\U0001F4F1 Etisalat 188 plan + {disp}\n\U0001F947 {tier} tier\n\n"
              f"Call or WhatsApp {WA_DISPLAY} · link in bio.\n\n"
              f"#UAEPremiumNumbers #EtisalatPostpaid #UAE #Dubai #PremiumNumber")

    results = {}
    rf = mp.post_facebook(cfg, cap_fb, link, feed_url)
    results["fb_feed"] = (rf.status_code, (rf.json() if rf is not None else None))
    print("FB feed:", results["fb_feed"][0], results["fb_feed"][1])

    ri = mp.post_instagram(cfg, cap_ig, feed_url)
    results["ig_feed"] = (getattr(ri, "status_code", None), (ri.json() if ri is not None else None))
    print("IG feed:", results["ig_feed"])

    ok_fbs, info_fbs = st.post_fb_story(cfg, story_fs)
    results["fb_story"] = (ok_fbs, info_fbs)
    print("FB story:", ok_fbs, info_fbs)

    ok_igs, info_igs = st.post_ig_story(cfg, story_url)
    results["ig_story"] = (ok_igs, info_igs)
    print("IG story:", ok_igs, info_igs)

    # record so the generator won't repost this number
    rec = {"id": f"upn-teststory-{digits}", "brand": "uae-premium-numbers",
           "digits": digits, "tier": tier, "type": "test_post_story",
           "posted_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    with open(f"{BASE}/archive/upn-teststory-{digits}.json", "w") as f:
        json.dump(rec, f, indent=2)

    print("\nSUMMARY:", json.dumps({k: (v[0] if isinstance(v, tuple) else v)
                                    for k, v in results.items()}))


if __name__ == "__main__":
    main()
