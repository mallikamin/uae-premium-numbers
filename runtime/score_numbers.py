#!/usr/bin/env python3
"""Fetch live numbers from the goldennummbers.com Google Sheet and score them.

Outputs top-N scored numbers to stdout (JSON) or saves to a file.

Scoring favors patterns that resonate with UAE buyers:
- Repeats / quadruples / triples in the last 4-6 digits
- Sequential ascending or descending
- Palindromes
- Lucky digits (7, 8, 786 anywhere)
- Round endings (000, 1000, 5000)
- Prefix prestige (050 > 052 > 056 > 055 > 058)
- Mild penalty on 4 in the last block (Asian-influenced market)
"""
from __future__ import annotations
import argparse, csv, io, json, os, sys, urllib.request
from pathlib import Path

# ───── Source-sheet config ──────────────────────────────────────────────
# Default (hardcoded) inventory sheets. The real source of truth at runtime
# is `sheets.json` next to this file (or path in env var SHEETS_CONFIG):
#
#   {"sheets": ["id1", "id2", ...], "gid": "0"}
#
# If sheets.json is present, it OVERRIDES the hardcoded SHEETS below.
# To swap inventory sources without a code change or sync.sh, just edit
# sheets.json on loom-edge — the next cron run picks it up automatically.
_DEFAULT_SHEETS = [
    # 2026-06-17: consolidated master sheet (single source). Superseded the dead
    # 1qAw… (now 404) + the empty 1Lmfsc… secondary. Real source of truth at
    # runtime is sheets.json next to this file; this is the last-resort fallback.
    "1YVzDy7ZE5yQ8e46yiPciPYYMyIk2Dog6pUH8GRsABPA",
]
_DEFAULT_GID = "0"


def _load_sheet_config() -> tuple[list[str], str]:
    """Read sheets.json if present; otherwise return hardcoded defaults.
    Resolution order:
      1. env var SHEETS_CONFIG  (absolute path)
      2. ./sheets.json next to this script
      3. hardcoded _DEFAULT_SHEETS
    """
    candidates = []
    env_path = os.environ.get("SHEETS_CONFIG")
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(Path(__file__).resolve().parent / "sheets.json")
    for p in candidates:
        try:
            if p.exists():
                cfg = json.loads(p.read_text())
                sheets = cfg.get("sheets") or []
                gid = str(cfg.get("gid", _DEFAULT_GID))
                if sheets and all(isinstance(s, str) for s in sheets):
                    return sheets, gid
        except Exception:
            continue
    return list(_DEFAULT_SHEETS), _DEFAULT_GID


SHEETS, GID = _load_sheet_config()
SHEET_ID = SHEETS[0]
SHEET_ID = SHEETS[0]
CSV_URL = (
    f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
    f"/gviz/tq?tqx=out:csv&headers=1&gid={GID}"
)

PREFIX_BONUS = {"050": 25, "052": 18, "056": 15, "055": 12, "058": 10}


def _sheet_url(sheet_id: str) -> str:
    return (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}"
        f"/gviz/tq?tqx=out:csv&headers=1&gid={GID}"
    )


def fetch_csv(url: str = CSV_URL) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def fetch_all_rows() -> list[dict]:
    """Union of Available rows across every sheet in SHEETS, deduped by digits.
    First-occurrence wins on conflict so the ordering of SHEETS is meaningful."""
    seen: dict[str, dict] = {}
    for sid in SHEETS:
        text = fetch_csv(_sheet_url(sid))
        for r in parse_csv(text):
            if r["digits"] not in seen:
                seen[r["digits"]] = r
    return list(seen.values())


def is_palindrome(s: str) -> bool:
    return len(s) >= 4 and s == s[::-1]


def max_run_same(s: str) -> int:
    best, cur = 1, 1
    for i in range(1, len(s)):
        if s[i] == s[i - 1]:
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
    return best


def has_sequence(s: str, length: int = 4) -> bool:
    if len(s) < length:
        return False
    asc = "0123456789"
    desc = asc[::-1]
    for seq in (asc, desc):
        for i in range(len(s) - length + 1):
            chunk = s[i : i + length]
            if chunk in seq:
                return True
    return False


def repeated_block(s: str) -> bool:
    """e.g. 1212, 123123, 4545."""
    n = len(s)
    for size in (2, 3, 4):
        if n >= size * 2:
            for i in range(n - size * 2 + 1):
                a = s[i : i + size]
                b = s[i + size : i + size * 2]
                if a == b:
                    return True
    return False


