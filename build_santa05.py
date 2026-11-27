"""Build the Mello edition from the base character made by build_santa_base.py.

blender -b --factory-startup --python-exit-code 1 -P build_santa05.py -- previews
The optional directory receives front, raise, bite, side, bitten, bun and sack previews and the page poster.
"""
import math
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mathutils import Matrix, Vector, Quaternion  # noqa: E402

import santa_kit as kit  # noqa: E402
from santa_kit import (TAU, aim_eyes, ball, bound, cord, ellipsoid, frame, hold, label, look,  # noqa: E402
                       material, place, profile, recolor, rigid, rings, surface, textured, turn)

BUN = Vector((0.0, -.50, 1.33))      # rest centre of the doughnut: held low, in front of his chest
RX, RY, RZ = .15, .135, .13
TOP = Vector((.55, 0, .835))          # the bite comes off the top of the doughnut, on the side away from the cream
BITE = .080                           # depth of the bite's floor along TOP
GRIP = .10                            # each glove wraps the lower side of the doughnut
SACK = Vector((.74, .14, 0))
# Like the real Mello doughnut (photos/mello.jpg), it is split like a book down its front-left, from
# the top-left to the underside, and the two halves are opened SPLIT apart around a line of whipped
# cream. The cut runs pole to pole along AXIS and opens out along CUT; each half's fried face points
# along +FRY (the right half, which the bite comes off) or -FRY (the left half).
AXIS = Vector((-.34, 0, .94)).normalized()
CUT = (Vector((-.62, -.78, 0)) - AXIS * Vector((-.62, -.78, 0)).dot(AXIS)).normalized()
FRY = AXIS.cross(CUT)
SPLIT = math.radians(36)
kit.start(5, 'Mello', 'photos/05 Mello Santa.jpg', [
    ('bun', BUN, BUN + Vector((0, 0, .2)), 'root'),
    ('mello_jaw', Vector((0, -.15, 1.644)), Vector((0, -.15, 1.704)), 'head'),
    # The piece he bites off: part of the bun until the bite, then gone into his mouth.
    ('chunk', BUN + TOP * BITE, BUN + TOP * (BITE + .1), 'bun'),
])
rig = kit.rig

crust = material('Sugared doughnut crust', '7A2507', .6)
crumb = material('Soft brioche crumb', 'F2E2B0', .85)
cream = material('Whipped cream', 'FFF8EE', .5, sheen=.3)
berry = material('Strawberry', 'D21C27', .3, coat=.7)
flesh = material('Strawberry flesh', 'EC6A60', .35, coat=.4)
seeds = material('Strawberry seeds', 'D9B23F', .4)
velvet = recolor('Crimson_velvet', 'Mello mustard velvet', 'A6961A', .36)
rope = material('Jute rope', 'C79A55', .85)
white = material('Mello white', 'FFFDF4', .4)
yellow = material('Mello yellow', 'F7C824', .4)
orange = material('Mello orange', 'E5871B', .45)
olive = material('Mello olive shadow', '6B5C12', .5)
red_paper = material('Red gift wrap', 'B8152A', .35, sheen=.2)
green_paper = material('Green gift wrap', '1F7A3E', .35, sheen=.2)
silver_paper = material('Silver gift wrap', 'E4E6EA', .3, .3)
gold_ribbon = material('Gold ribbon', 'E0A93A', .25, .7)
red_ribbon = material('Red ribbon', 'C7182C', .3, sheen=.4)
ginger = material('Gingerbread', 'A3602A', .7)
icing = material('Royal icing', 'FFFFFF', .45)
plush = material('Teddy plush', '8A5A32', .9, sheen=.5)
button = material('Black button eyes', '120C08', .2)


# ---------------------------------------------------------------- the Mello doughnut, with a bite
def direction(b, g):
    """Unit vector at angle b round AXIS from the cut (towards +FRY) and g along it (+-pi/2 at its ends)."""
    return math.cos(g) * (math.cos(b) * CUT + math.sin(b) * FRY) + math.sin(g) * AXIS


def crust_point(v):
    """The whole doughnut's surface along unit vector v: plump, flatter underneath, gently lumpy."""
    r = 1 / math.sqrt((v.x / RX) ** 2 + (v.y / RY) ** 2 + (v.z / RZ) ** 2)
    r *= 1 + .02 * math.cos(3 * math.atan2(v.y, v.x) + .4) * (1 - v.z * v.z) + .01 * math.sin(4 * v.x + 3 * v.y + 5 * v.z)
    p = v * r
    if p.z < -.7 * RZ:
        p.z = -.7 * RZ - .4 * (-.7 * RZ - p.z)
    return p


