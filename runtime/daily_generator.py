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
from make_grid_card import render_grid_card, BRAND_VARIANTS, PALETTE_ORDER
from make_story_card import render_story, render_grid_story
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
# Unified conversion WhatsApp — standard across all brands so every lead lands
# in one CRM (Malik, 2026-06-24). Matches postpaidplans + make_card.py.
WA_DISPLAY = "+971 56 902 8087"
LINK_BASE = "https://uaepremiumnumbers.com/choose-number/"

# Plan details for captions (Malik 2026-06-25: surface data/minutes + the right
# keywords on every post + story). The AED 188 entry = Etisalat "Freedom Plan 250"
# (non-stop data + 1,000 local minutes). Source of truth: postpaidplans PLANS[fp250].
# Tier nuance (postpaidplans 2026-06-04 incident): AED 188 is the PLAN price and
# includes a free SILVER number — Gold numbers are priced separately, so never
# let "from AED 188" read as the Gold number's price.
PLAN_DETAILS = "Non-stop data + 1,000 local minutes"
PLAN_LABEL = "Etisalat Postpaid Plans"
ID_PREFIX = "upn"             # post IDs are upn-001, upn-002, ...
BRAND_NAME = "uae-premium-numbers"
PAUSE_AFTER_BATCH_LIMIT = 3   # pause+ping for batches 1–3, auto-roll for 4+
POSTS_PER_DAY = 5             # 2026-06-25: 3→5/day (Malik: aim for 4–5 posts/day across FB+IG)
SINGLE_PER_DAY = 0            # 2026-06-29: PURE pattern-class — NO single-number cards (the proven
GRID_PER_DAY = 5              # losing format); all 5/day are pattern cards, matching GN/PPP + the brief.
GRID_NUMBERS_PER_CARD = 6     # each grid shows 6 numbers
GRID_FROM_PRICE = 188         # AED — matches Probiz, our entry price for Etisalat Post Paid plans
INTERVAL_MIN = 288            # 24h / 5 = 288 min between slots (~4.8h cadence)
RUNWAY_HOURS = 12             # runway guard: skip if queue tail >12h ahead
BATCH_DAYS_AFTER_FIRST = 10   # batch 1 was 1 day; batch 2+ are 10 days
GOLD_PER_DAY = 1              # of 2 singles → 1 Gold + 1 Silver

# ── PATTERN-CLASS grids (2026-06-29) ──
# Organic grids are now single-tier PATTERN cards: 3-6 in-stock numbers that ALL share
# ONE hot ending (e.g. all triple-7), labelled "TRIPLE 7 · MULTIPLE IN STOCK". Mirrors the
# proven GN/PPP format (CRM n=32: triples = 56% of sales; Silver ~78%; 054 = 69%). Sell-out-
# proof (the pool keeps many of the same pattern) and high-intent.
PLATINUM_WEEKDAYS = (0, 3)    # Mon & Thu → ~2 Platinum test cards/week (sheet has ~43 platinum)
TIER_PATTERNS = {
    "silver":   ["777", "666", "999", "888", "555", "222"],
    "gold":     ["888", "999", "777", "666", "8888", "7777"],
    "platinum": ["8888", "7777"],
}
# Tier-matched PLAN price shown on the card (never a Silver price next to Gold numbers — the
# 2026-06-07 DPA mismatch rule). Mirrors goldennummbers render_cards.TIERS.
TIER_PRICE = {"silver": 188, "gold": 500, "platinum": 1000}
TIER_PLAN = {
    "silver":   {"label": "Silver",   "plan": "Freedom Plan 250", "perks": "Non-stop data + 1,000 local minutes"},
    "gold":     {"label": "Gold",     "plan": "Gold Plan 500",    "perks": "Unlimited data + local & int'l calls"},
    "platinum": {"label": "Platinum", "plan": "Platinum Plan",    "perks": "Unlimited everything + 20GB roaming"},
}
# Cross-brand pattern phasing (Malik 2026-06-29: "don't post the same posts across all pages —
# mix the inventory patterns"). Each brand's generator uses the SAME formula with a different
# BRAND_INDEX (gn=0, ppp=1, upn=2, vipd=3): the per-tier start offset = (ordinal day + BRAND_INDEX)
# % len(endings). Since the 4 brands differ only by index, they LEAD each tier with a different hot
# ending every day (rotating daily) → different patterns AND disjoint numbers across pages.
BRAND_INDEX = 2