def score_number(digits: str, category: str) -> tuple[int, list[str]]:
    """Return (score, list of reasons)."""
    score = 0
    reasons: list[str] = []

    # Use the 7-digit subscriber portion (after "0XX")
    if not digits or len(digits) < 7:
        return -999, ["malformed"]
    prefix = digits[:3]
    sub = digits[3:]  # 7 digits typically
    last4 = digits[-4:]
    last5 = digits[-5:]
    last6 = digits[-6:]

    # Prefix prestige
    pb = PREFIX_BONUS.get(prefix, 0)
    if pb:
        score += pb
        reasons.append(f"prefix {prefix} +{pb}")

    # Tier baseline
    if category.lower() == "gold":
        score += 30
        reasons.append("Gold tier +30")
    elif category.lower() == "silver":
        score += 10
        reasons.append("Silver tier +10")

    # Quadruple / triple endings
    if last4 == last4[0] * 4:
        score += 80
        reasons.append(f"quadruple ending {last4} +80")
    elif digits.endswith(last4[0] * 5):
        score += 120
        reasons.append("quintuple ending +120")
    elif last4[-3:] == last4[-1] * 3:
        score += 35
        reasons.append(f"triple ending {last4[-3:]} +35")

    # Run of same digit anywhere in subscriber portion
    run = max_run_same(sub)
    if run >= 4:
        score += run * 12
        reasons.append(f"run of {run} same +{run*12}")

    # Palindromes
    if is_palindrome(last5):
        score += 50
        reasons.append("palindrome (last 5) +50")
    elif is_palindrome(last4):
        score += 30
        reasons.append("palindrome (last 4) +30")

    # Sequences
    if has_sequence(sub, 5):
        score += 60
        reasons.append("5-digit sequence +60")
    elif has_sequence(sub, 4):
        score += 35
        reasons.append("4-digit sequence +35")

    # Repeated blocks
    if repeated_block(last6):
        score += 25
        reasons.append("repeated block +25")

    # Lucky 786
    if "786" in digits:
        score += 30
        reasons.append("contains 786 +30")

    # Round endings
    for tail, bonus in (("0000", 70), ("000", 25), ("500", 8), ("100", 5)):
        if digits.endswith(tail):
            score += bonus
            reasons.append(f"ends {tail} +{bonus}")
            break

    # Lucky 7 / 8 density in subscriber portion
    sevens = sub.count("7")
    eights = sub.count("8")
    if sevens >= 3:
        score += sevens * 3
        reasons.append(f"{sevens}x 7s +{sevens*3}")
    if eights >= 3:
        score += eights * 3
        reasons.append(f"{eights}x 8s +{eights*3}")

    # Mild 4 penalty in last 4
    fours = last4.count("4")
    if fours >= 2:
        penalty = fours * 2
        score -= penalty
        reasons.append(f"{fours}x 4s in last4 -{penalty}")

    return score, reasons


def parse_csv(csv_text: str) -> list[dict]:
    out: list[dict] = []
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        status = (row.get("Status") or "").strip().lower()
        if status != "available":
            continue
        category = (row.get("Category") or "").strip()
        if category.lower() not in ("gold", "silver"):
            continue
        with_zero = (row.get("With Zero") or "").strip().replace(" ", "")
        if not with_zero or len(with_zero) < 10:
            continue
        out.append({
            "digits": with_zero,
            "category": "Gold" if category.lower() == "gold" else "Silver",
            "msisdn": (row.get("MSISDN") or "").strip(),
            "code": (row.get("Code") or "").strip(),
        })
    return out


def format_display(digits: str) -> str:
    if len(digits) == 10 and digits.startswith("0"):
        return f"{digits[:3]} {digits[3:6]} {digits[6:]}"
    return digits


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--out", type=str, default="-")
    p.add_argument("--mix", action="store_true",
                   help="Force a mix of Gold and Silver (max 60/40)")
    p.add_argument("--prefix-variety", action="store_true",
                   help="Spread top picks across prefixes (max 3 per prefix)")
    args = p.parse_args()

    csv_text = fetch_csv()
    rows = parse_csv(csv_text)
    print(f"# parsed {len(rows)} available Gold/Silver numbers", file=sys.stderr)

    scored = []
    for r in rows:
        s, why = score_number(r["digits"], r["category"])
        scored.append({
            **r,
            "display": format_display(r["digits"]),
            "score": s,
            "reasons": why,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)

    picks: list[dict] = []
    used_prefix: dict[str, int] = {}
    gold_count = 0
    silver_count = 0
    target = args.top

    for cand in scored:
        if len(picks) >= target:
            break
        prefix = cand["digits"][:3]
        if args.prefix_variety and used_prefix.get(prefix, 0) >= 3:
            continue
        if args.mix:
            # Cap ratios
            if cand["category"] == "Gold" and gold_count >= max(1, target * 6 // 10):
                continue
            if cand["category"] == "Silver" and silver_count >= max(1, target * 4 // 10):
                continue
        picks.append(cand)
        used_prefix[prefix] = used_prefix.get(prefix, 0) + 1
        if cand["category"] == "Gold":
            gold_count += 1
        else:
            silver_count += 1

    payload = json.dumps(picks, indent=2, ensure_ascii=False)
    if args.out == "-":
        print(payload)
    else:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(payload)
        print(f"# wrote {len(picks)} picks to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