def opened(p, b):
    """Swing point p, at angle b from the cut, with its half: the cut opens SPLIT wide and the
    swing fades to nothing at the back, where the halves are still joined."""
    return Matrix.Rotation(SPLIT / 2 * math.cos(b / 2), 3, AXIS) @ p


SIDE = TOP.cross(Vector((0, 1, 0))).normalized()   # with UP, spans the floor of the bite
UP = SIDE.cross(TOP)


def bitten(p):
    """Carve a scalloped bite down from the top; returns the point and whether it was carved."""
    u, v = p.dot(SIDE), p.dot(UP)
    wall = BITE + .045 * ((u / RX) ** 2 + (v / RY) ** 2) + .006 * abs(math.sin(5 * math.atan2(v, u)))
    depth = p.dot(TOP)
    if depth > wall:
        return p - TOP * (depth - wall), True
    return p, False


def blend(x, stops):
    """sRGB colours for values x, interpolated between (value, hex) stops."""
    at = [s for s, _ in stops]
    rgb = [[int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)] for _, h in stops]
    return np.stack([np.interp(x, at, [c[k] for c in rgb]) for k in range(3)], axis=-1)


def crust_paint(width=2048, seed=5):
    """The crust's colour on its (round the cut, along the cut) UVs: darkest mid-face, where it fried
    longest, golden towards the pale ring the cut runs along, mottled, then rolled in granulated sugar."""
    height = width // 2
    rnd = np.random.default_rng(seed)
    b = (np.arange(width) + .5) / width * TAU
    g = (np.arange(height) + .5) / height * math.pi - math.pi / 2
    cb, sb, cg, sg = np.cos(b)[None, :], np.sin(b)[None, :], np.cos(g)[:, None], np.sin(g)[:, None]
    d = [cg * cb * c + cg * sb * f + sg * a for c, f, a in zip(CUT, FRY, AXIS)]

    def noise(scale, count=14):
        waves, phases = rnd.normal(0, scale, (count, 3)), rnd.uniform(0, TAU, count)
        return sum(np.sin(k[0] * d[0] + k[1] * d[1] + k[2] * d[2] + p) for k, p in zip(waves, phases)) / math.sqrt(count / 2)

    face = np.abs(cg * sb)                     # 0 on the ring, 1 in the middle of a fried face
    img = blend(np.clip(face + .05 * noise(4), 0, 1), [(0, 'D0904A'), (.08, 'B4561E'), (.2, '93340C'), (.4, '7A2507'),
                                                     (.7, '6A1D05'), (1, '6A1D05')])
    img *= (1 + .05 * noise(5) + .05 * noise(14))[:, :, None]
    glow = np.clip(.14 * noise(12), 0, None)[:, :, None]   # patches that fried a brighter orange
    img = img * (1 - glow) + blend(glow[:, :, 0], [(0, 'B8501A'), (1, 'B8501A')]) * glow
    sugar = np.array([.95, .92, .89])
    texel = math.pi * .138 / height            # metres per texel along the cut
    density = np.clip(.6 + .35 * noise(10), .15, 1)         # the sugar clings in patches
    count = 90000
    rows = (np.arcsin(rnd.uniform(-1, 1, count)) + math.pi / 2) / math.pi * height
    for cu, cv, rv, k, e, t, keep in zip(rnd.uniform(0, width, count), rows, rnd.uniform(.0004, .001, count) / texel,
                                         rnd.uniform(.35, .9, count), rnd.uniform(1, 1.7, count),
                                         rnd.uniform(0, math.pi, count), rnd.uniform(0, 1, count)):
        if keep > density[min(int(cv), height - 1), int(cu) % width]:
            continue
        squeeze = max(math.cos(g[int(min(cv, height - 1))]), .02)
        ru = min(rv * e / squeeze, width / 2)
        jj = np.arange(max(0, int(cv - rv * e - 1)), min(height, int(cv + rv * e + 2)))
        ii = np.arange(int(cu - ru - 1), int(cu + ru + 2))
        du = (ii[None, :] + .5 - cu) * np.maximum(np.cos(g[jj]), .02)[:, None]
        dv = jj[:, None] + .5 - cv
        x, y = du * math.cos(t) + dv * math.sin(t), dv * math.cos(t) - du * math.sin(t)
        alpha = (np.clip((1 - ((x / e) ** 2 + y ** 2) / rv ** 2) * 2.5, 0, 1) * k)[:, :, None]
        cols = ii % width
        img[jj[:, None], cols[None, :]] = img[jj[:, None], cols[None, :]] * (1 - alpha) + sugar * alpha
    count = 100000                             # and the fine sugar dust between the crystals
    jj = np.clip(((np.arcsin(rnd.uniform(-1, 1, count)) + math.pi / 2) / math.pi * height).astype(int), 0, height - 1)
    ii = rnd.integers(0, width, count)
    alpha = rnd.uniform(.15, .4, count)[:, None]
    img[jj, ii] = img[jj, ii] * (1 - alpha) + sugar * alpha
    return np.clip(img, 0, 1)


