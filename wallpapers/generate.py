#!/usr/bin/env python3
"""Generate the original DeepSeek-inspired 4K wallpaper (no external assets).

Run from anywhere: python3 wallpapers/generate.py
"""

import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deepseek-neural-whale-4k.jpg")

W, H = 3840, 2160
random.seed(20261119)

BLUE = (77, 107, 254)
BRIGHT = (138, 180, 255)
CYAN = (110, 231, 255)
TEXT = (205, 214, 244)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def vertical_gradient(top, bottom):
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        draw.line([(0, y), (W, y)], fill=lerp(top, bottom, y / (H - 1)))
    return img


def radial_glow(size, center, radius, color, peak):
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    cx, cy = center
    steps = 90
    for i in range(steps, 0, -1):
        t = i / steps
        alpha = int(peak * (1 - t) ** 2)
        r = radius * t
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            fill=color + (alpha,),
        )
    return layer.filter(ImageFilter.GaussianBlur(radius * 0.08))


def catmull_rom(points, samples_per_segment=28, closed=True):
    pts = []
    n = len(points)
    if closed:
        seq = [points[-1]] + points + [points[0], points[1]]
    else:
        seq = [points[0]] + points + [points[-1]]
    for i in range(1, len(seq) - 2):
        p0, p1, p2, p3 = seq[i - 1], seq[i], seq[i + 1], seq[i + 2]
        for s in range(samples_per_segment):
            t = s / samples_per_segment
            t2, t3 = t * t, t * t * t
            x = 0.5 * (
                (2 * p1[0])
                + (-p0[0] + p2[0]) * t
                + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
            )
            y = 0.5 * (
                (2 * p1[1])
                + (-p0[1] + p2[1]) * t
                + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
            )
            pts.append((x, y))
    return pts


def point_in_poly(x, y, poly):
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi) + xi
        ):
            inside = not inside
        j = i
    return inside


def to_canvas(points, box):
    x0, y0, x1, y1 = box
    return [(x0 + x * (x1 - x0), y0 + y * (y1 - y0)) for x, y in points]


# --- background -----------------------------------------------------------------

img = vertical_gradient((3, 6, 16), (8, 16, 40)).convert("RGBA")

# large cold glow behind the subject
img = Image.alpha_composite(
    img, radial_glow((W, H), (int(W * 0.55), int(H * 0.52)), int(W * 0.52), (20, 50, 140), 150)
)
# faint cyan pool lower-left
img = Image.alpha_composite(
    img, radial_glow((W, H), (int(W * 0.30), int(H * 0.78)), int(W * 0.28), (20, 90, 130), 55)
)

