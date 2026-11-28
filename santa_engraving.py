"""Engraved brass for Santa 01's teacup: generated colour, roughness/metal and normal maps.

The cup is polished brass with flowers and leaves engraved round its lower body on a stippled ground,
and a vine of small leaves along both faces of its strap handle. One square texture holds both:
rows below BAND_ROWS are the cup's band, tiling across (u wraps round the cup), and rows STRIP are
the handle's strip, tiling along the handle. Everything else is plain polished brass, so the plain
band under the rim and the strap's edges can sample it too. Arrays are rows from the bottom (v up).
"""
import math

import numpy as np

from santa_model import noise

TAU = math.tau
SIZE = 1024
BAND_ROWS = 832  # rows [0, BAND_ROWS): the cup's band, from the foot (v = 0) up to the lip
STRIP = (864, 992)  # rows holding the handle's strip, across the strap's width
POLISHED = (.82, .60, .24)  # linear colour of polished brass, as Santa's Polished_brass_edges


def engraving(top_row):
    """Groove depth (0..1) and the stippled-ground mask; the band's engraving stops near `top_row`."""
    W = H = SIZE
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    groove = np.zeros((H, W), np.float32)
    motif = np.zeros((H, W), bool)

    def windows(points, pad):
        """The canvas windows (with the u shift that wraps them) around a shape."""
        x0, x1 = min(p[0] for p in points) - pad, max(p[0] for p in points) + pad
        y0 = max(0, int(min(p[1] for p in points) - pad))
        y1 = min(H, int(max(p[1] for p in points) + pad) + 1)
        for shift in ((-W, 0, W) if y0 < y1 else ()):
            a, b = max(0, int(x0 + shift)), min(W, int(x1 + shift) + 1)
            if a < b:
                yield shift, slice(y0, y1), slice(a, b)

    def line(points, width):
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            ex, ey = bx - ax, by - ay
            length2 = max(ex * ex + ey * ey, 1e-9)
            for shift, sy, sx in windows(((ax, ay), (bx, by)), width + 1):
                px, py = xs[sy, sx] - shift, ys[sy, sx]
                t = np.clip(((px - ax) * ex + (py - ay) * ey) / length2, 0, 1)
                d = np.hypot(px - ax - t * ex, py - ay - t * ey)
                groove[sy, sx] = np.maximum(groove[sy, sx], np.clip(1 - (d / width) ** 2, 0, 1))

    def inside(points):
        edges = list(zip(points, points[1:] + points[:1]))
        for shift, sy, sx in windows(points, 1):
            px, py = xs[sy, sx] - shift, ys[sy, sx]
            mask = np.zeros(px.shape, bool)
            for (ax, ay), (bx, by) in edges:
                if ay != by:
                    mask ^= ((ay > py) != (by > py)) & (px < ax + (py - ay) * (bx - ax) / (by - ay))
            yield sy, sx, mask

    def fill(points):
        """A polished shape; it covers the lines drawn before it."""
        for sy, sx, mask in inside(points):
            motif[sy, sx] |= mask
            groove[sy, sx][mask] = 0

    def covered(points):
        total = hit = 0
        for sy, sx, mask in inside(points):
            total += mask.sum()
            hit += (mask & motif[sy, sx]).sum()
        return hit / max(total, 1)

    def bezier(a, c, b, n=32):
        return [((1 - t) ** 2 * a[0] + 2 * (1 - t) * t * c[0] + t * t * b[0],
                 (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * c[1] + t * t * b[1]) for t in np.linspace(0, 1, n)]

    def tangent(points, k):
        a, b = points[max(0, k - 1)], points[min(len(points) - 1, k + 1)]
        tx, ty = b[0] - a[0], b[1] - a[1]
        length = math.hypot(tx, ty) or 1
        return tx / length, ty / length

    def leaf(base, tip, bend, half_width, veins=5, w=1.7, max_cover=None):
        """A pointed leaf with a midrib and paired veins; skipped if drawn shapes cover > max_cover of it."""
        dx, dy = tip[0] - base[0], tip[1] - base[1]
        spine = bezier(base, ((base[0] + tip[0]) / 2 - dy * bend, (base[1] + tip[1]) / 2 + dx * bend), tip)
        n = len(spine)
        half = [half_width * math.sin(math.pi * (k / (n - 1)) ** .8) ** .9 for k in range(n)]
        left, right = [], []
        for k, (x, y) in enumerate(spine):
            tx, ty = tangent(spine, k)
            left.append((x - ty * half[k], y + tx * half[k]))
            right.append((x + ty * half[k], y - tx * half[k]))
        outline = left + right[::-1]
        if max_cover is not None and covered(outline) > max_cover:
            return
        fill(outline)
        line(outline + outline[:1], w)
        line(spine[2:-3], w * .85)
        for v in range(veins):
            k = int((v + 1) / (veins + 1) * (n - 1))
            (x, y), (tx, ty) = spine[k], tangent(spine, k)
            for side in (-1, 1):
                ex, ey = .55 * tx - side * .85 * ty, .55 * ty + side * .85 * tx
                reach = half[k] * .8
                line([(x, y), (x + ex * reach * .5 + tx * reach * .12, y + ey * reach * .5 + ty * reach * .12),
                      (x + ex * reach, y + ey * reach)], w * .7)

    def flower(cx, cy, radius, petals=11, turn=0.0):
        """Two rings of veined petals round a seeded disc."""
        for k in range(petals):
            c, s = math.cos(turn + TAU * k / petals), math.sin(turn + TAU * k / petals)
            leaf((cx + .30 * radius * c, cy + .30 * radius * s), (cx + radius * c, cy + radius * s),
                 .06, .21 * radius, veins=2)
        for k in range(7):
            c, s = math.cos(turn + TAU * (k + .5) / 7), math.sin(turn + TAU * (k + .5) / 7)
            leaf((cx + .10 * radius * c, cy + .10 * radius * s), (cx + .55 * radius * c, cy + .55 * radius * s),
                 .05, .18 * radius, veins=1)
        disc = [(cx + .16 * radius * math.cos(a), cy + .16 * radius * math.sin(a)) for a in np.linspace(0, TAU, 25)]
        fill(disc)
        line(disc, 1.6)
        for k in range(8):
            a, r = TAU * k / 8, .08 * radius
            line([(cx + r * math.cos(a) + 2.4 * math.cos(b), cy + r * math.sin(a) + 2.4 * math.sin(b))
                  for b in np.linspace(0, TAU, 9)], 1.2)

    def curl(cx, cy, radius, turn=0.0, sign=1, turns=1.5, w=1.6):
        line([(cx + radius * (1 - .8 * t) * math.cos(turn + sign * t * turns * TAU),
               cy + radius * (1 - .8 * t) * math.sin(turn + sign * t * turns * TAU)) for t in np.linspace(0, 1, 60)], w)

    # ---- the cup's band, one 90-degree repeat: flowers first, then leaves packed round them from large
    # to small (each may overlap what is already drawn by a little), then curling tendrils in the gaps.
    f = top_row / 600  # the layout is drawn for a 600-row engraved field
    rng = np.random.default_rng(5)
    # The stippled ground ends at a fine wavy line below the plain band at the rim; leaves drawn
    # later may reach over it.
    wave = top_row + 10 * np.sin(np.arange(W + 1) * (3 * TAU / W) + .5)
    line([(x, wave[x]) for x in range(0, W + 1, 8)], 1.7)
    line(bezier((430, 0), (330, 110 * f), (215, 190 * f), 24), 2.0)
    line(bezier((690, 0), (650, 150 * f), (700, 290 * f), 24), 2.0)
    flower(210, 315 * f, 122 * f, petals=11, turn=.2)
    flower(700, 385 * f, 92 * f, petals=9, turn=.6)
    flower(975, 150 * f, 60 * f, petals=8, turn=.1)
    for size in np.linspace(250, 60, 320) * f:
        x, y = rng.uniform(0, W), rng.uniform(15, top_row - 15)
        angle = math.pi / 2 + rng.uniform(-1.0, 1.0) if size > 150 * f else rng.uniform(0, TAU)
        tip = (x + size * math.cos(angle), y + size * math.sin(angle))
        if 0 <= tip[1] <= top_row + 30:
            leaf((x, y), tip, rng.uniform(-.24, .24), size * rng.uniform(.16, .22), veins=max(2, int(size / 34)),
                 max_cover=.14)
    taken = motif.copy()
    for _ in range(260):
        x, y, r = rng.uniform(0, W), rng.uniform(25, top_row - 25), rng.uniform(14, 30) * f
        ring = [(x + r * math.cos(a), y + r * math.sin(a)) for a in np.linspace(0, TAU, 13)[:-1]]
        if sum((mask & taken[sy, sx]).sum() for sy, sx, mask in inside(ring)) == 0:
            curl(x, y, r * .9, turn=rng.uniform(0, TAU), sign=rng.choice((-1, 1)))
            for sy, sx, mask in inside(ring):
                taken[sy, sx] |= mask
    field = (ys >= 12) & (ys <= wave[None, :W])
    line([(x, 7) for x in range(-8, W + 9, 16)], 1.8)  # a fine line where the engraving starts

    # ---- the handle's strip: a vine of small alternating leaves between two border lines
    s0, s1 = STRIP
    mid = (s0 + s1) / 2
    line([(x, s0 + 9) for x in range(-8, W + 9, 16)], 1.6)
    line([(x, s1 - 9) for x in range(-8, W + 9, 16)], 1.6)
    line([(x, mid + 7 * math.sin(x * TAU / 256)) for x in range(-8, W + 9, 8)], 1.5)
    for k in range(16):
        x = k * 64
        y = mid + 7 * math.sin(x * TAU / 256)
        leaf((x, y), (x + 50, y + (40 if k % 2 else -40)), .14 if k % 2 else -.14, 13, veins=2, w=1.4)
    field |= (ys >= s0 + 14) & (ys <= s1 - 14)
    return groove, field & ~motif


def maps(top_row, seed=11):
    """Linear colour, occlusion/roughness/metal and tangent normal maps for the engraved brass."""
    groove, ground = engraving(top_row)
    ground = ground.astype(np.float32)
    hatch = np.tanh(noise(SIZE, .7, 2.4, seed=seed))  # short vertical strokes of the stippling tool
    speck = np.tanh(noise(SIZE, 1.5, seed=seed + 1))
    shade = 1 - ground * (.26 + .07 * hatch) - .5 * groove
    color = np.array(POLISHED, np.float32)[None, None, :] * shade[:, :, None]
    color[:, :, 2] *= 1 - .18 * ground - .2 * groove  # a warmer, browner tone down in the cuts
    rough = .20 + ground * (.24 + .05 * speck) + .30 * groove
    occlusion = 1 - .10 * ground - .30 * groove
    orm = np.stack((occlusion, rough, np.ones_like(rough)), axis=-1)
    height = ground * (-.30 + .10 * hatch) - .9 * groove
    du = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) / 2  # wraps, like the band
    dv = np.gradient(height, axis=0)
    strength = 1.6
    normal = np.stack((-du * strength, -dv * strength, np.ones_like(du)), axis=-1)
    normal = normal / np.linalg.norm(normal, axis=-1, keepdims=True) * .5 + .5
    return color, orm, normal