# Auto-tuner output — written by creative_analytics/tuner.py (env-var-scoped
# to UPN via run_analytics.sh). Missing file → defaults above (cold-start).
TUNING_STATE_FILE = f'{BASE_DIR}/creative_analytics/tuning_state.json'
_HOUR_BUCKET_CENTER_PKT = {"night": 3, "morning": 9, "midday": 15, "evening": 21}


def load_tuning() -> dict:
    blank = {
        "hour": {}, "tier": {}, "format": {}, "brand_variant": {},
        "winning_hour_bucket": "morning",
        "recommendations": [],
    }
    try:
        with open(TUNING_STATE_FILE) as f:
            state = json.load(f)
    except Exception:
        return blank
    t = state.get("tuning", {}) or {}
    h = t.get("hour_weights", {}) or {}
    winning = max(h.items(), key=lambda kv: kv[1], default=("morning", 1.0))[0] if h else "morning"
    return {
        "hour":          h,
        "tier":          t.get("tier_weights", {}) or {},
        "format":        t.get("format_weights", {}) or {},
        "brand_variant": t.get("brand_variant_weights", {}) or {},
        "winning_hour_bucket": winning,
        "recommendations":    state.get("recommendations", []),
    }


def tuned_mix(tuning: dict) -> dict:
    """Apply tuner weights ON TOP of UPN defaults (5 singles / 10 grids).
    All-neutral weights pass through unchanged."""
    fw = tuning.get("format", {}) or {}
    sw = float(fw.get("single-card", 1.0))
    gw = float(fw.get("grid",        1.0))
    if (sw == 1.0 and gw == 1.0) or (sw + gw) <= 0:
        singles, grids = SINGLE_PER_DAY, GRID_PER_DAY
    else:
        biased_s = SINGLE_PER_DAY * sw
        biased_g = GRID_PER_DAY * gw
        tot = biased_s + biased_g
        singles = max(1, min(POSTS_PER_DAY - 1, round(POSTS_PER_DAY * biased_s / tot)))
        grids = POSTS_PER_DAY - singles

    tw = tuning.get("tier", {}) or {}
    g_w = float(tw.get("Gold",   1.0))
    s_w = float(tw.get("Silver", 1.0))
    if (g_w == 1.0 and s_w == 1.0) or (g_w + s_w) <= 0:
        gold = max(0, min(singles, round(singles * GOLD_PER_DAY / max(1, SINGLE_PER_DAY))))
    else:
        biased_g = GOLD_PER_DAY * g_w
        biased_s = (SINGLE_PER_DAY - GOLD_PER_DAY) * s_w
        tot = biased_g + biased_s
        gold = max(0, min(singles, round(singles * biased_g / tot)))

    winning = tuning.get("winning_hour_bucket")
    anchor_hour_pkt = _HOUR_BUCKET_CENTER_PKT.get(winning, 9) if winning else 9
    return {"singles": singles, "grids": grids, "gold_in_singles": gold,
            "anchor_hour_pkt": anchor_hour_pkt}

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

    plan_line = f"📶 {PLAN_LABEL} — {PLAN_DETAILS}, from AED 188/mo"
    if tier == "Gold":
        pair_line = "🎁 Pairs with any Etisalat postpaid plan — this premium Golden Number is priced separately"
    else:
        pair_line = "🎁 Plans from AED 188/mo include a FREE Silver number"

    return (
        f"{opener}\n\n"
        f"{bullets}\n{prefix_line}\n\n"
        f"{plan_line}\n{pair_line}\n\n"
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

IG_TAGS_CORE = ["#UAEPremiumNumbers", "#GoldenNumbers", "#EtisalatPostpaid",
                "#EtisalatPostpaidPlans", "#UAE"]
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
    "#UAEPremiumNumbers #GoldenNumbers #EtisalatPlans #EtisalatPostpaid "
    "#EtisalatPostpaidPlans #PremiumNumber #PostpaidPlan #VIPNumber #UAE "
    "#Dubai #AbuDhabi #Sharjah #Ajman #UAENumbers #MobileNumber "
    "#VanityNumber #Etisalat #etisalatuae"
)