def crumb_swatch(size=256, seed=7):
    """Tileable soft brioche crumb: pale, with shadowed air pockets lit along their upper rims."""
    rnd = np.random.default_rng(seed)
    y, x = np.mgrid[0:size, 0:size].astype(float)
    shade = np.ones((size, size))
    for _ in range(160):
        cx, cy = rnd.uniform(0, size, 2)
        r, e = rnd.uniform(2, 8), rnd.uniform(1, 1.8)
        dx, dy = (x - cx + size / 2) % size - size / 2, (y - cy + size / 2) % size - size / 2
        dist = np.sqrt((dx / e) ** 2 + dy ** 2) / r
        shade -= .16 * np.clip(1 - dist, 0, 1) ** .6
        shade += .06 * np.clip(1 - np.abs(dist - 1.15) * 4, 0, 1) * (dy > 0)
    shade += .03 * rnd.standard_normal((size, size))
    return np.clip(np.array([.95, .89, .69])[None, None, :] * shade[:, :, None], 0, 1)


# Half a hulled strawberry standing tip up: (height, half-width) up its outline.
BERRY = [(0, .030), (.005, .036), (.012, .039), (.025, .036), (.042, .028), (.060, .019), (.076, .010), (.090, .002)]
BERRY_W = .038


def berry_width(z):
    return float(np.interp(z, [h for h, _ in BERRY], [w for _, w in BERRY]))


def berry_paint(size=256):
    """The cut face (UVs span the outline's width and height): a pale core and pale veins fanning out
    through rosy flesh to a deep red rim with its seeds."""
    v, u = (np.mgrid[0:size, 0:size] + .5) / size
    top = BERRY[-1][0]
    w = np.interp(v * top, [h for h, _ in BERRY], [w for _, w in BERRY])
    r = np.abs((u - .5) * 2 * BERRY_W) / np.maximum(w, 1e-4)
    core = r / (.75 + .5 * v)                  # the pith narrows towards the tip
    img = blend(np.clip(core, 0, 1.3), [(0, 'FBE2D8'), (.25, 'F7C3B6'), (.45, 'F08E80'), (.65, 'E65A4E'), (.85, 'D8312F'),
                                        (.95, 'C41B22'), (1.3, 'C41B22')])
    veins = (.5 + .5 * np.cos(TAU * (7 * v - 3 * r))) ** 6 * np.clip((r - .12) * 6, 0, 1) * np.clip((.86 - r) * 6, 0, 1)
    img += (np.array([.98, .82, .79]) - img) * .3 * veins[:, :, None]
    for k in range(1, 9):                      # seeds sitting in the rim
        z = top * (k + .3 * (k % 2)) / 9.5
        for side in (-1, 1):
            cu, cv = .5 + side * .93 * berry_width(z) / (2 * BERRY_W), z / top
            dot = np.clip(1 - np.hypot((u - cu) * size / 2.6, (v - cv) * size / 2.6), 0, 1)[:, :, None]
            img += (np.array([.89, .75, .35]) - img) * dot
    return np.clip(img, 0, 1)


def piped(path, radius, mat, ridges=10, depth=.04, sides=24):
    """A rope of cream piped through a star tip along `path`, `radius(t)` thick for t in 0..1."""
    points = [Vector(p) for p in path]
    rows, u = [], None
    for i, p in enumerate(points):
        axis = (points[min(i + 1, len(points) - 1)] - points[max(0, i - 1)]).normalized()
        if u is None:
            u = axis.cross(Vector((0, 0, 1)) if abs(axis.z) < .95 else Vector((1, 0, 0))).normalized()
        else:
            u = (u - axis * u.dot(axis)).normalized()   # carried along the rope so it never twists
        v = axis.cross(u)
        r = radius(i / (len(points) - 1))
        rows.append([p + r * (1 + depth * math.cos(ridges * a)) * (u * math.cos(a) + v * math.sin(a))
                     for a in (TAU * s / sides for s in range(sides))])
    rings(rows, mat)


