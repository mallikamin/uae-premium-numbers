#!/usr/bin/env python3
"""Render a 1080x1920 vertical STORY card for uaepremiumnumbers.com.

Story counterpart to make_card.py (the 1:1 feed card). Same Etisalat
red/white aesthetic, same unified 8087 WhatsApp, but 9:16 for FB + IG
Stories. Reuses make_card's palette, fonts, QR and WA_DISPLAY so the two
formats stay visually identical and the contact number never drifts.

Usage:
  python make_story_card.py --digits 0561112222 --tier Gold --out story.jpg
"""
from __future__ import annotations
import argparse, os
from PIL import Image, ImageDraw

import make_card as mc  # palette, find_font, text_size, make_qr, format_display, WA_DISPLAY
import make_grid_card as mgc  # PALETTES / PALETTE_ORDER for grid-story palette rotation

W, H = 1080, 1920


def _centered(draw, text, font, y, fill, ls=0):
    """Width-centered draw on the 1080-wide story canvas (mc.W is also 1080)."""
    return mc.draw_centered(draw, text, font, y, fill, letter_spacing=ls)


def _fit_font(draw, text, names, max_size, min_size, ls, max_width):
    """Largest font (max_size..min_size) whose letter-spaced width fits max_width."""
    size = max_size
    while size > min_size:
        font = mc.find_font(names, size)
        total = sum(mc.text_size(draw, ch, font)[0] for ch in text) + ls * (len(text) - 1)
        if total <= max_width:
            return font
        size -= 4
    return mc.find_font(names, min_size)


