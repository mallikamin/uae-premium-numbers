"""
Generate brand assets for etisalat.shop
- OG image (1200x630)
- Favicon (favicon.ico, 32x32)
- App icons (icon-192.png, icon-512.png)

Uses PIL/Pillow only with system fonts.
"""

from PIL import Image, ImageDraw, ImageFont
import os
import struct

# ── Config ──────────────────────────────────────────────────────────────────
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
BG_COLOR = (13, 17, 23)          # #0D1117
GOLD = (201, 169, 98)            # #C9A962
GOLD_LIGHT = (232, 213, 163)     # #E8D5A3
TEXT_WHITE = (245, 245, 240)     # #F5F5F0
TEXT_MUTED = (180, 180, 175)     # Muted text approximation
WHATSAPP_GREEN = (37, 211, 102)  # #25D366


def load_font(bold=False, size=40):
    """Load system font with fallbacks."""
    font_candidates = []
    if bold:
        font_candidates = [
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/calibrib.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    else:
        font_candidates = [
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]

    for path in font_candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue

    print(f"  [warn] No system font found, using default bitmap font")
    return ImageFont.load_default()


def draw_gold_gradient_line(draw, y, x_start, x_end, height, img_width):
    """Draw a horizontal line with gold gradient effect."""
    for x in range(x_start, x_end):
        t = (x - x_start) / max(1, (x_end - x_start))
        # Gold to gold-light to gold
        if t < 0.5:
            t2 = t * 2
            r = int(GOLD[0] + (GOLD_LIGHT[0] - GOLD[0]) * t2)
            g = int(GOLD[1] + (GOLD_LIGHT[1] - GOLD[1]) * t2)
            b = int(GOLD[2] + (GOLD_LIGHT[2] - GOLD[2]) * t2)
        else:
            t2 = (t - 0.5) * 2
            r = int(GOLD_LIGHT[0] + (GOLD[0] - GOLD_LIGHT[0]) * t2)
            g = int(GOLD_LIGHT[1] + (GOLD[1] - GOLD_LIGHT[1]) * t2)
            b = int(GOLD_LIGHT[2] + (GOLD[2] - GOLD_LIGHT[2]) * t2)
        draw.rectangle([x, y, x, y + height - 1], fill=(r, g, b))


def draw_gold_text(draw, position, text, font, img):
    """Draw text with a gold gradient fill effect."""
    # Create a temporary image for the text mask
    bbox = font.getbbox(text)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # Create text mask
    mask = Image.new('L', (text_w + 20, text_h + 20), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.text((10, 10 - bbox[1]), text, font=font, fill=255)

    # Create gradient image
    gradient = Image.new('RGB', mask.size, BG_COLOR)
    grad_draw = ImageDraw.Draw(gradient)
    for x in range(mask.size[0]):
        t = x / max(1, mask.size[0])
        if t < 0.35:
            t2 = t / 0.35
            r = int(GOLD[0] + (GOLD_LIGHT[0] - GOLD[0]) * t2)
            g = int(GOLD[1] + (GOLD_LIGHT[1] - GOLD[1]) * t2)
            b = int(GOLD[2] + (GOLD_LIGHT[2] - GOLD[2]) * t2)
        elif t < 0.65:
            r, g, b = GOLD_LIGHT
        else:
            t2 = (t - 0.65) / 0.35
            r = int(GOLD_LIGHT[0] + (GOLD[0] - GOLD_LIGHT[0]) * t2)
            g = int(GOLD_LIGHT[1] + (GOLD[1] - GOLD_LIGHT[1]) * t2)
            b = int(GOLD_LIGHT[2] + (GOLD[2] - GOLD_LIGHT[2]) * t2)
        grad_draw.line([(x, 0), (x, mask.size[1])], fill=(r, g, b))

    # Paste gradient text onto main image
    x, y = position
    x_paste = x - 10
    y_paste = y - 10
    img.paste(gradient, (x_paste, y_paste), mask)


def generate_og_image():
    """Generate OG social share image (1200x630)."""
    print("Generating og-image.png (1200x630)...")
    W, H = 1200, 630
    img = Image.new('RGB', (W, H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Top gold accent line
    draw_gold_gradient_line(draw, 0, 0, W, 4, W)

    # Bottom gold accent line
    draw_gold_gradient_line(draw, H - 4, 0, W, 4, W)

    # Load fonts
    font_title = load_font(bold=True, size=64)
    font_subtitle = load_font(bold=False, size=26)
    font_features = load_font(bold=False, size=22)
    font_price = load_font(bold=True, size=36)
    font_contact = load_font(bold=False, size=20)

    # "etisalat.shop" - large gold gradient text, centered
    title_text = "etisalat.shop"
    title_bbox = font_title.getbbox(title_text)
    title_w = title_bbox[2] - title_bbox[0]
    title_x = (W - title_w) // 2
    title_y = 120
    draw_gold_text(draw, (title_x, title_y), title_text, font_title, img)

    # Subtitle: "Authorized Etisalat Dealer -- UAE"
    subtitle_text = "Authorized Etisalat Dealer \u2014 UAE"
    subtitle_bbox = font_subtitle.getbbox(subtitle_text)
    subtitle_w = subtitle_bbox[2] - subtitle_bbox[0]
    subtitle_x = (W - subtitle_w) // 2
    subtitle_y = title_y + 85
    draw.text((subtitle_x, subtitle_y), subtitle_text, fill=TEXT_WHITE, font=font_subtitle)

    # Gold separator line
    sep_w = 200
    sep_y = subtitle_y + 50
    draw_gold_gradient_line(draw, sep_y, (W - sep_w) // 2, (W + sep_w) // 2, 2, W)

    # Features line
    features_text = "Postpaid Plans  |  VIP Numbers  |  Unlimited Data & Calling"
    features_bbox = font_features.getbbox(features_text)
    features_w = features_bbox[2] - features_bbox[0]
    features_x = (W - features_w) // 2
    features_y = sep_y + 25
    draw.text((features_x, features_y), features_text, fill=TEXT_MUTED, font=font_features)

    # Price highlight box
    price_text = "From AED 188/mo"
    price_bbox = font_price.getbbox(price_text)
    price_w = price_bbox[2] - price_bbox[0]
    price_h = price_bbox[3] - price_bbox[1]
    box_pad_x, box_pad_y = 30, 16
    box_w = price_w + box_pad_x * 2
    box_h = price_h + box_pad_y * 2
    box_x = (W - box_w) // 2
    box_y = features_y + 55

    # Draw rounded price box with gold border
    draw.rounded_rectangle(
        [box_x, box_y, box_x + box_w, box_y + box_h],
        radius=10,
        outline=GOLD,
        width=2
    )
    price_x = box_x + box_pad_x
    price_y = box_y + box_pad_y - 2
    draw_gold_text(draw, (price_x, price_y), price_text, font_price, img)

    # WhatsApp contact at bottom
    wa_text = "+971 56 699 9377"
    wa_bbox = font_contact.getbbox(wa_text)
    wa_w = wa_bbox[2] - wa_bbox[0]

    # Draw a small green circle as WhatsApp icon indicator
    circle_r = 10
    total_w = circle_r * 2 + 10 + wa_w
    start_x = (W - total_w) // 2
    wa_y = box_y + box_h + 45

    # Green circle
    draw.ellipse(
        [start_x, wa_y + 2, start_x + circle_r * 2, wa_y + 2 + circle_r * 2],
        fill=WHATSAPP_GREEN
    )
    # "W" inside circle
    w_font = load_font(bold=True, size=14)
    draw.text((start_x + 5, wa_y + 3), "W", fill=(255, 255, 255), font=w_font)

    # Phone number
    draw.text((start_x + circle_r * 2 + 10, wa_y), wa_text, fill=TEXT_WHITE, font=font_contact)

    # Save
    path = os.path.join(OUTPUT_DIR, "og-image.png")
    img.save(path, "PNG", quality=95)
    print(f"  Saved: {path}")


def draw_sim_chip(draw, cx, cy, size, gold_color, gold_light_color):
    """Draw a simplified SIM chip icon centered at (cx, cy)."""
    # Outer rounded rectangle (SIM card body)
    card_w = size
    card_h = int(size * 1.3)
    corner_cut = int(size * 0.2)  # top-right corner cut for SIM card shape

    x1 = cx - card_w // 2
    y1 = cy - card_h // 2
    x2 = cx + card_w // 2
    y2 = cy + card_h // 2

    # Draw SIM card outline with corner cut
    points = [
        (x1, y1),
        (x2 - corner_cut, y1),
        (x2, y1 + corner_cut),
        (x2, y2),
        (x1, y2),
    ]
    draw.polygon(points, fill=None, outline=gold_color, width=max(2, size // 30))

    # Inner chip rectangle
    chip_w = int(size * 0.55)
    chip_h = int(size * 0.45)
    chip_x1 = cx - chip_w // 2
    chip_y1 = cy - chip_h // 2 - int(size * 0.08)
    chip_x2 = chip_x1 + chip_w
    chip_y2 = chip_y1 + chip_h

    draw.rounded_rectangle(
        [chip_x1, chip_y1, chip_x2, chip_y2],
        radius=max(2, size // 20),
        fill=gold_color,
        outline=gold_light_color,
        width=max(1, size // 40)
    )

    # Chip contact lines (horizontal and vertical)
    line_color = BG_COLOR
    line_w = max(1, size // 40)
    mid_x = (chip_x1 + chip_x2) // 2
    mid_y = (chip_y1 + chip_y2) // 2

    # Horizontal center line
    draw.line([(chip_x1 + 3, mid_y), (chip_x2 - 3, mid_y)], fill=line_color, width=line_w)
    # Vertical center line
    draw.line([(mid_x, chip_y1 + 3), (mid_x, chip_y2 - 3)], fill=line_color, width=line_w)
    # Two additional horizontal lines
    qy1 = chip_y1 + (mid_y - chip_y1) // 2
    qy2 = mid_y + (chip_y2 - mid_y) // 2
    draw.line([(chip_x1 + 3, qy1), (mid_x - 2, qy1)], fill=line_color, width=line_w)
    draw.line([(mid_x + 2, qy2), (chip_x2 - 3, qy2)], fill=line_color, width=line_w)


def generate_app_icon(size, filename):
    """Generate app icon with SIM chip design."""
    print(f"Generating {filename} ({size}x{size})...")
    img = Image.new('RGB', (size, size), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # SIM chip icon in upper portion
    chip_size = int(size * 0.35)
    chip_cy = int(size * 0.4)
    draw_sim_chip(draw, size // 2, chip_cy, chip_size, GOLD, GOLD_LIGHT)

    # "e.shop" text below the chip
    font_size = max(12, int(size * 0.1))
    font = load_font(bold=True, size=font_size)
    text = "e.shop"
    bbox = font.getbbox(text)
    text_w = bbox[2] - bbox[0]
    text_x = (size - text_w) // 2
    text_y = int(size * 0.68)
    draw_gold_text(draw, (text_x, text_y), text, font, img)

    # Subtle gold border (rounded rect inset)
    border_inset = max(4, size // 30)
    draw.rounded_rectangle(
        [border_inset, border_inset, size - border_inset, size - border_inset],
        radius=max(8, size // 10),
        outline=GOLD,
        width=max(1, size // 100)
    )

    path = os.path.join(OUTPUT_DIR, filename)
    img.save(path, "PNG")
    print(f"  Saved: {path}")


def generate_favicon():
    """Generate favicon.ico (32x32) with gold 'e' on dark navy."""
    print("Generating favicon.ico (32x32)...")
    size = 32
    img = Image.new('RGBA', (size, size), (*BG_COLOR, 255))
    draw = ImageDraw.Draw(img)

    # Gold "e" centered
    font = load_font(bold=True, size=24)
    text = "e"
    bbox = font.getbbox(text)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size - text_w) // 2
    y = (size - text_h) // 2 - bbox[1]
    draw.text((x, y), text, fill=GOLD, font=font)

    # Save as ICO using Pillow's built-in ICO support
    path = os.path.join(OUTPUT_DIR, "favicon.ico")
    # Convert to RGB for ICO compatibility, add a 32x32 and 16x16 size
    img_rgb = img.convert('RGB')
    img_16 = img_rgb.resize((16, 16), Image.LANCZOS)

    # Pillow can save ICO directly
    img_rgb.save(path, format='ICO', sizes=[(32, 32), (16, 16)])
    print(f"  Saved: {path}")


def main():
    print("=" * 60)
    print("  etisalat.shop Asset Generator")
    print("=" * 60)
    print(f"  Output: {OUTPUT_DIR}")
    print()

    generate_og_image()
    generate_favicon()
    generate_app_icon(192, "icon-192.png")
    generate_app_icon(512, "icon-512.png")

    print()
    print("All assets generated successfully.")
    print()

    # Verify all files exist
    expected = ["og-image.png", "favicon.ico", "icon-192.png", "icon-512.png"]
    all_ok = True
    for f in expected:
        full_path = os.path.join(OUTPUT_DIR, f)
        if os.path.exists(full_path):
            file_size = os.path.getsize(full_path)
            print(f"  [OK] {f} ({file_size:,} bytes)")
        else:
            print(f"  [MISSING] {f}")
            all_ok = False

    if all_ok:
        print("\nAll files verified.")
    else:
        print("\nSome files are missing!")

    return all_ok


if __name__ == "__main__":
    main()
