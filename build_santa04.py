"""Build the Landmark on Robson edition from the packed character made by build_santa01.py.

blender -b --factory-startup --python-exit-code 1 -P build_santa04.py -- previews
The optional directory receives front, lifted, tree and sign previews and the page poster.
"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import santa_kit as kit  # noqa: E402
from santa_kit import (TAU, aim_eyes, ball, bound, cord, flat, frame, hold, label, leaf, look,  # noqa: E402
                       material, place, profile, rigid, surface, textured, turn)

TREE = Vector((-.21, -.50, 1.28))     # tree axis at the foot of the foliage
LEAN = turn(-10, 'Y')                 # the tip leans out to Santa's right, clear of his face
GRIPS = Vector((0, -.04, .08))        # both gloves hug the lowest branches, either side of the axis
SPAN = .175
HEIGHT, WIDTH, DEPTH = .68, .25, .72  # foliage height, half-width and depth ratio (a slightly flat tree)
TIP = TREE + Vector((0, 0, HEIGHT))
kit.start(4, 'LandmarkOnRobson', 'photos/04 Landmark on Robson Santa.jpg', [
    ('tree', TREE + GRIPS, TREE + GRIPS + Vector((0, 0, .2)), 'root'),
])
rig = kit.rig

# A tileable needle swatch: short dark strokes over a mid green.
rng = np.random.default_rng(4)
y, x = np.mgrid[:128, :128] / 128
needles = np.zeros((128, 128))
for _ in range(900):
    cx, cy, a = rng.uniform(0, 1), rng.uniform(0, 1), rng.uniform(-.5, .5) + math.pi / 2 * rng.integers(0, 2)
    dx, dy = (x - cx + .5) % 1 - .5, (y - cy + .5) % 1 - .5
    along, across = dx * math.cos(a) + dy * math.sin(a), -dx * math.sin(a) + dy * math.cos(a)
    needles += np.exp(-(across / .006) ** 2) * (np.abs(along) < .05) * rng.uniform(.5, 1)
shade = np.clip(.55 + .35 * np.tanh(needles - .6), 0, 1)
fir = textured(material('Fir needles', '2F5E2A', .78, sheen=.25),
               shade[:, :, None] * np.array([.20, .40, .17]) + (1 - shade[:, :, None]) * np.array([.06, .16, .07]), .09)
fir_tips = material('Fresh fir tips', '4E8A3A', .7, sheen=.25)
bark = material('Spruce trunk', '5A3A22', .85)
red_bauble = material('Red glass bauble', 'C8102E', .12, coat=1)
green_bauble = material('Green glass bauble', '1E7B3A', .12, coat=1)
gold = material('Bauble caps', 'D9A441', .25, 1)
wire = material('Light wire', '1F3A1C', .6)
bulb = material('Warm fairy lights', 'FFD27A', .3, emit=6)
holly = material('Holly leaves', '1F5E2A', .35)
berry = material('Holly berries', 'B3121E', .25, coat=.6)
glow = material('Sign glow', 'FFE9B8', .4, emit=3.5)
brass_glow = material('Sign brass', 'E7B45A', .3, .6, emit=.6)
backing = material('Sign backing', '3A1A0E', .55)
outline = material('Sign lettering outline', '5A2810', .5)


def radius(z):
    """Foliage half-width at height z above the foot of the tree."""
    return WIDTH * max(.02, 1 - z / HEIGHT) ** .92


# ---------------------------------------------------------------- the little fir
rnd = random.Random(4)
with bound('tree'), frame(Matrix.Translation(TREE + GRIPS) @ LEAN.to_4x4() @ Matrix.Translation(-GRIPS)):
    profile([(-.10, .026, .026), (.02, .030, .030)], bark, n=12)
    tiers = 6
    for k in range(tiers):
        top = HEIGHT * (k + 1.25) / tiers if k < tiers - 1 else HEIGHT
        bottom = HEIGHT * (k - .15) / tiers if k else -.015
        rb, rt = radius(bottom) * 1.05, radius(top) * .55
        phase = rnd.uniform(0, TAU)
        lobes = 11 - k
        profile([(bottom - .025, rb * .88, rb * .88 * DEPTH), (bottom, rb, rb * DEPTH),
                 (bottom + .25 * (top - bottom), rb * .78 + rt * .22, (rb * .78 + rt * .22) * DEPTH),
                 (top, rt, rt * DEPTH)], fir, n=44,
                wobble=lambda a, z, p=phase, n=lobes: 1 + .13 * math.cos(n * a + p) + .06 * math.cos(2.7 * n * a))
    # Feathery sprig tips break up the silhouette of every tier.
    for _ in range(1100):
        z = HEIGHT * rnd.random() ** 1.15 * .97
        a = rnd.uniform(0, TAU)
        r = radius(z) * rnd.uniform(.85, 1.02)
        base = Vector((r * math.cos(a), r * DEPTH * math.sin(a), z))
        out = Vector((math.cos(a), math.sin(a) / DEPTH * .8, -.35)).normalized() * rnd.uniform(.03, .05)
        cord([base - out * .3, base + out * .5, base + out], .0045, fir_tips if rnd.random() < .4 else fir, [1, .7, .15],
             sides=4)
    # Fairy lights spiral up the tree on a fine wire.
    path, bulbs = [], []
    turns = 3.6
    for k in range(181):
        t = k / 180
        z = .03 + (HEIGHT - .09) * t
        a = -math.pi / 2 + TAU * turns * t
        r = radius(z) * 1.02 + .006
        path.append((r * math.cos(a), r * DEPTH * math.sin(a), z - .012 * math.sin(a * 2)))
        if k % 4 == 2:
            bulbs.append(path[-1])
    cord(path, .0016, wire, sides=4)
    for p in bulbs:
        ball(*p, .0085, bulb, 8, 4)
    # Baubles hang on the outside of the branches, most of them where Santa's guests can see.
    for k in range(17):
        z = .06 + (HEIGHT - .16) * ((k * .618) % 1)
        a = -math.pi / 2 + rnd.uniform(-1.6, 1.6) if k % 4 else rnd.uniform(0, TAU)
        r = radius(z) * 1.01 + .02
        c = Vector((r * math.cos(a), r * DEPTH * math.sin(a), z))
        size = rnd.uniform(.020, .027)
        ball(*c, size, red_bauble if k % 2 else green_bauble, 16, 8)
        with place(*c):
            profile([(size * .82, .0065, .0065), (size * 1.18, .0055, .0055)], gold, n=8)
    # Holly sprig with berries at the front of the lowest tier.
    hx, hz = .04, .09
    with place(hx, -radius(hz) * DEPTH - .012, hz, roll=-70):
        for a in (-50, 10, 65):
            with place(yaw=0, tilt=a):
                leaf(.055, .018, holly, fold=.35, curl=.1)
    for i in range(3):
        ball(hx - .01 + .011 * i, -radius(hz) * DEPTH - .02, hz + .006 * (i % 2), .0085, berry, 10, 5)

    # Brass bell finial and the glowing Landmark on Robson sign above the tip.
    with place(0, 0, HEIGHT - .03):
        profile([(0, .016, .016), (.02, .010, .010), (.035, .0055, .0055), (.06, .0055, .0055)], gold, n=16)
        profile([(.055, .020, .020), (.075, .026, .026), (.09, .015, .015), (.10, .004, .004)], gold, n=16)
    SIGN = Vector((-.07, -.03, HEIGHT + .22))
    with place(*SIGN, yaw=12):
        # Dark plaque with a polished rim; arch window with the building; two lines of glowing lettering.
        with place(roll=90):
            profile([(-.009, .175, .125), (.006, .175, .125)], backing, power=.55, n=48)
            profile([(.006, .178, .128), (.010, .170, .121)], brass_glow, power=.55, n=48, close=False,
                    two_sided=True)
        arch = [(.07 * math.cos(math.pi * k / 20), -.0125, .0 + .07 * math.sin(math.pi * k / 20)) for k in range(21)]
        cord(arch, .0035, brass_glow, sides=6)
        cord([(-.085, -.0125, 0), (.085, -.0125, 0)], .003, brass_glow, sides=6)
        # Landmark tower: a stepped tower with a spire between two lower blocks, lit by window bands.
        for x0, w, h in ((-.040, .017, .036), (.040, .017, .030), (0, .021, .056), (0, .011, .066)):
            surface([(x0 - w, -.0128, .004), (x0 + w, -.0128, .004), (x0 + w, -.0128, h), (x0 - w, -.0128, h)],
                    [(0, 1, 2, 3)], glow)
        for x0, w, h in ((-.040, .017, .036), (.040, .017, .030), (0, .021, .056)):
            for b in range(int((h - .006) / .010)):
                cord([(x0 - w * .7, -.0138, .010 + b * .010), (x0 + w * .7, -.0138, .010 + b * .010)], .0014, outline,
                     sides=4)
        cord([(0, -.0128, .066), (0, -.0128, .084)], .0016, brass_glow, sides=4)
        label('Landmark', glow, flat(0, -.0145, -.032), .25, bold=.045, outline=(outline, .05), step=.0011)
        label('on Robson', glow, flat(0, -.0145, -.085), .20, bold=.045, outline=(outline, .05), step=.0011)
    cord([(0, 0, HEIGHT + .06), SIGN + Vector((0, .01, -.12))], .004, gold, sides=6)


# ---------------------------------------------------------------- five-second loop
def pose_at(t):
    lift = .5 - .5 * math.cos(TAU * t)
    rock = turn(4 * math.sin(TAU * 2 * t), 'Y') @ turn(-3 * lift, 'X')
    centre = TREE + GRIPS + Vector((0, -.02, .05)) * lift
    rigid('tree', centre, rock)
    for side, sign in (('L', 1), ('R', -1)):
        hold(side, centre + rock @ LEAN @ Vector((sign * SPAN, 0, 0)), rock @ LEAN)
    sign_board = centre + rock @ LEAN @ (TIP - TREE - GRIPS + Vector((-.07, 0, .22)))
    look(sign_board, -math.radians(3) * lift, turn_share=.3)
    aim_eyes(sign_board)


kit.attach('Landmark on Robson props')
kit.bake('Santa04_Tree_Glow', 121, pose_at,
         ['tree', 'head', 'eye.L', 'eye.R'] + [f'{n}.{s}' for s in 'LR' for n in ('upper_arm', 'forearm', 'hand')])
FRONT = ((-.20, -6.1, 2.05), (-.06, -.03, 1.13), 74, (800, 900))
kit.finish('santa04', FRONT, [
    ('front', 1, FRONT),
    ('lift', 61, FRONT),
    ('tree', 1, ((-.55, -2.1, 1.75), (-.25, -.52, 1.62), 60, (640, 640))),
    ('sign', 1, ((-.55, -1.45, 2.15), (-.40, -.55, 2.12), 80, (640, 640))),
])