def strawberry_half():
    """Half a strawberry along +Z, its glossy skin behind (+Y) and its cut face towards -Y."""
    n = 12
    rows = [[(w * math.cos(a), .9 * w * math.sin(a), z) for a in (math.pi * k / n for k in range(n + 1))]
            for z, w in BERRY]
    surface([p for row in rows for p in row], [(j * (n + 1) + k, j * (n + 1) + k + 1, (j + 1) * (n + 1) + k + 1,
                                                (j + 1) * (n + 1) + k)
                                               for j in range(len(BERRY) - 1) for k in range(n)], berry, rounded=True)
    cols, top = 10, BERRY[-1][0]
    points = [(-w + 2 * w * k / cols, 0, z) for z, w in BERRY for k in range(cols + 1)]
    surface(points, [(j * (cols + 1) + k, j * (cols + 1) + k + 1, (j + 1) * (cols + 1) + k + 1, (j + 1) * (cols + 1) + k)
                     for j in range(len(BERRY) - 1) for k in range(cols)], flesh,
            uv=[(x / (2 * BERRY_W) + .5, z / top) for x, _, z in points])
    for k in range(16):                        # seeds on the skin round the edges of the cut
        z = .010 + .070 * ((k * .618) % 1)
        w = berry_width(z) + .0004
        a = (.25 + .15 * (k % 3)) if k % 2 else math.pi - .25 - .15 * (k % 3)
        ball(w * math.cos(a), .9 * w * math.sin(a), z, .0015, seeds, 4, 2)


textured(crust, crust_paint(), None)    # the crust and the strawberry's cut face are laid out by their own UVs
textured(crumb, crumb_swatch(), .07)
textured(flesh, berry_paint(), None)
N, M = 72, 36                          # crust columns round AXIS (open at the cut) and rows along it
with bound('bun'), place(*BUN):
    whole, grid, carved, uv = [], [], [], []
    for j in range(M + 1):
        g = -math.pi / 2 + math.pi * j / M
        row = [opened(crust_point(direction(b, g)), b) for b in (TAU * i / N for i in range(N + 1))]
        whole.append(row)
        row = [bitten(p) for p in row]
        grid.append([p for p, _ in row])
        carved.append([c for _, c in row])
        uv.extend((i / N, j / M) for i in range(N + 1))
    # Partition the intact shell exactly at the bite rim. Mixed faces belong
    # only to the removable cap, not to an overlapping exterior crust.
    outside, piece = [], []
    for j in range(M):
        for i in range(N):
            quad = [(j, i), (j, i + 1), (j + 1, i + 1), (j + 1, i)]
            polygon = tuple(a * (N + 1) + b for a, b in quad)
            (piece if any(carved[a][b] for a, b in quad) else outside).append(polygon)
    surface([p for row in whole for p in row], outside, crust, rounded=True, uv=uv)
    surface([p for row in grid for p in row], piece, crumb)
    with bound('chunk'):
        surface([p for row in whole for p in row], piece, crust, rounded=True, uv=uv)
    # The two cut faces, flat crumb from the spine out to each lip.
    faces = []
    for i, flip in ((0, False), (N, True)):
        rows = [[AXIS * p.dot(AXIS) + (p - AXIS * p.dot(AXIS)) * k / 6 for k in range(7)] for p in (r[i] for r in whole)]
        polys = [(j * 7 + k, j * 7 + k + 1, (j + 1) * 7 + k + 1, (j + 1) * 7 + k) for j in range(M) for k in range(6)]
        surface([p for row in rows for p in row], [q[::-1] for q in polys] if flip else polys, crumb)
        faces += [p for row in rows for p in row]
    assert not any(bitten(p)[1] for p in faces), 'the bite reaches the cut'
    # The bite opens into the cream filling: a soft, lumpy pool of cream fills the hollow, deepest in
    # the middle, leaving a band of crumb round the rim. It stays below the crust of the piece he bites
    # off, so it is hidden until he takes it.
    pool = []
    for j, row in enumerate(grid):
        for i, p in enumerate(row):
            deep = (whole[j][i] - p).length              # how far the bite carved this point down
            ripple = 1 + .25 * math.sin(70 * p.dot(SIDE) + 1) * math.sin(60 * p.dot(UP))
            pool.append(p + TOP * (.85 * max(0, deep - .01) * ripple - .002))
    surface(pool, piece, cream, rounded=True)
    # Whipped cream piped back and forth down the cut, so it bulges out between the lips in stacked
    # soft folds. It leans on the right half, so the left half's crumb shows beside it, as in the photo.
    lean = Matrix.Rotation(SPLIT * .2, 3, AXIS)
    for k in range(17):
        g = -.7 + 1.85 * k / 16
        out, across = lean @ direction(0, g), lean @ FRY
        r = crust_point(direction(0, g)).length
        gap = .9 * r * math.cos(g) * math.sin(SPLIT / 2)    # half the gap at the fold's middle
        swing = .18 * gap * (1 if k % 2 else -1)
        with frame(Matrix.Translation(out * .9 * r + across * swing)
                   @ Matrix((out, across, out.cross(across))).transposed().to_4x4()):
            ellipsoid(0, 0, 0, .15 * r * math.cos(g) + .009, gap + .004, .021, cream, 20, 10,
                      wobble=lambda a, z, k=k: 1 + .05 * math.cos(3 * a + k) + .03 * math.cos(8 * a + 2 * k))
    # A piped swirl over the top of the cut, crowned with half a strawberry.
    base = crust_point(direction(0, 1.12)) * .97
    spin = (Vector((0, 0, 1)) * .55 + direction(0, 1.12) * .45).normalized().to_track_quat('Z', 'Y').to_matrix()
    with frame(Matrix.Translation(base) @ spin.to_4x4()):
        turns, steps = 2.4, 72
        path = [(.046 * (1 - .8 * s) * math.cos(TAU * turns * s), .046 * (1 - .8 * s) * math.sin(TAU * turns * s),
                 .058 * s) for s in (k / steps for k in range(steps + 1))]
        end = TAU * turns
        path += [(.006 * math.cos(end + .6), .006 * math.sin(end + .6), .066), (.002, 0, .072)]
        piped(path, lambda t: .024 * (1 - .5 * t) * min(1, .45 + t / .1) * (1 if t < .93 else max(.12, (1 - t) / .07)),
              cream)
        profile([(0, .046, .046), (.03, .032, .032), (.055, .014, .014), (.066, .002, .002)], cream, n=24)
    with place(*(base + spin @ Vector((0, -.014, .052))), yaw=-8, tilt=-16):
        strawberry_half()

