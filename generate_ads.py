from PIL import Image, ImageDraw, ImageFont
import os

OUT = os.path.dirname(os.path.abspath(__file__))

# Colors
BG = (13, 17, 23)        # #0D1117
SURFACE = (22, 27, 34)   # #161B22
GOLD = (201, 169, 98)    # #C9A962
GOLD_LIGHT = (232, 213, 163)  # #E8D5A3
WHITE = (245, 245, 240)
MUTED = (160, 160, 155)

def get_font(size, bold=False):
    """Try to get a good font, fallback to default"""
    font_names = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for fn in font_names:
        try:
            return ImageFont.truetype(fn, size)
        except:
            pass
    return ImageFont.load_default()

def draw_rounded_rect(draw, xy, radius, fill):
    x0, y0, x1, y1 = xy
    draw.rectangle([x0+radius, y0, x1-radius, y1], fill=fill)
    draw.rectangle([x0, y0+radius, x1, y1-radius], fill=fill)
    draw.pieslice([x0, y0, x0+2*radius, y0+2*radius], 180, 270, fill=fill)
    draw.pieslice([x1-2*radius, y0, x1, y0+2*radius], 270, 360, fill=fill)
    draw.pieslice([x0, y1-2*radius, x0+2*radius, y1], 90, 180, fill=fill)
    draw.pieslice([x1-2*radius, y1-2*radius, x1, y1], 0, 90, fill=fill)

def draw_gold_line(draw, y, x0, x1, thickness=3):
    for i in range(thickness):
        draw.line([(x0, y+i), (x1, y+i)], fill=GOLD)

def draw_sim_card(draw, cx, cy, size=120):
    """Draw a stylized SIM card icon"""
    w, h = size, int(size * 1.3)
    x0, y0 = cx - w//2, cy - h//2
    # Card outline
    draw_rounded_rect(draw, (x0, y0, x0+w, y0+h), 10, GOLD)
    # Inner chip
    chip_margin = size // 4
    cx0 = x0 + chip_margin
    cy0 = y0 + h//3
    cw = w - 2*chip_margin
    ch = h//3
    draw_rounded_rect(draw, (cx0, cy0, cx0+cw, cy0+ch), 6, BG)
    # Chip lines
    mid_x = cx0 + cw//2
    mid_y = cy0 + ch//2
    draw.line([(cx0+4, mid_y), (cx0+cw-4, mid_y)], fill=GOLD_LIGHT, width=1)
    draw.line([(mid_x, cy0+4), (mid_x, cy0+ch-4)], fill=GOLD_LIGHT, width=1)

# ============================================
# 1. SQUARE AD IMAGE (1200x1200)
# ============================================
img = Image.new('RGB', (1200, 1200), BG)
draw = ImageDraw.Draw(img)

# Top accent bar
draw.rectangle([0, 0, 1200, 6], fill=GOLD)

# Draw SIM card
draw_sim_card(draw, 600, 280, size=160)

# Gold divider
draw_gold_line(draw, 400, 400, 800, 3)

# Main text
font_big = get_font(72, bold=True)
font_med = get_font(42, bold=True)
font_small = get_font(32)
font_price = get_font(56, bold=True)

# "ETISALAT PLANS"
draw.text((600, 440), "ETISALAT", fill=GOLD, font=font_big, anchor="mt")
draw.text((600, 530), "PREMIUM PLANS", fill=WHITE, font=font_med, anchor="mt")

# Divider
draw_gold_line(draw, 600, 450, 750, 2)

# Price
draw.text((600, 650), "From AED 188/mo", fill=GOLD_LIGHT, font=font_price, anchor="mt")

# Features
features = ["Unlimited Data & Calling", "VIP Gold & Platinum Numbers", "Free SIM Delivery — All UAE"]
y = 760
for feat in features:
    # Gold bullet
    draw.ellipse([440, y+8, 456, y+24], fill=GOLD)
    draw.text((475, y), feat, fill=WHITE, font=font_small)
    y += 55