def grid_caption_fb(grid_id: str, numbers_display: list[str], brand_variant: str,
                    tier: str = "silver", pattern_label: str = "") -> str:
    """FB caption for a single-tier PATTERN card. Leads with the pattern + tier-matched plan
    (Silver 188 / Gold 500 / Platinum 1000). Keeps ETISALAT + Post Paid Plans keywords."""
    plan = TIER_PLAN.get(tier, TIER_PLAN["silver"])
    price = TIER_PRICE.get(tier, GRID_FROM_PRICE)
    number_lines = "\n".join(f"• {n}" for n in numbers_display[:8])
    head = f"👑 {plan['label'].upper()} Etisalat VIP Numbers"
    if pattern_label:
        head += f" — {pattern_label}, multiple in stock"
    return (
        f"{head}:\n"
        f"{number_lines}\n\n"
        f"Comes with the {plan['plan']} (AED {price:,}/mo) — {plan['perks']}.\n"
        f"✓ Official ETISALAT Channel Partner · Premium / Golden / VIP Numbers\n"
        f"✓ Free UAE Delivery — Instant Activation\n"
        f"✓ Etisalat postpaid numbers in Dubai, Abu Dhabi, Sharjah & across the UAE\n\n"
        f"Message the number you want — Call or WhatsApp {WA_DISPLAY}\n"
        f"uaepremiumnumbers.com"
    )


def grid_caption_ig(grid_id: str, numbers_display: list[str], brand_variant: str,
                    tier: str = "silver", pattern_label: str = "") -> str:
    """IG caption — single-tier PATTERN card + tag stack."""
    plan = TIER_PLAN.get(tier, TIER_PLAN["silver"])
    price = TIER_PRICE.get(tier, GRID_FROM_PRICE)
    number_lines = "\n".join(f"• {n}" for n in numbers_display[:8])
    head = f"👑 {plan['label'].upper()} Etisalat VIP Numbers"
    if pattern_label:
        head += f" · {pattern_label} · multiple in stock"
    return (
        f"{head}\n"
        f"{plan['plan']} · AED {price:,}/mo · {plan['perks']}\n\n"
        f"{number_lines}\n\n"
        f"✓ Official ETISALAT Channel Partner\n"
        f"✓ Free UAE Delivery · Instant Activation\n\n"
        f"Message the number you want — WhatsApp {WA_DISPLAY}\n\n"
        f"{GRID_IG_HASHTAGS}"
    )


def pat_label(p: str) -> str:
    """'777' -> 'TRIPLE 7'; '8888' -> 'QUAD 8'."""
    return f"{'QUAD' if len(p) >= 4 else 'TRIPLE'} {p[0]}"


def todays_tiers(count: int) -> list[str]:
    """Silver-led grid tiers (real sales ~78% Silver), mirroring GN: 3 Silver + 1 Gold + 1
    rotating (Gold, or a Platinum test on Mon/Thu). Trims/extends to `count`."""
    if count <= 0:
        return []
    base = ["silver", "silver", "silver", "gold", "gold"]
    if datetime.now().weekday() in PLATINUM_WEEKDAYS:
        base[-1] = "platinum"
    if count <= len(base):
        return base[:count]
    return base + ["silver"] * (count - len(base))


def _inv_by_tier(all_rows: list[dict]) -> dict[str, list[str]]:
    """Group AVAILABLE digits by tier (lowercased category) for pattern selection."""
    inv: dict[str, list[str]] = {"silver": [], "gold": [], "platinum": []}
    for r in all_rows:
        c = (r.get("category") or "").lower()
        if c in inv:
            inv[c].append(r["digits"])
    return inv


def _shuffle_054_first(pool: list[str], used: set[str], n: int, rng: random.Random) -> list[str]:
    """054-first, shuffled so combos vary every run; PREFER fresh (not already used this batch)
    but FALL BACK to reuse from the same pattern pool so a deep pool never runs out."""
    g054 = [d for d in pool if d[:3] == "054"]
    goth = [d for d in pool if d[:3] != "054"]
    rng.shuffle(g054)
    rng.shuffle(goth)
    ordered = g054 + goth
    fresh = [d for d in ordered if d not in used]
    return (fresh if len(fresh) >= min(n, 3) else ordered)[:n]