# ---------------------------------------------------------------- mustard velvet Mello sack
rnd = random.Random(55)
bulges = [rnd.uniform(0, TAU) for _ in range(3)]


def sack_radius(z):
    levels = [(.004, .12), (.02, .24), (.08, .30), (.18, .32), (.30, .30), (.40, .25), (.47, .195), (.52, .175),
              (.57, .21), (.62, .25), (.65, .26)]
    for (z0, r0), (z1, r1) in zip(levels, levels[1:]):
        if z <= z1:
            return r0 + (r1 - r0) * (z - z0) / (z1 - z0)
    return levels[-1][1]


def slump(a, z):
    return 1 + .06 * math.sin(3 * a + bulges[0]) * math.sin(math.pi * min(1, z / .5)) + .035 * math.cos(5 * a + bulges[1])


def on_sack(z, lift=.006):
    """Lettering mapper that follows the slumped velvet around the front of the sack."""
    def mapper(u, v, depth=0):
        zz = z + v
        r = sack_radius(zz)
        a = -math.pi / 2 + u / (r * .95)
        k = slump(a, zz)
        normal = Vector((math.cos(a) * .9, math.sin(a), 0)).normalized()
        p = Vector((k * r * math.cos(a), k * r * .9 * math.sin(a), zz))
        return p + normal * (lift - depth)
    return mapper


def box(x, y, z, w, d, h, paper, ribbon, yaw, tilt):
    with place(x, y, z, yaw=yaw, tilt=tilt):
        profile([(-h, w, d), (h, w, d)], paper, power=.14, n=24)
        profile([(-h - .002, w + .002, .011), (h + .002, w + .002, .011)], ribbon, power=.14, n=24)
        profile([(-h - .002, .011, d + .002), (h + .002, .011, d + .002)], ribbon, power=.14, n=24)
        for side in (-1, 1):
            cord([(0, 0, h), (side * .030, -.012, h + .028), (side * .052, 0, h + .022), (side * .030, .012, h + .010),
                  (0, 0, h)], .007, ribbon, [.6, 1, 1, 1, .6], sides=6)
        ball(0, 0, h + .006, .011, ribbon, 10, 5)