# sparse dot grid
grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
gd = ImageDraw.Draw(grid)
for gx in range(0, W, 64):
    for gy in range(0, H, 64):
        a = 18 if (gx // 64 + gy // 64) % 2 == 0 else 9
        gd.ellipse([gx - 1, gy - 1, gx + 1, gy + 1], fill=(120, 160, 255, a))
img = Image.alpha_composite(img, grid)

# hex-ish contours and sonar rings
deco = Image.new("RGBA", (W, H), (0, 0, 0, 0))
dd = ImageDraw.Draw(deco)
cx, cy = int(W * 0.55), int(H * 0.53)
for r in range(int(W * 0.12), int(W * 0.42), 120):
    dd.arc([cx - r, cy - r, cx + r, cy + r], 200, 340, fill=(80, 120, 240, 18), width=2)
for r in range(180, 700, 110):
    dd.arc([cx - r, cy - r, cx + r, cy + r], 20, 160, fill=(80, 180, 240, 10), width=1)
img = Image.alpha_composite(img, deco)

# particles
rng = random.Random(7)
particles = Image.new("RGBA", (W, H), (0, 0, 0, 0))
pd = ImageDraw.Draw(particles)
for _ in range(420):
    px = rng.randint(0, W - 1)
    py = rng.randint(0, H - 1)
    r = rng.choice([1, 1, 1, 2, 2, 3])
    a = rng.randint(25, 110)
    col = rng.choice([BLUE, BRIGHT, CYAN])
    pd.ellipse([px - r, py - r, px + r, py + r], fill=col + (a,))
img = Image.alpha_composite(img, particles)

# --- whale geometry -------------------------------------------------------------

# normalized, facing left; tail on the right
body_norm = [
    (0.08, 0.52),
    (0.11, 0.45),
    (0.20, 0.39),
    (0.34, 0.36),
    (0.50, 0.37),
    (0.65, 0.41),
    (0.78, 0.44),
    (0.86, 0.46),
    (0.95, 0.35),
    (0.97, 0.38),
    (0.91, 0.47),
    (0.97, 0.57),
    (0.95, 0.60),
    (0.86, 0.53),
    (0.78, 0.56),
    (0.65, 0.60),
    (0.50, 0.66),
    (0.34, 0.68),
    (0.20, 0.64),
    (0.11, 0.58),
]
box = (int(W * 0.09), int(H * 0.20), int(W * 0.91), int(H * 0.80))
body = to_canvas(catmull_rom(body_norm, 32, True), box)

fin_norm = [
    (0.36, 0.60),
    (0.28, 0.75),
    (0.44, 0.63),
]
fin = to_canvas(fin_norm, box)

dorsal_norm = [
    (0.51, 0.38),
    (0.535, 0.35),
    (0.565, 0.355),
    (0.59, 0.39),
]
dorsal = to_canvas(dorsal_norm, box)

# fill the silhouette with a dark blue gradient
mask = Image.new("L", (W, H), 0)
md = ImageDraw.Draw(mask)
md.polygon(body, fill=255)
md.polygon(fin, fill=255)
md.polygon(dorsal, fill=255)
fill = vertical_gradient((10, 24, 56), (3, 6, 15)).convert("RGBA")
whale = Image.new("RGBA", (W, H), (0, 0, 0, 0))
whale.paste(fill, (0, 0), mask)
img = Image.alpha_composite(img, whale)

# soft inner light near the top of the back
inner = Image.new("RGBA", (W, H), (0, 0, 0, 0))
idraw = ImageDraw.Draw(inner)
idraw.polygon(body, fill=(30, 70, 180, 28))
inner = inner.filter(ImageFilter.GaussianBlur(40))
inner.putalpha(Image.composite(inner.getchannel("A"), Image.new("L", (W, H), 0), mask))
img = Image.alpha_composite(img, inner)

# --- outline + glow -------------------------------------------------------------

outline = Image.new("RGBA", (W, H), (0, 0, 0, 0))
od = ImageDraw.Draw(outline)
od.line(body + [body[0]], fill=BLUE + (230,), width=5, joint="curve")
od.line(fin, fill=BLUE + (190,), width=4, joint="curve")
od.line(dorsal, fill=BLUE + (190,), width=4, joint="curve")

glow = outline.filter(ImageFilter.GaussianBlur(26))
img = Image.alpha_composite(img, glow)
img = Image.alpha_composite(img, glow)
img = Image.alpha_composite(img, outline)

# --- neural network inside the body ---------------------------------------------

rng = random.Random(42)
nodes = []

# outline nodes
for i in range(0, len(body), 9):
    nodes.append(body[i])
for i in range(0, len(fin), 7):
    nodes.append(fin[i])
for i in range(0, len(dorsal), 5):
    nodes.append(dorsal[i])

# interior nodes
bx0, by0, bx1, by1 = box
attempts = 0
while len(nodes) < 190 and attempts < 60000:
    attempts += 1
    x = rng.uniform(bx0, bx1)
    y = rng.uniform(by0, by1)
    if (
        point_in_poly(x, y, body)
        or point_in_poly(x, y, fin)
        or point_in_poly(x, y, dorsal)
    ):
        # keep some spacing
        if all((x - nx) ** 2 + (y - ny) ** 2 > 52 ** 2 for nx, ny in nodes):
            nodes.append((x, y))

# connect to nearest neighbours
links = Image.new("RGBA", (W, H), (0, 0, 0, 0))
ld = ImageDraw.Draw(links)
for i, (x, y) in enumerate(nodes):
    dists = []
    for j, (x2, y2) in enumerate(nodes):
        if i == j:
            continue
        d = math.hypot(x2 - x, y2 - y)
        if d < 210:
            dists.append((d, x2, y2))
    dists.sort()
    for d, x2, y2 in dists[:3]:
        a = int(90 * (1 - d / 210)) + 18
        ld.line([(x, y), (x2, y2)], fill=BLUE + (a,), width=1)

# a few brighter data paths along the spine
spine = catmull_rom(
    [
        (0.16, 0.49),
        (0.30, 0.46),
        (0.46, 0.45),
        (0.62, 0.47),
        (0.76, 0.49),
        (0.86, 0.49),
    ],
    20,
    False,
)
spine = to_canvas(spine, box)
for i in range(len(spine) - 1):
    ld.line([spine[i], spine[i + 1]], fill=CYAN + (120,), width=2)

links_glow = links.filter(ImageFilter.GaussianBlur(7))
img = Image.alpha_composite(img, links_glow)
img = Image.alpha_composite(img, links)

# nodes with glow
node_glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
nd = ImageDraw.Draw(node_glow)
for x, y in nodes:
    nd.ellipse([x - 7, y - 7, x + 7, y + 7], fill=CYAN + (40,))
node_glow = node_glow.filter(ImageFilter.GaussianBlur(9))
img = Image.alpha_composite(img, node_glow)

nodes_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
nld = ImageDraw.Draw(nodes_layer)
for x, y in nodes:
    r = 3
    nld.ellipse([x - r, y - r, x + r, y + r], fill=TEXT + (210,))
    nld.ellipse([x - 1, y - 1, x + 1, y + 1], fill=(255, 255, 255, 235))
img = Image.alpha_composite(img, nodes_layer)

# glowing eye
ex, ey = to_canvas([(0.155, 0.485)], box)[0]
eye_glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
ed = ImageDraw.Draw(eye_glow)
ed.ellipse([ex - 26, ey - 26, ex + 26, ey + 26], fill=CYAN + (90,))
eye_glow = eye_glow.filter(ImageFilter.GaussianBlur(14))
img = Image.alpha_composite(img, eye_glow)
ed2 = ImageDraw.Draw(img)
ed2.ellipse([ex - 5, ey - 5, ex + 5, ey + 5], fill=(220, 250, 255, 255))

# --- vignette + finishing -------------------------------------------------------

vignette = Image.new("L", (W, H), 0)
vd = ImageDraw.Draw(vignette)
vd.ellipse([-int(W * 0.15), -int(H * 0.20), W + int(W * 0.15), H + int(H * 0.20)], fill=255)
vignette = vignette.filter(ImageFilter.GaussianBlur(260))
black = Image.new("RGBA", (W, H), (0, 0, 0, 255))
black.putalpha(Image.eval(vignette, lambda v: int((255 - v) * 0.55)))
img = Image.alpha_composite(img, black)

# subtle top/bottom grade
grade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
gr = ImageDraw.Draw(grade)
for y in range(int(H * 0.18)):
    a = int(55 * (1 - y / (H * 0.18)))
    gr.line([(0, y), (W, y)], fill=(0, 0, 0, a))
for y in range(int(H * 0.82), H):
    a = int(70 * ((y - H * 0.82) / (H * 0.18)))
    gr.line([(0, y), (W, y)], fill=(0, 0, 0, a))
img = Image.alpha_composite(img, grade)

img = img.convert("RGB")
img.save(OUT, quality=92, optimize=True)
print("saved", OUT, img.size)