def pick_pattern(tier: str, inv: dict, used: set[str], pat_cursor: dict,
                 rng: random.Random, n: int):
    """Pick (label, [numbers], [endings]) for a tier — mirrors the proven GN engine.
    (1) Prefer a SINGLE deep hot ending (purest pattern-class, e.g. all 777 — works for
    Silver's big pool), rotating which ending each run via pat_cursor. (2) Else a GROUPED
    fallback matching ANY of the tier's hot endings (robust for thin Gold/Platinum)."""
    pats = TIER_PATTERNS[tier]
    cur = pat_cursor.get(tier, 0)
    avail = inv.get(tier, [])
    for off in range(len(pats)):
        p = pats[(cur + off) % len(pats)]
        sub_pool = [d for d in avail if d.endswith(p)]
        if len(sub_pool) >= max(n, 3):
            pat_cursor[tier] = (cur + off + 1) % len(pats)
            return pat_label(p), _shuffle_054_first(sub_pool, used, n, rng), [p]
    grouped = [d for d in avail if any(d.endswith(q) for q in pats)]
    if len(grouped) >= 3:
        pat_cursor[tier] = (cur + 1) % len(pats)
        lbl = "QUAD 8 / 7" if tier == "platinum" else "TRIPLE & QUAD"
        return lbl, _shuffle_054_first(grouped, used, n, rng), list(pats)
    return None, [], []


def _brand_day_cursor() -> dict:
    """Per-tier starting offset into TIER_PATTERNS, phased by brand + day so sister brands
    diverge. Identical formula in every brand's generator (only BRAND_INDEX differs) →
    guaranteed-different lead ending per brand per day, rotating daily."""
    base = date.today().toordinal()
    return {t: (base + BRAND_INDEX) % len(p) for t, p in TIER_PATTERNS.items()}


def pick_grid_numbers(all_rows: list[dict], count: int, numbers_per_card: int,
                      seed_str: str) -> list[dict]:
    """PATTERN-CLASS grids: `count` single-tier cards, Silver-led, each a set of
    `numbers_per_card` in-stock numbers sharing ONE hot ending. Returns a list of
    {numbers, tier, pattern_label}. Cross-brand phasing (see BRAND_INDEX) makes each page
    lead with a different ending. A tier that can't fill falls back to Silver (deep pool)
    so a slot is never silently dropped."""
    rng = random.Random(f"{seed_str}-pattern")
    inv = _inv_by_tier(all_rows)
    pat_cursor = _brand_day_cursor()
    used: set[str] = set()
    out: list[dict] = []
    for want in todays_tiers(count):
        tier = want
        label, nums, _ = pick_pattern(tier, inv, used, pat_cursor, rng, numbers_per_card)
        if (not label or len(nums) < 3) and tier != "silver":
            tier = "silver"
            label, nums, _ = pick_pattern(tier, inv, used, pat_cursor, rng, numbers_per_card)
        if not label or len(nums) < 3:
            continue
        for d in nums:
            used.add(d)
        out.append({"numbers": nums, "tier": tier, "pattern_label": label})
    return out


def pick_brand_variants_for_day(count: int, seed_str: str,
                                tuning: dict | None = None) -> list[str]:
    """Weighted random pick of brand variants for the day's grids.
    Default weights V1:V2:V3 = 2:2:1 → over time ~40%/40%/20%.
    Multiplied by tuner's per-variant weight if `tuning` supplied."""
    rng = random.Random(f"{seed_str}-brand")
    variants = list(BRAND_VARIANTS.keys())
    bv_w = (tuning or {}).get("brand_variant", {})
    weights = [BRAND_VARIANTS[v].get("weight", 1) * float(bv_w.get(v, 1.0))
               for v in variants]
    return rng.choices(variants, weights=weights, k=count)