def render_story(digits: str, tier: str, out_path: str,
                 site: str = "uaepremiumnumbers.com",
                 plan_aed: int = 188) -> str:
    img = Image.new("RGB", (W, H), mc.BG)
    draw = ImageDraw.Draw(img)

    # ─── Top red ribbon with brand ──────────────────────────────────────
    rib_h = 130
    draw.rectangle([0, 0, W, rib_h], fill=mc.RED)
    draw.line([(0, rib_h), (W, rib_h)], fill=mc.RED_DARK, width=2)
    brand_font = mc.find_font(["seguisb.ttf", "arialbd.ttf", "segoeui.ttf"], 40)
    _centered(draw, "UAE  PREMIUM  NUMBERS", brand_font, (rib_h - 40) // 2 - 2, mc.WHITE, ls=8)

    # ─── AVAILABLE NOW ─────────────────────────────────────────────────
    label_font = mc.find_font(["seguisb.ttf", "segoeui.ttf", "arialbd.ttf"], 36)
    _centered(draw, "AVAILABLE  NOW", label_font, 270, mc.RED, ls=8)
    draw.line([(W // 2 - 90, 332), (W // 2 + 90, 332)], fill=mc.RED, width=3)

    # ─── Hero number ───────────────────────────────────────────────────
    display = mc.format_display(digits)
    number_font = _fit_font(draw, display,
                            ["georgiab.ttf", "georgia.ttf", "cambriab.ttf", "arialbd.ttf"],
                            max_size=126, min_size=84, ls=6, max_width=W - 80)
    _centered(draw, display, number_font, 440, mc.INK, ls=6)

    # ─── Tier pill ─────────────────────────────────────────────────────
    tier_text = tier.upper()
    tier_font = mc.find_font(["seguisb.ttf", "arialbd.ttf"], 34)
    tw, th = mc.text_size(draw, tier_text, tier_font)
    pad_x, pad_y = 34, 14
    pw, ph = tw + pad_x * 2, th + pad_y * 2
    px, py = (W - pw) // 2, 640
    draw.rounded_rectangle([px, py, px + pw, py + ph], radius=ph // 2,
                           fill=mc.RED_TINT, outline=mc.RED, width=2)
    draw.text((px + pad_x, py + pad_y - 2), tier_text, font=tier_font, fill=mc.RED)

    # ─── Plan price tag (reuse feed-card component) ────────────────────
    mc.draw_plan_tag(draw, cx=W // 2, cy=850, price_aed=plan_aed)
    pd_font = mc.find_font(["seguisb.ttf", "arialbd.ttf"], 28)
    _centered(draw, "Etisalat Postpaid · Non-stop data + 1,000 mins", pd_font, 945, mc.TEXT_BODY)

    # ─── Booking CTA — big WhatsApp 8087 ───────────────────────────────
    bk_label_font = mc.find_font(["seguisb.ttf", "arialbd.ttf"], 30)
    bk_phone_font = mc.find_font(["georgiab.ttf", "arialbd.ttf"], 58)
    bk_sub_font   = mc.find_font(["segoeui.ttf", "arial.ttf"], 26)
    _centered(draw, "BOOKING OPEN", bk_label_font, 1010, mc.RED)
    _centered(draw, mc.WA_DISPLAY, bk_phone_font, 1058, mc.TEXT_DARK)
    _centered(draw, "Call or WhatsApp", bk_sub_font, 1138, mc.MUTED)

    # ─── QR ────────────────────────────────────────────────────────────
    qr_url = (f"https://{site}/choose-number/"
              f"?n={digits}&utm_source=story&utm_medium=organic&utm_campaign=card")
    qr_size = 280
    qr_img = mc.make_qr(qr_url, box_size=6).resize((qr_size, qr_size), Image.Resampling.NEAREST)
    qr_x, qr_y = (W - qr_size) // 2, 1300
    pad = 12
    draw.rounded_rectangle([qr_x - pad, qr_y - pad, qr_x + qr_size + pad, qr_y + qr_size + pad],
                           radius=12, fill=mc.WHITE, outline=mc.HAIRLINE, width=1)
    img.paste(qr_img, (qr_x, qr_y))
    cap_font = mc.find_font(["segoeui.ttf", "arial.ttf"], 24)
    _centered(draw, "scan to view this number online", cap_font, qr_y + qr_size + 24, mc.MUTED)

    # ─── Bottom red ribbon ─────────────────────────────────────────────
    foot_h = 130
    y0 = H - foot_h
    draw.rectangle([0, y0, W, H], fill=mc.RED)
    draw.line([(0, y0), (W, y0)], fill=mc.RED_DARK, width=2)
    domain_font = mc.find_font(["seguisb.ttf", "arialbd.ttf", "segoeui.ttf"], 30)
    wa_font     = mc.find_font(["seguisb.ttf", "arialbd.ttf", "segoeui.ttf"], 26)
    draw.text((80, y0 + (foot_h - 30) // 2 - 2), site, font=domain_font, fill=mc.WHITE)
    wa_text = f"WhatsApp {mc.WA_DISPLAY}"
    tw2, _ = mc.text_size(draw, wa_text, wa_font)
    draw.text((W - 80 - tw2, y0 + (foot_h - 26) // 2 - 1), wa_text, font=wa_font, fill=mc.WHITE)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    ext = os.path.splitext(out_path)[1].lower()
    if ext in (".jpg", ".jpeg"):
        img.save(out_path, "JPEG", quality=92, optimize=True, progressive=True)
    elif ext == ".webp":
        img.save(out_path, "WEBP", quality=92, method=6)
    else:
        img.save(out_path, "PNG", optimize=True)
    return out_path


def render_grid_story(numbers: list[str], out_path: str,
                      brand_variant: str = "uaepremiumnumbers",
                      from_price: int = 188,
                      palette: str | None = None,
                      site: str = "uaepremiumnumbers.com",
                      subheadline: str | None = None) -> str:
    """Vertical 1080x1920 STORY for a multi-number grid post — the story
    counterpart to make_grid_card's 1:1 feed card. Numbers stacked in cells.

    Palette-aware so a grid post's square + story share ONE palette (matches
    the gn/ppp/vipd grids, which rotate palettes in both sizes). Colours come
    from make_grid_card.PALETTES; the single-card render_story stays red/white.
    ON_ACCENT is the dark text that sits on the bright accent ribbons/stripes.
    """
    pal = mgc.PALETTES.get(palette or "midnight-gold", mgc.PALETTES["midnight-gold"])
    BG, RED, RED_DARK = pal["BG"], pal["RED"], pal["RED_DARK"]
    CELL, HAIR, INK = pal["CELL_PANEL"], pal["HAIRLINE"], pal["INK"]
    TEXT_BODY, TEXT_DARK, ON_ACCENT = pal["TEXT_BODY"], pal["TEXT_DARK"], pal["ON_ACCENT"]

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Top ribbon
    rib_h = 130
    draw.rectangle([0, 0, W, rib_h], fill=RED)
    draw.line([(0, rib_h), (W, rib_h)], fill=RED_DARK, width=2)
    brand_font = mc.find_font(["seguisb.ttf", "arialbd.ttf", "segoeui.ttf"], 40)
    _centered(draw, "UAE  PREMIUM  NUMBERS", brand_font, (rib_h - 40) // 2 - 2, ON_ACCENT, ls=8)

    # Header
    hf = mc.find_font(["georgiab.ttf", "arialbd.ttf"], 48)
    _centered(draw, "Premium ETISALAT Numbers", hf, 205, RED)
    sf = mc.find_font(["seguisb.ttf", "arialbd.ttf"], 30)
    _centered(draw, subheadline or "Available Now · Postpaid Plans", sf, 280, TEXT_BODY)

    # Authority badge (green = trust — constant across palettes, white text)
    badge = "OFFICIAL ETISALAT CHANNEL PARTNER"
    bgf = mc.find_font(["seguisb.ttf", "arialbd.ttf"], 24)
    bw, bh = mc.text_size(draw, badge, bgf)
    bx, by = (W - (bw + 60)) // 2, 340
    draw.rounded_rectangle([bx, by, bx + bw + 60, by + bh + 26], radius=(bh + 26) // 2,
                           fill=(40, 160, 90))
    draw.text((bx + 30, by + 13 - 2), badge, font=bgf, fill=mc.WHITE)

    # Number cells (stacked)
    nums = numbers[:6]
    top, cell_h, gap = 440, 150, 16
    cw, cx0 = W - 160, 80
    for i, d in enumerate(nums):
        cy = top + i * (cell_h + gap)
        draw.rounded_rectangle([cx0, cy, cx0 + cw, cy + cell_h], radius=16,
                               fill=CELL, outline=HAIR, width=1)
        draw.rounded_rectangle([cx0, cy, cx0 + 16, cy + cell_h], radius=6, fill=RED)
        disp = mc.format_display(d)
        nf = _fit_font(draw, disp, ["georgiab.ttf", "arialbd.ttf"], 66, 40, 4, cw - 90)
        tw, th = mc.text_size(draw, disp, nf)
        draw.text((cx0 + (cw - tw) // 2, cy + (cell_h - th) // 2 - 8), disp, font=nf, fill=INK)

    after = top + len(nums) * (cell_h + gap) + 12
    pf = mc.find_font(["georgiab.ttf", "arialbd.ttf"], 42)
    _centered(draw, f"Starting from {from_price} AED", pf, after, RED)
    pdf = mc.find_font(["seguisb.ttf", "arialbd.ttf"], 27)
    _centered(draw, "Etisalat Postpaid · Non-stop data + 1,000 mins", pdf, after + 54, TEXT_BODY)
    cf = mc.find_font(["georgiab.ttf", "arialbd.ttf"], 50)
    _centered(draw, f"WhatsApp {mc.WA_DISPLAY}", cf, after + 108, TEXT_DARK)

    # Bottom ribbon
    foot_h = 130
    y0 = H - foot_h
    draw.rectangle([0, y0, W, H], fill=RED)
    draw.line([(0, y0), (W, y0)], fill=RED_DARK, width=2)
    domain_font = mc.find_font(["seguisb.ttf", "arialbd.ttf", "segoeui.ttf"], 30)
    wa_font = mc.find_font(["seguisb.ttf", "arialbd.ttf", "segoeui.ttf"], 26)
    draw.text((80, y0 + (foot_h - 30) // 2 - 2), site, font=domain_font, fill=ON_ACCENT)
    wa_text = f"WhatsApp {mc.WA_DISPLAY}"
    tw2, _ = mc.text_size(draw, wa_text, wa_font)
    draw.text((W - 80 - tw2, y0 + (foot_h - 26) // 2 - 1), wa_text, font=wa_font, fill=ON_ACCENT)

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
    p.add_argument("--digits", help="single-number story")
    p.add_argument("--numbers", help="comma-separated digits → grid story")
    p.add_argument("--tier", default="Gold")
    p.add_argument("--out", required=True)
    p.add_argument("--plan-aed", type=int, default=188, dest="plan_aed")
    p.add_argument("--palette", default=None, choices=mgc.PALETTE_ORDER)
    args = p.parse_args()
    if args.numbers:
        nums = [n.strip() for n in args.numbers.split(",") if n.strip()]
        print(render_grid_story(nums, args.out, from_price=args.plan_aed, palette=args.palette))
    else:
        print(render_story(args.digits, args.tier, args.out, plan_aed=args.plan_aed))


if __name__ == "__main__":
    main()