with place(*SACK, yaw=-18):
    profile([(z, sack_radius(z), sack_radius(z) * .9) for z in
             (.004, .02, .08, .18, .30, .40, .47, .52, .57, .62, .65)], velvet, n=44, close=False, wobble=slump,
            two_sided=True)
    # Jute rope twisted twice around the gathered neck, knotted at the front with loose ends.
    for strand in (0, math.pi):
        cord([(.183 * math.cos(TAU * k / 48) * (1 + .03 * math.cos(6 * TAU * k / 48 + strand)),
               .165 * math.sin(TAU * k / 48) * (1 + .03 * math.cos(6 * TAU * k / 48 + strand)),
               .52 + .006 * math.sin(6 * TAU * k / 48 + strand)) for k in range(49)], .0085, rope, sides=6)
    ball(.06, -.172, .515, .022, rope, 10, 6)
    for dx, end in ((.01, (-.005, -.21, .38)), (.04, (.10, -.215, .40))):
        cord([(.06, -.176, .51), (.06 + dx, -.205, .46), end], .008, rope, [1, 1, .7], sides=6)
    label('mello', white, on_sack(.23), .36, bold=.03,
          outline=[(yellow, .045, 0, 0), (orange, .07, .004, -.007), (olive, .09, .009, -.014)], step=.0022)
    # Treats peeking out of the open sack.
    box(-.07, .03, .69, .085, .075, .07, red_paper, gold_ribbon, 20, -12)
    box(.11, .05, .67, .07, .065, .06, green_paper, red_ribbon, -15, 14)
    box(.03, -.09, .62, .06, .055, .05, silver_paper, gold_ribbon, 35, 6)
    with place(-.15, -.10, .60, roll=-18, tilt=10):
        # Gingerbread figure: flat cookie with piped icing.
        ellipsoid(0, 0, .085, .042, .014, .040, ginger, 16, 8)
        ellipsoid(0, 0, .015, .040, .014, .055, ginger, 16, 8)
        for sx in (-1, 1):
            cord([(sx * .03, 0, .04), (sx * .07, 0, .06)], .014, ginger)
        for x, z in ((-.014, .095), (.014, .095)):
            ball(x, -.013, z, .005, icing, 8, 4)
        cord([(-.016 + .032 * k / 6, -.014, .072 - .008 * math.sin(math.pi * k / 6)) for k in range(7)], .0022, icing,
             sides=4)
        for z in (.03, .005):
            ball(0, -.014, z, .006, red_ribbon, 8, 4)
    with place(.16, -.08, .64, yaw=-25):
        ball(0, 0, 0, .055, plush, 16, 8)
        for sx in (-1, 1):
            ball(sx * .042, .005, .042, .020, plush, 10, 5)
            ball(sx * .020, -.048, .012, .0065, button, 8, 4)
        ellipsoid(0, -.050, -.010, .022, .016, .017, material('Teddy muzzle', 'C9A274', .9), 12, 6)
        ball(0, -.066, -.004, .0065, button, 8, 4)


# ---------------------------------------------------------------- ten-second loop
CAMERA = Vector((-.05, -3.2, 1.6))
DURATION = 10.0
FRAMES = 241
LIP = Vector((0, -.205, 1.600))
MOUTH = Vector((0, -.15, 1.625))
LOW = turn(8, 'X')
# Preserve the resting hand alignment: only a small backward pitch.
HIGH = turn(-4, 'X')
# Use the actual outer crust rather than an approximate radial distance.
# Contact the inner portion of the actual removable crust, rather than its
# furthest lateral point. This keeps the two-handed lift closer to midline.
contact_candidates = [p for row in whole for p in row
                      if bitten(p)[1] and p.dot(TOP) > BITE + .008
                      and abs(p.x) < .085]
# Use the rear-facing edge of the existing bite cap (towards Santa),
# not its front/top centre. The pastry need not enter his beard.
CONTACT = max(contact_candidates, key=lambda p: p.y - .35*abs(p.x-.025)
              + .15*p.z) if contact_candidates else max(
                  (p for row in whole for p in row), key=lambda p: p.dot(TOP))
kit.santa_motion.BODY_TILT_DEG = 4.0
kit.santa_motion.CLOTHING_SWAY_DEG = 4.5
kit.santa_motion.FOOT_ADJUST_DEG = 1.25
kit.santa_motion.HAT_FOLLOW_DEG = 4.0


def ease(t, a, b):
    u = max(0., min(1., (t-a)/(b-a)))
    return u**3 * (10 + u * (-15 + 6*u))


def pulse(t, a, b, c, d):
    return ease(t,a,b) * (1-ease(t,c,d))


def head_deform():
    head = rig.pose.bones['head']
    return head.matrix @ rig.data.bones['head'].matrix_local.inverted()