# Bottom bar
draw.rectangle([0, 1100, 1200, 1106], fill=GOLD)
font_brand = get_font(36, bold=True)
draw.text((600, 1140), "etisalat.shop", fill=GOLD, font=font_brand, anchor="mt")
font_tag = get_font(24)
draw.text((600, 1180), "Authorized Etisalat Dealer", fill=MUTED, font=font_tag, anchor="mt")

img.save(os.path.join(OUT, "ad-square.png"), quality=95)
print("Created: ad-square.png (1200x1200)")

# ============================================
# 2. HORIZONTAL AD IMAGE (1200x628)
# ============================================
img2 = Image.new('RGB', (1200, 628), BG)
draw2 = ImageDraw.Draw(img2)

# Top accent
draw2.rectangle([0, 0, 1200, 4], fill=GOLD)

# Left side — SIM card
draw_sim_card(draw2, 200, 280, size=130)

# Left brand
font_sm_brand = get_font(22)
draw2.text((200, 400), "etisalat.shop", fill=GOLD, font=get_font(28, bold=True), anchor="mt")
draw2.text((200, 435), "Authorized Dealer", fill=MUTED, font=font_sm_brand, anchor="mt")

# Vertical gold line separator
for i in range(2):
    draw2.line([(380, 80), (380, 548)], fill=GOLD, width=1)

# Right side — content
font_h1 = get_font(58, bold=True)
font_h2 = get_font(36, bold=True)
font_body = get_font(28)
font_cta = get_font(32, bold=True)

draw2.text((430, 80), "ETISALAT", fill=GOLD, font=font_h1)
draw2.text((430, 150), "PREMIUM PLANS", fill=WHITE, font=font_h2)

draw_gold_line(draw2, 210, 430, 700, 2)

# Features on right
features2 = [
    "Unlimited Data from AED 188/mo",
    "VIP Gold & Platinum Numbers",
    "Unlimited International Calling",
    "Free SIM Delivery — All UAE"
]
y2 = 240
for feat in features2:
    draw2.ellipse([440, y2+6, 454, y2+20], fill=GOLD)
    draw2.text((470, y2), feat, fill=WHITE, font=font_body)
    y2 += 48

# CTA button
draw_rounded_rect(draw2, (430, 470, 750, 530), 12, GOLD)
draw2.text((590, 500), "Order on WhatsApp", fill=BG, font=font_cta, anchor="mm")

# WhatsApp number
draw2.text((800, 500), "+971 56 699 9377", fill=MUTED, font=font_body, anchor="lm")

# Bottom accent
draw2.rectangle([0, 624, 1200, 628], fill=GOLD)

img2.save(os.path.join(OUT, "ad-horizontal.png"), quality=95)
print("Created: ad-horizontal.png (1200x628)")

# ============================================
# 3. SQUARE LOGO (1200x1200)
# ============================================
logo = Image.new('RGB', (1200, 1200), BG)
draw3 = ImageDraw.Draw(logo)

# Outer gold circle
cx, cy, r = 600, 540, 400
for i in range(4):
    draw3.ellipse([cx-r-i, cy-r-i, cx+r+i, cy+r+i], outline=GOLD)

# Inner circle
r2 = 350
draw3.ellipse([cx-r2, cy-r2, cx+r2, cy+r2], fill=SURFACE)

# SIM card icon in center (smaller)
draw_sim_card(draw3, cx, cy - 60, size=140)

# Brand text inside circle
font_logo = get_font(64, bold=True)
font_logo_sub = get_font(28)
draw3.text((cx, cy + 120), "etisalat.shop", fill=GOLD, font=font_logo, anchor="mm")
draw3.text((cx, cy + 170), "AUTHORIZED DEALER", fill=MUTED, font=font_logo_sub, anchor="mm")

# Gold dots at cardinal points
dot_r = 10
for angle_offset, dx, dy in [(0, 0, -r-15), (1, r+15, 0), (2, 0, r+15), (3, -r-15, 0)]:
    draw3.ellipse([cx+dx-dot_r, cy+dy-dot_r, cx+dx+dot_r, cy+dy+dot_r], fill=GOLD)

logo.save(os.path.join(OUT, "logo-square.png"), quality=95)
print("Created: logo-square.png (1200x1200)")

print("\nAll 3 images saved to:", OUT)
