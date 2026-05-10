#!/usr/bin/env python3
"""Render a 1080x1080 number card for uaepremiumnumbers.com.

Number-led layout with Etisalat red ribbons, plan-price tag in the corner,
WhatsApp + QR footer. Adapted from goldennummbers/runtime/make_card.py — same
utilities (find_font, make_qr, format_display, etc.) but a fresh render_card
for the red/white telecom-shop aesthetic and plan-led positioning.

Usage:
  python make_card.py --digits 0562787778 --tier Gold \
                      --out cards/0562787778.jpg

Output format is detected from --out extension (jpg/jpeg/webp/png).
"""
from __future__ import annotations
import argparse, os, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import qrcode

W = H = 1080

# Palette — Etisalat red on white. Mirrors the website theme (#ED1C24)
# established in the 2026-04 brand pivot (RESUME.md row 4).
BG = (255, 255, 255)            # pure white
BG_SOFT = (250, 250, 252)       # near-white, for subtle panels
RED = (237, 28, 36)             # #ED1C24 Etisalat red
RED_DARK = (177, 20, 26)        # #b1141a — for shadows / depth on red ribbons
RED_TINT = (253, 235, 236)      # very light red, for tier-pill fill
TEXT_DARK = (26, 26, 26)        # near-black hero text
TEXT_BODY = (60, 60, 60)        # body copy
MUTED = (140, 140, 145)         # captions, secondary lines
INK = (15, 15, 20)              # darkest, for the hero number itself
WHITE = (255, 255, 255)
HAIRLINE = (228, 228, 232)      # thin separators on white


FONT_DIRS = [
    r"C:\Windows\Fonts",
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/truetype/liberation",
    "/usr/share/fonts",
    "/Library/Fonts",
]

# Cross-platform font equivalents for the Windows-named candidates the rest
# of the file passes in. First match wins.
FONT_ALIASES = {
    "georgiab.ttf":   ["georgiab.ttf", "DejaVuSerif-Bold.ttf",      "LiberationSerif-Bold.ttf"],
    "georgia.ttf":    ["georgia.ttf",  "DejaVuSerif.ttf",           "LiberationSerif-Regular.ttf"],
    "cambriab.ttf":   ["cambriab.ttf", "DejaVuSerif-Bold.ttf",      "LiberationSerif-Bold.ttf"],
    "seguisb.ttf":    ["seguisb.ttf",  "DejaVuSans-Bold.ttf",       "LiberationSans-Bold.ttf"],
    "segoeui.ttf":    ["segoeui.ttf",  "DejaVuSans.ttf",            "LiberationSans-Regular.ttf"],
    "arialbd.ttf":    ["arialbd.ttf",  "DejaVuSans-Bold.ttf",       "LiberationSans-Bold.ttf"],
    "arial.ttf":      ["arial.ttf",    "DejaVuSans.ttf",            "LiberationSans-Regular.ttf"],
}


def find_font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    expanded: list[str] = []
    for name in candidates:
        for alt in FONT_ALIASES.get(name, [name]):
            if alt not in expanded:
                expanded.append(alt)
    for name in expanded:
        for d in FONT_DIRS:
            path = os.path.join(d, name)
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def solid_bg(size: tuple[int, int], color=BG) -> Image.Image:
    return Image.new("RGB", size, color)


