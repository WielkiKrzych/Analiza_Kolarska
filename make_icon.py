#!/usr/bin/env python3
"""Generate the Analiza Kolarska app icon (original artwork, v2).

Design: a macOS-style squircle with a warm amber→crimson gradient, a minimalist
bike wheel (rim, hub, radial spokes) and a bold power lightning-bolt through it —
"cycling + power". Rendered at 4x and downsampled for crisp anti-aliased edges.
Outputs icon.png (1024x1024).
"""
import math

from PIL import Image, ImageDraw, ImageFilter

S = 1024
SS = 4
W = S * SS


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    return tuple(int(round(lerp(c1[i], c2[i], t))) for i in range(3))


def superellipse_mask(size, n=5.0):
    m = Image.new("L", (size, size), 0)
    px = m.load()
    c = (size - 1) / 2.0
    a = size / 2.0
    for y in range(size):
        for x in range(size):
            if (abs(x - c) / a) ** n + (abs(y - c) / a) ** n <= 1.0:
                px[x, y] = 255
    return m


def make_gradient(size, top, mid, bottom, glow):
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(size):
        t = y / (size - 1)
        if t < 0.5:
            base = mix(top, mid, t / 0.5)
        else:
            base = mix(mid, bottom, (t - 0.5) / 0.5)
        for x in range(size):
            px[x, y] = base
    gx, gy, gr = size * 0.5, size * 0.42, size * 0.75
    for y in range(size):
        for x in range(size):
            d = math.hypot(x - gx, y - gy) / gr
            if d < 1.0:
                k = (1.0 - d) ** 2 * 0.45
                r, g, b = px[x, y]
                px[x, y] = (min(255, int(r + (glow[0] - r) * k)),
                            min(255, int(g + (glow[1] - g) * k)),
                            min(255, int(b + (glow[2] - b) * k)))
    return img


def draw_wheel(draw, cx, cy, r, color, spokes=16):
    rim_w = int(r * 0.085)
    # outer rim
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=rim_w)
    # inner rim highlight
    r2 = r - rim_w * 1.6
    draw.ellipse([cx - r2, cy - r2, cx + r2, cy + r2],
                 outline=color, width=max(2, int(rim_w * 0.35)))
    # hub
    hub = r * 0.135
    draw.ellipse([cx - hub, cy - hub, cx + hub, cy + hub], fill=color)
    hub2 = hub * 0.5
    # spokes
    sw = max(2, int(r * 0.018))
    for i in range(spokes):
        ang = (2 * math.pi * i) / spokes
        x0 = cx + hub * 0.9 * math.cos(ang)
        y0 = cy + hub * 0.9 * math.sin(ang)
        x1 = cx + r2 * math.cos(ang)
        y1 = cy + r2 * math.sin(ang)
        draw.line([(x0, y0), (x1, y1)], fill=color, width=sw)
    return hub2


def draw_bolt(base_img, cx, cy, r, fill, glow):
    """Bold lightning bolt centered on the wheel, with soft glow."""
    scale = r * 1.05
    # normalized bolt polygon (classic zig-zag), y-down
    pts_n = [
        (0.16, -0.62), (-0.22, 0.06), (0.02, 0.06),
        (-0.16, 0.62), (0.24, -0.10), (-0.02, -0.10),
    ]
    pts = [(cx + px * scale, cy + py * scale) for px, py in pts_n]

    glow_layer = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)
    gd.polygon(pts, fill=glow + (255,))
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=int(r * 0.09)))
    base_img.alpha_composite(glow_layer)

    top = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    td = ImageDraw.Draw(top)
    td.polygon(pts, fill=fill + (255,))
    # thin outline for crispness
    td.line(pts + [pts[0]], fill=(255, 255, 255, 230), width=max(2, int(r * 0.012)),
            joint="curve")
    base_img.alpha_composite(top)


def main():
    top = (0x3A, 0x0C, 0x4A)      # deep plum
    mid = (0xC0, 0x2A, 0x4E)      # crimson
    bottom = (0xFF, 0x7A, 0x2D)   # amber-orange
    glow = (0xFF, 0xD1, 0x66)     # warm glow
    wheel_col = (0xFF, 0xF6, 0xEC)  # warm white
    bolt_fill = (0xFF, 0xD6, 0x3A)  # amber
    bolt_glow = (0xFF, 0x9A, 0x2A)  # orange glow

    bg = make_gradient(W, top, mid, bottom, glow).convert("RGBA")
    draw = ImageDraw.Draw(bg)
    cx = cy = W / 2
    r = W * 0.315
    draw_wheel(draw, cx, cy, r, wheel_col, spokes=18)
    draw_bolt(bg, cx, cy, r, bolt_fill, bolt_glow)

    mask = superellipse_mask(W, n=5.0)
    out = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    out.paste(bg, (0, 0), mask)
    final = out.resize((S, S), Image.LANCZOS)
    final.save("icon.png")
    print("wrote icon.png", final.size)


if __name__ == "__main__":
    main()