def reachable(centre, spin):
    constraints = []
    for side, sign in (('L',1),('R',-1)):
        upper = rig.data.bones['upper_arm.'+side]
        fore = rig.data.bones['forearm.'+side]
        offset = spin @ (Vector((sign*GRIP,-.01,-.055))-kit.GRIP[side])
        constraints.append((kit.attached(upper.name)-offset, upper.length+fore.length-.012))
    # Solve the two arm constraints in a constant-depth plane. Adjust
    # height/lateral position first, never drag the bun toward the chest
    # merely to achieve the requested height.
    for depth in (centre.y, centre.y+.005, centre.y+.010, centre.y+.015):
        disks = []
        for anchor, radius in constraints:
            r2 = radius*radius - (depth-anchor.y)**2
            if r2 <= 0:
                break
            disks.append((Vector((anchor.x,anchor.z)),math.sqrt(r2)))
        if len(disks) != 2:
            continue
        if (disks[0][0]-disks[1][0]).length > disks[0][1]+disks[1][1]:
            continue
        q = Vector((centre.x,centre.z))
        for _ in range(200):
            for anchor,radius in disks:
                delta = q-anchor
                if delta.length > radius:
                    q = anchor+delta.normalized()*radius
            if all((q-anchor).length <= radius+.00001 for anchor,radius in disks):
                return Vector((q.x,depth,q.y))
    # If the rig cannot reach the selected depth, use the safe original
    # reach solver and report the exceptional frame rather than break grips.
    print('[Mello] fixed-depth reach unavailable; using safe reach',flush=True)
    for _ in range(100):
        for anchor, radius in constraints:
            delta = centre-anchor
            if delta.length > radius:
                centre = anchor+delta.normalized()*radius
        if all((centre-anchor).length <= radius+.00001 for anchor,radius in constraints):
            break
    return centre


def bind_mouth():
    # The shared character has a sculpted open smile, not a jaw rig.
    # Add a local lower-mouth control only to this edition. Keep teeth,
    # upper lip, nose and moustache on the original head bone.
    mesh = kit.santa
    head = mesh.vertex_groups['head']
    jaw = mesh.vertex_groups.new(name='mello_jaw')
    weights = {}
    for face in mesh.data.polygons:
        mat = mesh.data.materials[face.material_index]
        if not mat or mat.name not in ('Warm_lips', 'Laughing_mouth', 'Tongue', 'Laughing_face_skin'):
            continue
        for i in face.vertices:
            v = mesh.data.vertices[i]
            x,y,z = v.co
            if abs(x) > .085 or y > -.10 or not 1.565 < z < 1.644:
                continue
            w = ease(1.644-z, .002, .037) * (1-ease(abs(x),.035,.080))
            if mat.name == 'Laughing_face_skin':
                w *= .25
            weights[i] = max(weights.get(i,0.),w)
    count = 0
    for i,w in weights.items():
        try:
            original = head.weight(i)
        except RuntimeError:
            continue
        if original < .99 or w < .001:
            continue
        jaw.add([i],original*w,'REPLACE')
        head.add([i],original*(1-w),'REPLACE')
        count += 1
    print('[Mello] lower-mouth weighted vertices:',count,flush=True)


# The bake evaluates frames sequentially. A bite is permitted only once
# the actual, reach-limited pastry surface is close to the mouth.
bite_start = None
closest_contact = float('inf')