def draw_top_ribbon(draw: ImageDraw.ImageDraw, height: int = 88) -> int:
    """Etisalat-red ribbon along the top with the brand wordmark.
    Returns the y-coordinate just below the ribbon (for layout chaining)."""
    draw.rectangle([0, 0, W, height], fill=RED)
    # Brand wordmark, centered, white, tracked uppercase
    brand_font = find_font(["seguisb.ttf", "arialbd.ttf", "segoeui.ttf"], 32)
    draw_centered(draw, "UAE  PREMIUM  NUMBERS", brand_font,
                  (height - 32) // 2, WHITE, letter_spacing=8)
    # 1px highlight + 2px shadow under ribbon for depth on white
    draw.line([(0, height), (W, height)], fill=RED_DARK, width=1)
    return height


def draw_bottom_ribbon(draw: ImageDraw.ImageDraw, height: int = 78) -> None:
    """Red footer with domain + WhatsApp split."""
    y0 = H - height
    draw.rectangle([0, y0, W, H], fill=RED)
    draw.line([(0, y0), (W, y0)], fill=RED_DARK, width=1)

    domain_font = find_font(["seguisb.ttf", "arialbd.ttf", "segoeui.ttf"], 26)
    wa_font     = find_font(["seguisb.ttf", "arialbd.ttf", "segoeui.ttf"], 22)
    # Left: domain
    draw.text((75, y0 + (height - 26) // 2 - 2),
              "uaepremiumnumbers.com", font=domain_font, fill=WHITE)
    # Right: WhatsApp number
    wa_text = "WhatsApp +971 56 699 9377"
    tw, _ = text_size(draw, wa_text, wa_font)
    draw.text((W - 75 - tw, y0 + (height - 22) // 2 - 1),
              wa_text, font=wa_font, fill=WHITE)


def draw_plan_tag(draw: ImageDraw.ImageDraw, cx: int, cy: int,
                  price_aed: int = 188) -> tuple[int, int, int, int]:
    """Etisalat-red rounded tag with price + 'Plan included'. cx/cy = center.
    Returns the bbox so callers can lay things around it."""
    box_w, box_h = 340, 130          # widened from 280 — was clipping AED at 48pt
    x0, y0 = cx - box_w // 2, cy - box_h // 2
    x1, y1 = x0 + box_w, y0 + box_h

    # Drop-shadow plate (offset 4px, lighter red) — gives lift on white
    draw.rounded_rectangle([x0 + 4, y0 + 5, x1 + 4, y1 + 5],
                           radius=14, fill=(245, 200, 202))
    draw.rounded_rectangle([x0, y0, x1, y1], radius=14, fill=RED)

    # Price line — sized to fit cleanly inside the wider box
    price_font = find_font(["arialbd.ttf", "seguisb.ttf"], 44)
    price_text = f"AED {price_aed}/MO"
    pw, ph = text_size(draw, price_text, price_font)
    draw.text((x0 + (box_w - pw) // 2, y0 + 24),
              price_text, font=price_font, fill=WHITE)

    # Subtitle line
    sub_font = find_font(["seguisb.ttf", "segoeui.ttf"], 20)
    sub_text = "Plan included"
    sw, _ = text_size(draw, sub_text, sub_font)
    draw.text((x0 + (box_w - sw) // 2, y0 + 80),
              sub_text, font=sub_font, fill=(255, 220, 222))

    return x0, y0, x1, y1


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def draw_centered(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
                  y: int, fill, letter_spacing: int = 0) -> int:
    if letter_spacing == 0:
        w, h = text_size(draw, text, font)
        draw.text(((W - w) // 2, y), text, font=font, fill=fill)
        return h
    # Manual letter spacing
    char_widths = []
    for ch in text:
        cw, _ = text_size(draw, ch, font)
        char_widths.append(cw)
    total = sum(char_widths) + letter_spacing * (len(text) - 1)
    x = (W - total) // 2
    h = 0
    for ch, cw in zip(text, char_widths):
        bbox = draw.textbbox((x, y), ch, font=font)
        h = max(h, bbox[3] - bbox[1])
        draw.text((x, y), ch, font=font, fill=fill)
        x += cw + letter_spacing
    return h


def make_qr(url: str, box_size: int = 6) -> Image.Image:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


def format_display(digits: str) -> str:
    if len(digits) == 10 and digits.startswith("0"):
        return f"{digits[:3]} {digits[3:6]} {digits[6:]}"
    return digits


def render_card(digits: str, tier: str, reasons: list[str], out_path: str,
                site: str = "uaepremiumnumbers.com",
                wa: str = "+971 56 699 9377",
                plan_aed: int = 188) -> str:
    img = solid_bg((W, H))
    draw = ImageDraw.Draw(img)

    # ─── Top red ribbon with brand ─────────────────────────────────────
    draw_top_ribbon(draw, height=88)

    # ─── "AVAILABLE NOW" header in red, centered ────────────────────────
    label_font = find_font(["seguisb.ttf", "segoeui.ttf", "arialbd.ttf"], 28)
    draw_centered(draw, "AVAILABLE  NOW", label_font, 130, RED, letter_spacing=6)

    # Thin red divider under header
    div_y = 178
    draw.line([(W // 2 - 80, div_y), (W // 2 + 80, div_y)], fill=RED, width=2)

    # ─── Hero number ──────────────────────────────────────────────────
    display = format_display(digits)
    number_font = find_font(["georgiab.ttf", "georgia.ttf", "cambriab.ttf", "arialbd.ttf"], 124)
    draw_centered(draw, display, number_font, 240, INK, letter_spacing=6)

    # ─── Tier pill (white fill, red outline, red text) ──────────────────
    tier_text = tier.upper()
    tier_font = find_font(["seguisb.ttf", "arialbd.ttf"], 30)
    tw, th = text_size(draw, tier_text, tier_font)
    pill_pad_x, pill_pad_y = 30, 12
    pill_w, pill_h = tw + pill_pad_x * 2, th + pill_pad_y * 2
    pill_x, pill_y = (W - pill_w) // 2, 415
    draw.rounded_rectangle(
        [pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
        radius=pill_h // 2,
        fill=RED_TINT,
        outline=RED,
        width=2,
    )
    draw.text(
        (pill_x + pill_pad_x, pill_y + pill_pad_y - 2),
        tier_text, font=tier_font, fill=RED,
    )

    # ─── Two-column band: booking CTA (left) + plan tag (right) ────────
    band_y = 555
    # LEFT — booking CTA, centered around x=305
    left_cx = 305
    bk_label_font = find_font(["seguisb.ttf", "arialbd.ttf"], 22)
    bk_phone_font = find_font(["georgiab.ttf", "arialbd.ttf"], 38)
    bk_sub_font   = find_font(["segoeui.ttf", "arial.ttf"], 19)

    bk_label = "BOOKING OPEN"
    bw, _ = text_size(draw, bk_label, bk_label_font)
    draw.text((left_cx - bw // 2, band_y), bk_label, font=bk_label_font, fill=RED)

    pw, _ = text_size(draw, wa, bk_phone_font)
    draw.text((left_cx - pw // 2, band_y + 32), wa, font=bk_phone_font, fill=TEXT_DARK)

    sub = "Call or WhatsApp"
    sw, _ = text_size(draw, sub, bk_sub_font)
    draw.text((left_cx - sw // 2, band_y + 86), sub, font=bk_sub_font, fill=MUTED)

    # RIGHT — plan tag, centered around x=820
    draw_plan_tag(draw, cx=820, cy=band_y + 60, price_aed=plan_aed)

    # ─── QR code, centered, with hairline border on white bg ────────────
    qr_url = (
        f"https://{site}/choose-number/"
        f"?n={digits}&utm_source=facebook&utm_medium=organic&utm_campaign=card"
    )
    qr_img = make_qr(qr_url, box_size=5)   # box_size 5 → ~210px native, crisper
    qr_size = 200                          # smaller than 220 to leave room for caption
    qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.NEAREST)
    qr_x = (W - qr_size) // 2
    qr_y = 720
    # Hairline border so the QR sits cleanly on white (no plate needed,
    # but a 1px border anchors it visually)
    plate_pad = 10
    draw.rounded_rectangle(
        [qr_x - plate_pad, qr_y - plate_pad,
         qr_x + qr_size + plate_pad, qr_y + qr_size + plate_pad],
        radius=10, fill=WHITE, outline=HAIRLINE, width=1,
    )
    img.paste(qr_img, (qr_x, qr_y))

    # Caption below QR — pulled up to clear the bottom ribbon (starts y=1002)
    cap_font = find_font(["segoeui.ttf", "arial.ttf"], 20)
    draw_centered(draw, "scan to view this number online",
                  cap_font, qr_y + qr_size + 18, MUTED)

    # ─── Bottom red ribbon ────────────────────────────────────────────
    draw_bottom_ribbon(draw, height=78)

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
    p.add_argument("--digits", required=True)
    p.add_argument("--tier", default="Gold")
    p.add_argument("--reasons", default="", help="comma-separated short tags (unused in current layout, kept for call-compat with daily_generator)")
    p.add_argument("--out", required=True)
    p.add_argument("--plan-aed", type=int, default=188, dest="plan_aed",
                   help="Etisalat plan price shown in the right tag")
    args = p.parse_args()

    reasons = [r.strip() for r in args.reasons.split(",") if r.strip()]
    path = render_card(args.digits, args.tier, reasons, args.out,
                       plan_aed=args.plan_aed)
    print(path)


if __name__ == "__main__":
    main()
