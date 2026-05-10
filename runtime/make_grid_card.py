#!/usr/bin/env python3
"""Render a 1080x1080 multi-number grid card for uaepremiumnumbers.com.

Red/white Etisalat-branded grid layout — adapted from
goldennummbers/runtime/make_grid_card.py. Same overall composition (brand
header → subheadline → authority badge → grid → pricing → footer) but with
the Etisalat red ribbon system and white background instead of GN's
midnight-gold gradient.

Each card shows 6-12 premium ETISALAT numbers, "Starting from 188 AED"
pricing block, and a red "Order on WhatsApp or Call" CTA pill. The grid
layout auto-scales (2×3 for 6, 2×4 for 8, 3×4 for 12).

Brand variants (rotated for visual variety in the daily feed):
  - uaepremiumnumbers   → header "uaepremiumnumbers.com"
  - premium_etisalat    → header "Premium ETISALAT Numbers"
  - golden_numbers_uae  → header "Golden Numbers UAE" (matches FB Page name)

Usage (CLI):
  python make_grid_card.py --numbers 0561234567,0567778888,... \
      --brand-variant golden_numbers_uae \
      --out cards/2026-05/grids/grid-001.jpg
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

W = H = 1080

# Palette — matches make_card.py for visual consistency. Etisalat red on white.
BG = (255, 255, 255)             # white card background
RED = (237, 28, 36)              # #ED1C24 Etisalat red
RED_DARK = (177, 20, 26)         # ribbon shadow + darker accents
RED_TINT = (253, 235, 236)       # cell tint, pill fills
TEXT_DARK = (26, 26, 26)
TEXT_BODY = (60, 60, 60)
INK = (15, 15, 20)               # number cell text
WHITE = (255, 255, 255)
MUTED = (140, 140, 145)
HAIRLINE = (228, 228, 232)
CELL_PANEL = (250, 250, 252)     # subtle off-white for number cells
GREEN_BADGE = (40, 160, 90)      # kept — green = certified/trust signal

# Back-compat alias (some older code refs BG_COLOR; the local renderer just uses BG)
BG_COLOR = BG

FONT_DIRS = [
    r"C:\Windows\Fonts",
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/truetype/liberation",
    "/usr/share/fonts/truetype/noto",
    "/usr/share/fonts",
]

FONT_ALIASES = {
    "georgiab.ttf":   ["georgiab.ttf", "DejaVuSerif-Bold.ttf",      "LiberationSerif-Bold.ttf"],
    "georgia.ttf":    ["georgia.ttf",  "DejaVuSerif.ttf",           "LiberationSerif-Regular.ttf"],
    "seguisb.ttf":    ["seguisb.ttf",  "DejaVuSans-Bold.ttf",       "LiberationSans-Bold.ttf"],
    "segoeui.ttf":    ["segoeui.ttf",  "DejaVuSans.ttf",            "LiberationSans-Regular.ttf"],
    "arialbd.ttf":    ["arialbd.ttf",  "DejaVuSans-Bold.ttf",       "LiberationSans-Bold.ttf"],
    "arial.ttf":      ["arial.ttf",    "DejaVuSans.ttf",            "LiberationSans-Regular.ttf"],
    "seguisym.ttf":   ["seguisym.ttf", "DejaVuSans.ttf",            "LiberationSans-Regular.ttf"],
}


def find_font(candidates, size):
    expanded = []
    for name in candidates:
        for alt in FONT_ALIASES.get(name, [name]):
            if alt not in expanded:
                expanded.append(alt)
    for name in expanded:
        for d in FONT_DIRS:
            p = os.path.join(d, name)
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def text_size(draw, txt, font):
    bbox = draw.textbbox((0, 0), txt, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def fmt_number(d):
    if len(d) == 10 and d.startswith("0"):
        return f"{d[:3]} {d[3:6]} {d[6:]}"
    return d


# Brand variant definitions — rotated by daily_generator for feed variety.
# All variants share the red/white aesthetic; only header text + sub differ.
BRAND_VARIANTS = {
    "uaepremiumnumbers":  {"header_top": "uaepremiumnumbers.com",     "header_sub": None,                                          "weight": 2},
    "premium_etisalat":   {"header_top": "Premium ETISALAT Numbers",  "header_sub": None,                                          "weight": 1},
    "golden_numbers_uae": {"header_top": "Golden Numbers UAE",        "header_sub": "Premium Etisalat Numbers + Postpaid Plans",   "weight": 2},
}

# Subheadlines used when header has no second line (V1, V3)
SUBHEADLINES = [
    "Premium ETISALAT Numbers — Post Paid Plans",
    "Hand-Picked Etisalat Numbers · From 188 AED",
    "ETISALAT Premium Numbers · Post Paid Available",
    "Etisalat Numbers — Starting from 188 AED",
    "Post Paid Plans on Premium ETISALAT Numbers",
    "Premium ETISALAT Numbers · Available Now",
    "Hand-Picked ETISALAT Numbers",
]

DEFAULT_SELLING_POINTS = [
    "Premium ETISALAT Numbers",
    "Post Paid Plans Available",
    "Free UAE Delivery",
]


@dataclass
class GridLayout:
    cols: int
    rows: int
    cell_h: int
    top_y: int
    side_pad: int
    cell_gap: int
    number_font_size: int


def grid_layout(num_count: int) -> GridLayout:
    if num_count <= 4:
        return GridLayout(cols=1, rows=4, cell_h=110, top_y=320, side_pad=80, cell_gap=18, number_font_size=58)
    if num_count <= 6:
        return GridLayout(cols=2, rows=3, cell_h=120, top_y=320, side_pad=60, cell_gap=16, number_font_size=44)
    if num_count <= 8:
        return GridLayout(cols=2, rows=4, cell_h=95,  top_y=320, side_pad=60, cell_gap=14, number_font_size=40)
    return GridLayout(cols=3, rows=4, cell_h=85,      top_y=320, side_pad=50, cell_gap=12, number_font_size=32)


def draw_card_background(img: Image.Image):
    """Solid white background — replaces GN's dark vertical gradient.
    Kept as a function so render_grid_card stays structurally aligned with
    the goldennummbers original (easier diffs / cross-brand maintenance)."""
    # No-op: the Image is already created with white BG. Function preserved
    # so render_grid_card can call it identically to GN's flow.
    return


def draw_brand_header(draw, header_top: str, header_sub: str | None):
    """Variant header text. Sits BELOW the top red ribbon (y=88), so all
    Y-coordinates here are offset compared to GN's version which renders
    over a flat dark canvas."""
    if header_sub:
        # Two-line variant (e.g., "Golden Numbers UAE" + sub)
        top_font = find_font(["georgiab.ttf", "arialbd.ttf"], 60)
        tw, _ = text_size(draw, header_top, top_font)
        draw.text(((W - tw) // 2, 110), header_top, font=top_font, fill=RED)
        sub_font = find_font(["seguisb.ttf", "arialbd.ttf"], 26)
        sw, _ = text_size(draw, header_sub, sub_font)
        draw.text(((W - sw) // 2, 188), header_sub, font=sub_font, fill=TEXT_BODY)
        draw.line([(W // 2 - 100, 235), (W // 2 + 100, 235)], fill=RED, width=2)
    else:
        # Single-line variant (e.g., "uaepremiumnumbers.com")
        font_size = 64 if len(header_top) <= 18 else 52
        top_font = find_font(["georgiab.ttf", "arialbd.ttf"], font_size)
        tw, _ = text_size(draw, header_top, top_font)
        draw.text(((W - tw) // 2, 120), header_top, font=top_font, fill=RED)


def draw_subheadline(draw, subheadline: str, y: int = 195):
    """Renders only when the brand variant has no header_sub of its own."""
    sub_font = find_font(["seguisb.ttf", "arialbd.ttf"], 28)
    sw, _ = text_size(draw, subheadline, sub_font)
    draw.text(((W - sw) // 2, y), subheadline, font=sub_font, fill=TEXT_BODY)
    draw.line([(W // 2 - 100, y + 45), (W // 2 + 100, y + 45)], fill=RED, width=2)


def draw_authority_badge(draw, y: int, text: str = "OFFICIAL ETISALAT CHANNEL PARTNER"):
    font = find_font(["arialbd.ttf", "seguisb.ttf"], 22)
    tw, th = text_size(draw, text, font)
    pad_x, pad_y = 20, 10
    bw = tw + pad_x * 2
    bh = th + pad_y * 2
    bx = (W - bw) // 2
    draw.rounded_rectangle([bx, y, bx + bw, y + bh], radius=bh // 2, fill=GREEN_BADGE)
    draw.text((bx + pad_x, y + pad_y - 2), text, font=font, fill=WHITE)


def draw_number_grid(draw, numbers, layout: GridLayout):
    """Number cells — light off-white panels with a red left stripe + red
    corner pill, dark number text. Inverted from GN's dark-cell + gold-text
    treatment; gives the same scannability against a white card background."""
    cols = layout.cols
    rows = layout.rows
    cell_h = layout.cell_h
    avail_w = W - layout.side_pad * 2 - layout.cell_gap * (cols - 1)
    cell_w = avail_w // cols
    num_font = find_font(["georgiab.ttf", "arialbd.ttf"], layout.number_font_size)
    badge_font = find_font(["arialbd.ttf", "seguisb.ttf"], 14)

    for idx, n in enumerate(numbers[:cols * rows]):
        col = idx % cols
        row = idx // cols
        x = layout.side_pad + col * (cell_w + layout.cell_gap)
        y = layout.top_y + row * (cell_h + layout.cell_gap)

        # Cell: subtle off-white fill with hairline border (anchors against pure white bg)
        draw.rounded_rectangle([x, y, x + cell_w, y + cell_h],
                               radius=12, fill=CELL_PANEL,
                               outline=HAIRLINE, width=1)
        # Red accent stripe on left edge (4px wide, full height)
        draw.rectangle([x, y + 1, x + 4, y + cell_h - 1], fill=RED)

        # "GOLD" tier pill — red bg, white text
        pill_text = "GOLD"
        pw, ph = text_size(draw, pill_text, badge_font)
        pill_x = x + 14
        pill_y = y + 10
        draw.rounded_rectangle([pill_x, pill_y, pill_x + pw + 12, pill_y + ph + 6],
                               radius=4, fill=RED)
        draw.text((pill_x + 6, pill_y + 2), pill_text, font=badge_font, fill=WHITE)

        # The number — dark text on light cell
        nfmt = fmt_number(n)
        nw, nh = text_size(draw, nfmt, num_font)
        nx = x + (cell_w - nw) // 2 + 12
        ny = y + (cell_h - nh) // 2 - 2
        draw.text((nx, ny), nfmt, font=num_font, fill=INK)


def draw_from_price(draw, from_price: int, y_center: int):
    """Pricing box — white fill, red outline + red price text. Sits on the
    LEFT of the lower band; selling-point bullets sit to its right."""
    box_x1 = 60
    box_y1 = y_center - 55
    box_x2 = 300
    box_y2 = y_center + 55
    draw.rounded_rectangle([box_x1, box_y1, box_x2, box_y2],
                           radius=14, fill=WHITE, outline=RED, width=2)

    label_font = find_font(["seguisb.ttf", "arialbd.ttf"], 22)
    label = "Starting from"
    lw, _ = text_size(draw, label, label_font)
    draw.text((box_x1 + (box_x2 - box_x1 - lw) // 2, box_y1 + 12),
              label, font=label_font, fill=MUTED)

    price_font = find_font(["georgiab.ttf", "arialbd.ttf"], 44)
    price_text = f"{from_price} AED"
    pw, _ = text_size(draw, price_text, price_font)
    draw.text((box_x1 + (box_x2 - box_x1 - pw) // 2, box_y1 + 38),
              price_text, font=price_font, fill=RED)


def draw_footer(draw, wa_number: str, cta_text: str):
    """Footer band: hairline divider, RED CTA pill (white text), WA number
    in dark text below. Bottom 4px of the card is the red trim strip."""
    draw.line([(80, H - 175), (W - 80, H - 175)], fill=HAIRLINE, width=1)
    cta_font = find_font(["arialbd.ttf", "seguisb.ttf"], 28)
    cw, ch = text_size(draw, cta_text, cta_font)
    pad_x, pad_y = 32, 14
    pw = cw + pad_x * 2
    ph = ch + pad_y * 2
    px = (W - pw) // 2
    py = H - 150
    draw.rounded_rectangle([px, py, px + pw, py + ph],
                           radius=ph // 2, fill=RED)
    draw.text((px + pad_x, py + pad_y - 2),
              cta_text, font=cta_font, fill=WHITE)
    wa_font = find_font(["georgiab.ttf", "arialbd.ttf"], 30)
    ww, _ = text_size(draw, wa_number, wa_font)
    draw.text(((W - ww) // 2, py + ph + 10),
              wa_number, font=wa_font, fill=TEXT_DARK)


def draw_top_ribbon(draw: ImageDraw.ImageDraw, height: int = 88) -> int:
    """Match make_card.py: red top ribbon with the brand wordmark."""
    draw.rectangle([0, 0, W, height], fill=RED)
    brand_font = find_font(["seguisb.ttf", "arialbd.ttf", "segoeui.ttf"], 32)
    bw, _ = text_size(draw, "UAE  PREMIUM  NUMBERS", brand_font)
    draw.text(((W - bw) // 2, (height - 32) // 2),
              "UAE  PREMIUM  NUMBERS", font=brand_font, fill=WHITE)
    draw.line([(0, height), (W, height)], fill=RED_DARK, width=1)
    return height


def render_grid_card(
    numbers: list[str],
    brand_variant: str = "uaepremiumnumbers",
    from_price: int = 188,
    subheadline: str | None = None,
    wa_number: str = "+971 56 699 9377",
    cta_text: str = "Order on WhatsApp or Call",
    authority_badge: str = "OFFICIAL ETISALAT CHANNEL PARTNER",
    selling_points: list[str] | None = None,
    out_path: str = "grid.jpg",
) -> str:
    """Render a 1080x1080 multi-number grid card.

    Args:
        numbers: 6-12 digit strings to display.
        brand_variant: one of the keys in BRAND_VARIANTS.
        from_price: integer AED price for the 'Starting from' block.
        subheadline: optional override; if None, picks deterministically from SUBHEADLINES.
        out_path: file path to save the JPG.

    Returns:
        out_path on success.
    """
    if brand_variant not in BRAND_VARIANTS:
        raise ValueError(f"Unknown brand_variant '{brand_variant}'. Use one of {list(BRAND_VARIANTS)}.")
    bv = BRAND_VARIANTS[brand_variant]
    if subheadline is None:
        # Stable pick: hash the first number for deterministic per-card subheadline
        idx = sum(ord(c) for c in (numbers[0] if numbers else brand_variant)) % len(SUBHEADLINES)
        subheadline = SUBHEADLINES[idx]

    img = Image.new("RGB", (W, H), BG)
    draw_card_background(img)   # no-op on white but kept for parity
    draw = ImageDraw.Draw(img)

    # Top red ribbon (replaces GN's 4px gold strip with a full brand band)
    draw_top_ribbon(draw, height=88)

    draw_brand_header(draw, bv["header_top"], bv["header_sub"])
    if not bv["header_sub"]:
        draw_subheadline(draw, subheadline, y=200)
    draw_authority_badge(draw, y=275, text=authority_badge)

    layout = grid_layout(len(numbers))
    draw_number_grid(draw, numbers, layout)

    grid_bottom = layout.top_y + layout.rows * (layout.cell_h + layout.cell_gap)
    pricing_y = grid_bottom + 60
    draw_from_price(draw, from_price, y_center=pricing_y)

    points = selling_points or DEFAULT_SELLING_POINTS
    point_font = find_font(["seguisym.ttf", "seguisb.ttf", "arialbd.ttf"], 26)
    bullet_test = "✓"
    try:
        tw_test = point_font.getlength(bullet_test)
        bullet = bullet_test if tw_test and tw_test > 0 else "•"
    except Exception:
        bullet = "•"
    sy = pricing_y - 50
    for line in points[:3]:
        # Red bullet, dark body — readable on white
        draw.text((340, sy), bullet, font=point_font, fill=RED)
        bw, _ = text_size(draw, bullet, point_font)
        draw.text((340 + bw + 10, sy), line, font=point_font, fill=TEXT_DARK)
        sy += 40

    draw_footer(draw, wa_number, cta_text=cta_text)
    # Bottom red trim strip — narrow, matches the visual weight of the ribbon top
    draw.rectangle([0, H - 4, W, H], fill=RED)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    ext = os.path.splitext(out_path)[1].lower()
    if ext in (".jpg", ".jpeg"):
        img.save(out_path, "JPEG", quality=92, optimize=True, progressive=True)
    elif ext == ".webp":
        img.save(out_path, "WEBP", quality=92, method=6)
    else:
        img.save(out_path, "PNG", optimize=True)
    return out_path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--numbers", required=True)
    p.add_argument("--brand-variant", default="uaepremiumnumbers", choices=list(BRAND_VARIANTS))
    p.add_argument("--from-price", type=int, default=188)
    p.add_argument("--subheadline", default=None)
    p.add_argument("--wa", default="+971 56 699 9377")
    p.add_argument("--cta", default="Order on WhatsApp or Call")
    p.add_argument("--out", required=True)
    args = p.parse_args()

    nums = [n.strip() for n in args.numbers.split(",") if n.strip()]
    out = render_grid_card(
        numbers=nums,
        brand_variant=args.brand_variant,
        from_price=args.from_price,
        subheadline=args.subheadline,
        wa_number=args.wa,
        cta_text=args.cta,
        out_path=args.out,
    )
    print(out)


if __name__ == "__main__":
    main()