def build_grid_post_json(post_id: str, digits_list: list[str], brand_variant: str,
                          sched_at_iso: str, image_url: str,
                          story_url: str = "", story_path: str = "",
                          tier: str = "silver", pattern_label: str = "") -> dict:
    """JSON envelope for a pattern-class grid post — carries digits_list + brand_variant +
    tier + pattern_label + type='grid' for downstream identification / re-render."""
    numbers_display = [format_display(d) for d in digits_list]
    return {
        "id": post_id,
        "brand": "uae-premium-numbers",
        "type": "grid",
        "scheduled_at": sched_at_iso,
        "scheduled_date": sched_at_iso[:10],
        "platforms": ["facebook", "instagram"],
        "caption_fb": grid_caption_fb(post_id, numbers_display, brand_variant, tier, pattern_label),
        "caption_ig": grid_caption_ig(post_id, numbers_display, brand_variant, tier, pattern_label),
        "image_url": image_url,
        "story_url": story_url,    # CDN url of the 9:16 story card (IG story)
        "story_path": story_path,  # local file of the story card (FB story upload)
        "link": LINK_BASE,
        "status": "approved",
        "digits_list": digits_list,
        "brand_variant": brand_variant,
        "tier": tier,
        "pattern_label": pattern_label,
        "from_price": TIER_PRICE.get(tier, GRID_FROM_PRICE),
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

    plan_line = f"📶 {PLAN_LABEL} — {PLAN_DETAILS}, from AED 188/mo"
    pair_line = ("🎁 Golden Number priced separately" if tier == "Gold"
                 else "🎁 Free Silver number with plans from AED 188/mo")

    return f"{opener}\n{medal} {hook}\n{plan_line}\n{pair_line}\n\n{cta}\n\n{tags}"


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


def pick_showcase(scored, target_count, seed_str, gold_target: int | None = None):
    """Showcase mix: gold_target Gold + remainder Silver, each tier stratified by
    score quartile. Seeded by date so a given day is reproducible if re-fired.
    Defaults to GOLD_PER_DAY/SINGLE_PER_DAY ratio; tuner-overridable."""
    rng = random.Random(seed_str)

    if gold_target is None:
        gold_target = max(1, round(target_count * GOLD_PER_DAY / SINGLE_PER_DAY))
    gold_target = max(0, min(target_count, gold_target))
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
        # Fresh-deploy defaults for UPN. GN's defaults assumed gn-001..gn-015
        # were already seeded by hand (next_post_id=16, batch_day=1 i.e.
        # "batch 1 already done its 1 day"). UPN deploys from zero, so we
        # start at upn-001 and batch_day=0 — the first run actually generates.
        # batch_size_days=10 (vs GN's 1) — UPN skips the 1-day pilot batch
        # and goes straight to the 10-day cadence, so 10 --force runs queue
        # 150 posts spread across 10 days without tripping the pause-after-1
        # review gate that GN uses for batches 1-3.
        return {
            "batch": 1,
            "batch_day": 0,
            "batch_size_days": 10,
            "next_post_id": 1,
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
    # Re-run safety: if there's nothing staged (idempotent re-render of an
    # already-committed batch), skip commit + push instead of crashing.
    diff = subprocess.run(
        ["git", "-C", SITE_REPO, "diff", "--cached", "--quiet"],
        capture_output=True,
    )
    if diff.returncode == 0:
        logging.info("push_cards: no staged diff — already committed; skipping push")
        return
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


def slot_times_for(fallback_date, anchor_hour_pkt: int = 9):
    """POSTS_PER_DAY slots spaced INTERVAL_MIN apart, anchored to the queue tail.

    `anchor_hour_pkt` (default 9) is the bootstrap hour when the queue is
    empty. Auto-tuner shifts this to the winning hour bucket's centre PKT.
    """
    interval = timedelta(minutes=INTERVAL_MIN)
    latest = _latest_scheduled_at()
    if latest:
        anchor = datetime.strptime(latest, "%Y-%m-%dT%H:%M:%S") + interval
    else:
        # First UPN run: anchor 20:30 PKT on 2026-05-10 per user direction
        # (first slot fires 30 min after deploy). Subsequent runs anchor off
        # the queue tail, so this hardcode only matters for the bootstrap.
        # After bootstrap, tuner-supplied anchor_hour_pkt drives placement.
        anchor = datetime(2026, 5, 10, 20, 30, 0)

    now = datetime.now()
    if anchor < now:
        skip = math.ceil((now - anchor).total_seconds() / (INTERVAL_MIN * 60))
        anchor += interval * skip

    raw = [anchor + interval * i for i in range(POSTS_PER_DAY)]
    # Collision avoidance: keep ≥30-min gap from every goldennummbers slot
    # known on edge (per user direction 2026-05-10).
    return _avoid_gn_collisions(raw, _gn_scheduled_at_set(),
                                min_gap_min=30, interval_min=INTERVAL_MIN)


def _gn_scheduled_at_set():
    """Set of datetime objects representing every scheduled_at across GN's
    approved/ + archive/. Used for collision avoidance — UPN slots get
    pushed past any GN slot within 30 min."""
    out: set[datetime] = set()
    for d in GN_DEDUP_PATHS:
        for path in glob.glob(f"{d}/*.json"):
            try:
                with open(path) as f:
                    p = json.load(f)
            except Exception:
                continue
            sa = p.get("scheduled_at")
            if sa:
                try:
                    out.add(datetime.strptime(sa, "%Y-%m-%dT%H:%M:%S"))
                except Exception:
                    continue
    return out


def _avoid_gn_collisions(slots, gn_slots, min_gap_min=30, interval_min=100):
    """Walk slots forward, ensuring each is ≥min_gap_min minutes from any GN
    slot AND ≥interval_min minutes from the previous UPN slot. Cascades."""
    if not gn_slots:
        return slots
    out = []
    prev = None
    for s in slots:
        if prev and (s - prev).total_seconds() < interval_min * 60:
            s = prev + timedelta(minutes=interval_min)
        for _ in range(20):  # safety cap on the push loop
            close = [gs for gs in gn_slots
                     if abs((s - gs).total_seconds()) < min_gap_min * 60]
            if not close:
                break
            s = max(close) + timedelta(minutes=min_gap_min)
            # Re-check interval against prev after a GN-driven push
            if prev and (s - prev).total_seconds() < interval_min * 60:
                s = prev + timedelta(minutes=interval_min)
        out.append(s)
        prev = s
    return out


def build_post_json(post_id, p, sched_at_iso, image_url, link, human,
                    story_url="", story_path=""):
    return {
        "id": post_id,
        "brand": "uae-premium-numbers",
        "scheduled_at": sched_at_iso,
        "scheduled_date": sched_at_iso[:10],
        "platforms": ["facebook", "instagram"],
        "caption_fb": fb_caption(p, human),
        "caption_ig": ig_caption(p, human),
        "image_url": image_url,
        "story_url": story_url,    # CDN url of the 9:16 story card (IG story)
        "story_path": story_path,  # local file of the story card (FB story upload)
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

        # First time we detect completion → set pause flag (for batches ≤
        # PAUSE_AFTER_BATCH_LIMIT) and exit. Email INTENTIONALLY OMITTED —
        # batch-completion is a queue/state change, not an actual post going
        # live, so per email policy (memory/feedback-email-policy.md) we
        # log only. Sheet-exhausted + crash emails are kept (real failures).
        if state["last_completion_email_for_batch"] < state["batch"]:
            logging.info(f"Batch {state['batch']} complete: "
                         f"days={state['batch_day']}/{state['batch_size_days']}, "
                         f"next_post_id={state['next_post_id']}")
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
    # Auto-tuner reshapes anchor hour + singles/grids/Gold mix per engagement.
    tuning = load_tuning()
    mix = tuned_mix(tuning)
    logging.info(
        f"Tuner: anchor={mix['anchor_hour_pkt']:02d}:00 PKT, "
        f"singles={mix['singles']} grids={mix['grids']} "
        f"gold_in_singles={mix['gold_in_singles']} "
        f"(vs defaults {SINGLE_PER_DAY}/{GRID_PER_DAY}/{GOLD_PER_DAY})"
    )
    fallback_date = (datetime.now() + timedelta(days=1)).date()
    slots = slot_times_for(fallback_date, anchor_hour_pkt=mix["anchor_hour_pkt"])
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

    # Step 2.5: pick singles + grids using TUNED counts (defaults 5/10).
    singles = pick_showcase(scored, mix["singles"], target_date.isoformat(),
                            gold_target=mix["gold_in_singles"])
    if len(singles) < mix["singles"]:
        logging.warning(f"Only {len(singles)} unique single candidates available "
                        f"(wanted {mix['singles']}).")

    grid_number_sets = pick_grid_numbers(rows, mix["grids"], GRID_NUMBERS_PER_CARD,
                                          target_date.isoformat())
    grid_brand_variants = pick_brand_variants_for_day(mix["grids"], target_date.isoformat(),
                                                      tuning=tuning)

    total_picked = len(singles) + len(grid_number_sets)
    if total_picked < POSTS_PER_DAY:
        logging.warning(f"Only {total_picked} total picks (wanted {POSTS_PER_DAY}).")

    # Step 3a: render single feed cards + 9:16 story cards
    story_dir_fs = os.path.join(month_dir_fs, "stories")
    os.makedirs(story_dir_fs, exist_ok=True)
    for p in singles:
        write_card(p["digits"], p["category"], month_dir_fs)
        render_story(p["digits"], p["category"],
                     os.path.join(story_dir_fs, f'{p["digits"]}.jpg'))

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
    # Rotate the 5 creative palettes per grid (square + story share ONE palette),
    # continuing across days via state["palette_cursor"] — matches gn/ppp/vipd.
    pcur = state.get("palette_cursor", 0)
    for i, (gspec, brand_variant) in enumerate(zip(grid_number_sets, grid_brand_variants)):
        digits_list = gspec["numbers"]
        g_tier = gspec["tier"]
        g_plabel = gspec["pattern_label"]
        grid_post_id = grid_ids[i]
        grid_filename = f"{grid_post_id}.jpg"
        grid_out_path = os.path.join(grid_dir_fs, grid_filename)
        palette = PALETTE_ORDER[(pcur + i) % len(PALETTE_ORDER)]
        # Pattern label shown on BOTH sizes (square reuses the subheadline slot; the
        # per-cell pill carries the tier). Tier-matched price (never a mismatch).
        sub = f"{TIER_PLAN[g_tier]['label'].upper()} · {g_plabel} · MULTIPLE IN STOCK"
        render_grid_card(
            numbers=digits_list,
            brand_variant=brand_variant,
            from_price=TIER_PRICE[g_tier],
            subheadline=sub,
            tier=g_tier,
            palette=palette,
            out_path=grid_out_path,
        )
        render_grid_story(digits_list,
                          os.path.join(story_dir_fs, grid_filename),
                          brand_variant=brand_variant, from_price=TIER_PRICE[g_tier],
                          subheadline=sub, palette=palette)
        grid_payloads.append((grid_post_id, digits_list, brand_variant, grid_filename,
                              g_tier, g_plabel))
    state["palette_cursor"] = (pcur + len(grid_number_sets)) % len(PALETTE_ORDER)

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
            story_url = f"{CARDS_PUBLIC_BASE}/{month_subdir}/stories/{digits}.jpg"
            story_path = os.path.join(story_dir_fs, f"{digits}.jpg")
            link = f"{LINK_BASE}?n={digits}"
            post = build_post_json(post_id, payload, sched_at, image_url, link, human,
                                   story_url=story_url, story_path=story_path)
            label = payload["display"]
            tier = payload["category"]
        else:
            _, digits_list, brand_variant, grid_filename, g_tier, g_plabel = payload
            image_url = f"{CARDS_PUBLIC_BASE}/{month_subdir}/grids/{grid_filename}"
            story_url = f"{CARDS_PUBLIC_BASE}/{month_subdir}/stories/{grid_filename}"
            story_path = os.path.join(story_dir_fs, grid_filename)
            post = build_grid_post_json(post_id, digits_list, brand_variant, sched_at, image_url,
                                        story_url=story_url, story_path=story_path,
                                        tier=g_tier, pattern_label=g_plabel)
            label = f"{g_tier.capitalize()} {g_plabel} x{len(digits_list)}"
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
        "singles": sum(1 for _, _, _, t in rows_for_email if t != "Grid"),
        "grids": sum(1 for _, _, _, t in rows_for_email if t == "Grid"),
        "first_id": rows_for_email[0][0] if rows_for_email else "",
        "last_id":  rows_for_email[-1][0] if rows_for_email else "",
    })
    save_state(state)

    # Step 6: log only — daily plan / queue summary email INTENTIONALLY OMITTED.
    # Per Malik 2026-05-10: emails fire only when a post actually goes live
    # (meta_poster.email_post_success) or on real failures. Scheduling /
    # batch / queue summaries are noise. See memory/feedback-email-policy.md.
    grid_count = sum(1 for _, _, _, t in rows_for_email if t == "Grid")
    single_count = len(rows_for_email) - grid_count
    print(f"Generated {len(rows_for_email)} posts ({single_count} singles, {grid_count} grids) "
          f"for {target_date.isoformat()}")
    logging.info(f"Generated {single_count}S+{grid_count}G for {target_date.isoformat()} "
                 f"(batch {state['batch']} day {state['batch_day']}) — "
                 f"first slot {slots[0].strftime('%H:%M')}, last slot {slots[-1].strftime('%H:%M')}")


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
