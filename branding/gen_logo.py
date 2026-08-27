"""Generates the SwachhAI app icon: a 'chasing arrows' recycle mark
(three rounded arrow segments around a circle) in green, with a small
blue AI-spark accent badge - built entirely with PIL primitives so it's
crisp at any output size.
"""
import math
import numpy as np
from PIL import Image, ImageDraw

SIZE = 2048  # supersample, downscale later for crisp edges
CENTER = SIZE / 2

GREEN_DARK = (21, 87, 36, 255)      # background gradient dark
GREEN_LIGHT = (34, 170, 90, 255)     # background gradient light
ARROW_WHITE = (255, 255, 255, 255)
BLUE_ACCENT = (21, 101, 192, 255)    # matches app's "AI" badge blue
BLUE_ACCENT_LIGHT = (66, 165, 245, 255)


def radial_gradient_bg(size):
    yy, xx = np.mgrid[0:size, 0:size]
    max_r = size * 0.72
    d = np.hypot(xx - size / 2, yy - size / 2) / max_r
    d = np.clip(d, 0.0, 1.0)

    out = np.empty((size, size, 4), dtype=np.uint8)
    for c in range(3):
        out[..., c] = (GREEN_LIGHT[c] + (GREEN_DARK[c] - GREEN_LIGHT[c]) * d).astype(np.uint8)
    out[..., 3] = 255
    return Image.fromarray(out, "RGBA")


def draw_recycle_arrows(draw, center, outer_r, inner_r, gap_deg=26, color=ARROW_WHITE):
    cx, cy = center
    slot = 120
    band_w = outer_r - inner_r
    for i in range(3):
        start = i * slot + gap_deg / 2
        end = start + (slot - gap_deg)
        bbox_outer = [cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r]
        draw.pieslice(bbox_outer, start, end, fill=color)

        # punch the inner circle out to leave a ring/band (only overshoot
        # on the `start` side, which has no arrowhead - overshooting past
        # `end` would chip into the arrowhead's base corner there)
        bbox_inner = [cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r]
        draw.pieslice(bbox_inner, start - 3, end, fill=(0, 0, 0, 0))

        # Arrowhead: base is exactly the band's straight radial edge at
        # `end`, apex extends tangentially forward (increasing-angle
        # direction) so it seams cleanly onto the band with no notches.
        ang = math.radians(end)
        p_in = (cx + inner_r * math.cos(ang), cy + inner_r * math.sin(ang))
        p_out = (cx + outer_r * math.cos(ang), cy + outer_r * math.sin(ang))
        mid = ((p_in[0] + p_out[0]) / 2, (p_in[1] + p_out[1]) / 2)

        tang_x, tang_y = -math.sin(ang), math.cos(ang)  # forward tangent
        head_len = band_w * 1.35
        apex = (mid[0] + head_len * tang_x, mid[1] + head_len * tang_y)

        # base corners sit exactly on the band's inner/outer radii - no
        # extra widen, so the triangle reads as one clean point (a widened
        # base creates a spike poking past the ring edge)
        draw.polygon([apex, p_out, p_in], fill=color)


def make_mark(size=SIZE, transparent_bg=False):
    bg = Image.new("RGBA", (size, size), (0, 0, 0, 0)) if transparent_bg else radial_gradient_bg(size)
    ring_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(ring_layer)

    outer_r = size * 0.335
    inner_r = size * 0.205
    draw_recycle_arrows(d, (size / 2, size / 2), outer_r, inner_r, gap_deg=24, color=ARROW_WHITE)

    combined = Image.alpha_composite(bg, ring_layer)

    # AI accent: small blue circular badge, lower-right, with a spark glyph
    badge_r = size * 0.135
    bx = size * 0.755
    by = size * 0.745
    bd = ImageDraw.Draw(combined)
    # subtle white ring so the badge separates from the green background
    bd.ellipse([bx - badge_r - size*0.012, by - badge_r - size*0.012,
                bx + badge_r + size*0.012, by + badge_r + size*0.012], fill=(255, 255, 255, 255))
    bd.ellipse([bx - badge_r, by - badge_r, bx + badge_r, by + badge_r], fill=BLUE_ACCENT)

    # 4-point spark/star glyph inside the badge
    spark_r_out = badge_r * 0.62
    spark_r_in = badge_r * 0.22
    pts = []
    for k in range(8):
        ang = math.radians(k * 45 - 90)
        r = spark_r_out if k % 2 == 0 else spark_r_in
        pts.append((bx + r * math.cos(ang), by + r * math.sin(ang)))
    bd.polygon(pts, fill=(255, 255, 255, 255))

    return combined


if __name__ == "__main__":
    icon = make_mark(SIZE, transparent_bg=False)
    icon_small = icon.resize((512, 512), Image.LANCZOS)
    icon_small.save("logo_preview_512.png")
    print("saved logo_preview_512.png")
