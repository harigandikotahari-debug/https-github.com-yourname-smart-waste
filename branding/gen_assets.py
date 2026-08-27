"""Generates the full SwachhAI brand asset set from the finalized mark
(gen_logo.make_mark): Play Store icon, Android adaptive-icon layers,
Play Store feature graphic, and a web favicon.
"""
import math
from PIL import Image, ImageDraw, ImageFont

from gen_logo import (
    ARROW_WHITE, BLUE_ACCENT, GREEN_DARK, GREEN_LIGHT,
    draw_recycle_arrows, make_mark, radial_gradient_bg,
)

FONT_BOLD = "C:/Windows/Fonts/segoeuib.ttf"
FONT_REG = "C:/Windows/Fonts/segoeui.ttf"

OUT = "."


def save(img, name, size=None):
    if size:
        img = img.resize((size, size) if isinstance(size, int) else size, Image.LANCZOS)
    img.save(f"{OUT}/{name}")
    print("saved", name, img.size)


def make_icon_only_mark(size, transparent=True):
    """Just the ring+badge (no background fill), for compositing onto an
    adaptive-icon foreground layer or a differently-colored surface."""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    outer_r = size * 0.335
    inner_r = size * 0.205
    draw_recycle_arrows(d, (size / 2, size / 2), outer_r, inner_r, gap_deg=24, color=ARROW_WHITE)

    badge_r = size * 0.135
    bx, by = size * 0.755, size * 0.745
    d.ellipse([bx - badge_r - size*0.012, by - badge_r - size*0.012,
               bx + badge_r + size*0.012, by + badge_r + size*0.012], fill=(255, 255, 255, 255))
    d.ellipse([bx - badge_r, by - badge_r, bx + badge_r, by + badge_r], fill=BLUE_ACCENT)
    spark_r_out, spark_r_in = badge_r * 0.62, badge_r * 0.22
    pts = []
    for k in range(8):
        ang = math.radians(k * 45 - 90)
        r = spark_r_out if k % 2 == 0 else spark_r_in
        pts.append((bx + r * math.cos(ang), by + r * math.sin(ang)))
    d.polygon(pts, fill=(255, 255, 255, 255))
    return layer


def make_play_store_icon():
    # Play Store requires a flat 512x512 PNG with NO alpha channel.
    icon = make_mark(2048, transparent_bg=False).convert("RGB")
    save(icon, "play_store_icon_512.png", 512)


def make_adaptive_icon_layers():
    # Android adaptive icons: 108dp icon, only the inner ~66dp "safe zone"
    # is guaranteed visible after masking (circle/squircle/rounded-square).
    # Export at 432px (4x of 108dp) as is standard practice.
    size = 432
    bg = radial_gradient_bg(size)
    save(bg, "adaptive_background_432.png")

    fg = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mark = make_icon_only_mark(int(size * 0.62), transparent=True)
    offset = ((size - mark.width) // 2, (size - mark.height) // 2)
    fg.alpha_composite(mark, offset)
    save(fg, "adaptive_foreground_432.png")


def make_feature_graphic():
    # Play Store feature graphic: exactly 1024x500, opaque.
    w, h = 1024, 500
    yy_size = max(w, h) * 2
    bg_big = radial_gradient_bg(yy_size)
    bg = bg_big.crop(((yy_size - w) // 2, (yy_size - h) // 2, (yy_size - w) // 2 + w, (yy_size - h) // 2 + h))
    bg = bg.convert("RGB")
    draw = ImageDraw.Draw(bg)

    mark_size = 340
    mark = make_icon_only_mark(mark_size)
    bg.paste(mark, (60, (h - mark_size) // 2), mark)

    title_font = ImageFont.truetype(FONT_BOLD, 92)
    tag_font = ImageFont.truetype(FONT_REG, 30)
    tx = 60 + mark_size + 40
    draw.text((tx, 165), "SwachhAI", font=title_font, fill=(255, 255, 255, 255))
    draw.text((tx + 4, 275), "AI Smart Waste Segregation & Collection", font=tag_font, fill=(230, 245, 235, 255))

    save(bg, "feature_graphic_1024x500.png")


def make_favicon():
    icon = make_mark(1024, transparent_bg=False)
    save(icon, "favicon_180.png", 180)
    save(icon, "favicon_32.png", 32)


if __name__ == "__main__":
    make_play_store_icon()
    make_adaptive_icon_layers()
    make_feature_graphic()
    make_favicon()