def pose_at(loop):
    global bite_start, closest_contact
    t = loop * DURATION
    if t == 0:
        bite_start = None
        closest_contact = float('inf')
    # Anticipation: eyes and head lead the lift; the elbows follow.
    lift = pulse(t,.50,2.30,3.60,5.10)
    meet = pulse(t,1.85,2.85,3.60,4.40)
    inspect = pulse(t,.12,.80,3.95,5.70)
    anticipation = pulse(t,.12,.55,.72,1.35)
    # A few small, uneven chewing impulses instead of mechanical nodding.
    chew = sum(amplitude * pulse(t,a,a+.12,a+.17,b) for a,b,amplitude in (
        (3.48,3.86,1.0),(3.97,4.40,.78),(4.51,4.99,.55),
        (5.10,5.65,.34)))
    satisfied = pulse(t,5.85,6.18,6.32,6.85)
    phase = TAU*loop
    chest = rig.pose.bones['chest']
    axis = chest.bone.matrix_local.to_3x3().inverted() @ Vector((1,0,0))
    # Keep feet planted through the shared idle system; lean in gently to eat.
    chest.rotation_quaternion = chest.rotation_quaternion @ Quaternion(
        axis.normalized(),math.radians(.7*anticipation+1.0*lift+4.0*meet+.25*chew
                     + .45*math.sin(2*phase)*(1-.75*meet)))
    kit.bpy.context.view_layer.update()
    follow = (chest.matrix @ chest.bone.matrix_local.inverted() @ BUN - BUN)*.65
    low = BUN + Vector((follow.x, max(-.015,min(.005,follow.y)),follow.z)) + Vector((.008*math.sin(phase)*(1-.85*meet),0,.006*math.sin(2*phase)*(1-.75*meet)))
    # Preserve the wrist fix: no yaw or roll, only the existing small pitch.
    spin = LOW.to_quaternion().slerp(HIGH.to_quaternion(),meet).to_matrix()
    # Look at the rising pastry, not its stationary chest-level location.
    # Estimate the visible pastry centre without introducing a head/hand feedback loop.
    raised = Vector((low.x, -.49, 1.49))
    visual_bun = low.lerp(raised,lift)
    target = CAMERA.lerp(visual_bun + Vector((0,0,.05)),.85*inspect)
    look(target,math.radians(5*meet + .22*chew + .9*satisfied),turn_share=.45)
    eye_inspect = pulse(t,.04,.55,3.95,5.45)
    aim_eyes(CAMERA.lerp(visual_bun + Vector((0,0,.05)),.95*eye_inspect))
    kit.bpy.context.view_layer.update()
    lip = head_deform() @ LIP
    # Explicit upward path, independent of the lip depth. Only a tiny
    # inward movement is allowed at the very top, after clearing the chest.
    near = Vector((low.x, -.49 + .025*meet, lip.z - (spin @ CONTACT).z))
    desired = low.lerp(near,lift) + Vector((0,-.012,.012)) * (4*lift*(1-lift))
    centre = reachable(desired,spin)
    # Let the head meet the reachable bun, without changing wrist orientation.
    contact = centre + spin @ CONTACT
    gap = contact - lip
    if meet > 0 and gap.length > .001:
        head = rig.pose.bones['head']
        shift = Vector((max(-.025,min(.025,gap.x)),
                        max(-.080,min(0.,gap.y)),
                        max(-.035,min(.025,gap.z)))) * meet
        matrix = head.matrix.copy()
        matrix.translation += shift
        head.matrix = matrix
        kit.bpy.context.view_layer.update()
    lip = head_deform() @ LIP
    distance = (contact-lip).length
    if 2.85 <= t <= 3.48:
        closest_contact = min(closest_contact,distance)
        if bite_start is None and t >= 3.0 and distance <= .025:
            bite_start = t
            print('[Mello] contact at %.3fs, gap %.3fm' % (t,distance),flush=True)
    # Preserve the eating sequence even if the contact tolerance is missed.
    # The fallback occurs at the held bite pose, before the arms lower.
    if bite_start is None and t >= 3.30:
        bite_start = t
        print('[Mello] Timed bite fallback; nearest contact %.3fm' % closest_contact,flush=True)
    rigid('bun',centre,spin)
    on_bun = centre + spin @ (TOP*BITE)
    gone = ease(t,bite_start,bite_start+.18) if bite_start is not None else 0.
    if loop >= 1.0-1e-8:
        gone = 0.
    if gone == 0:
        rigid('chunk',on_bun,spin)
    else:
        # Pull the cap into the mouth only during the contact window.
        # Once hidden keep it collapsed at the bun rather than tracking the face.
        point = on_bun.lerp(head_deform() @ MOUTH,gone) if gone < 1 else on_bun
        rigid('chunk',point,spin*(1-.999*gone))
    # Close the sculpted smile for the bite, then use the lower-mouth
    # control for chewing rather than exaggerating head nods.
    opening = pulse(t,2.25,2.85,3.0,3.22)
    closure = pulse(t,bite_start,bite_start+.20,5.65,6.25) if bite_start is not None else 0.
    jaw_delta = .021*closure - .010*opening - .008*chew*closure
    jaw = rig.pose.bones['mello_jaw']
    jaw.location = jaw.bone.matrix_local.to_3x3().inverted() @ Vector((0,0,jaw_delta))
    for side,sign in (('L',1),('R',-1)):
        hold(side,centre+spin @ Vector((sign*GRIP,-.01,-.055)),spin)


bind_mouth()
kit.attach('Mello props')
kit.bake('Santa05_Cream_Bun_Bite', FRAMES, pose_at,
         ['bun','chunk','head','eye.L','eye.R','mello_jaw'] + [f'{n}.{s}' for s in 'LR' for n in ('upper_arm','forearm','hand')],
         activity=lambda t: pulse(t*DURATION,.50,2.30,3.60,5.10))
FRONT = ((.12, -5.85, 1.98), (.12, -.03, 1.06), 77, (800, 900))
CLOSE = ((-.30, -1.45, 1.70), (-.05, -.35, 1.50), 62, (640, 640))
BITE_FRAME = round(3.35 * 24) + 1
kit.finish('santa05', FRONT, [
    ('front', 1, FRONT),
    ('raise', 40, FRONT),
    ('bite', BITE_FRAME, CLOSE),
    ('side', BITE_FRAME, ((-1.6, -.9, 1.65), (-.03, -.25, 1.55), 70, (640, 640))),
    ('bitten', 132, FRONT),
    ('bun', 132, CLOSE),
    ('sack', 1, ((.95, -1.9, .85), (.74, .1, .45), 70, (640, 640))),
])
