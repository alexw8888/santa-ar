"""Flower heads, stems and arrangements shared by the Bouquet Cafe edition (Santa 03).

All heads are modelled around their own origin, opening toward +Z, inside the current
santa_kit frame, so an arrangement only has to aim each head along its direction.
"""
import math
import random

from mathutils import Matrix, Vector

from santa_kit import TAU, ball, cord, ellipsoid, frame, leaf, material, sheet


def petal_ring(count, r, dist, height, spread, opening, mat, phase=0, rows=4, cols=5):
    """Cupped petals wrapped around the axis; `spread` is each petal's half-angle at its widest."""
    for i in range(count):
        a0 = TAU * i / count + phase
        grid = []
        for j in range(rows + 1):
            t = j / rows
            half = spread * (.45 + .55 * math.sin(math.pi * (.15 + .6 * t)))
            rad = r * (dist + opening * t * t)
            z = r * height * math.sin(math.pi / 2 * t)
            grid.append([(rad * math.cos(a0 + u * half) * (1 + .10 * u * u * t),
                          rad * math.sin(a0 + u * half) * (1 + .10 * u * u * t), z - r * .08 * u * u * t)
                         for u in [2 * k / (cols - 1) - 1 for k in range(cols)]])
        sheet(grid, mat)


def rose(r, mat, deep):
    ellipsoid(0, 0, r * .40, r * .22, r * .22, r * .42, deep, 8, 4)
    for count, dist, height, spread, opening, phase, tone in (
            (3, .12, .95, 1.5, .05, .3, deep), (4, .26, .92, 1.05, .12, 1.1, deep), (5, .42, .84, .85, .26, .2, mat),
            (6, .60, .70, .72, .48, .9, mat), (7, .76, .50, .60, .72, .4, mat)):
        petal_ring(count, r, dist, height, spread, opening, tone, phase)


def tulip(r, mat, green):
    ellipsoid(0, 0, -.004, r * .30, r * .30, r * .25, green, 8, 4)
    for ring, phase, scale in ((0, 0, 1), (1, math.pi / 3, .93)):
        for i in range(3):
            a0 = TAU * i / 3 + phase
            grid = []
            for j in range(6):
                t = j / 5
                rad = r * scale * (.30 + .70 * math.sin(math.pi * min(1, .12 + .80 * t)))
                half = math.radians(64) * (1 - .55 * t ** 3)
                grid.append([(rad * math.cos(a0 + u * half), rad * math.sin(a0 + u * half), r * 2.3 * t * scale)
                             for u in (-1, -.5, 0, .5, 1)])
            sheet(grid, mat)


def daisy(r, mat, centre, count=14):
    ellipsoid(0, 0, r * .05, r * .28, r * .28, r * .13, centre, 12, 4)
    for i in range(count):
        a = TAU * i / count
        c, s = math.cos(a), math.sin(a)
        grid = []
        for j in range(4):
            t = j / 3
            w = r * .13 * math.sin(math.pi * (.2 + .7 * t)) ** .5
            d = r * (.22 + .78 * t)
            z = r * (.04 - .18 * t * t)
            grid.append([(d * c - u * w * s, d * s + u * w * c, z) for u in (-1, 0, 1)])
        sheet(grid, mat)


def spike(length, mat, stem, size, seed):
    """Lavender or delphinium: florets clustered along the top of a stem (+Z)."""
    rnd = random.Random(seed)
    cord([(0, 0, -.03), (0, 0, length * .5), (0, 0, length)], .0022, stem, [1, .9, .6], sides=5)
    n = int(length / size * 1.6)
    for k in range(n):
        t = k / n
        z = length * (.38 + .62 * t)
        a = k * 2.4
        rr = size * (1.1 - .7 * t)
        ball(rr * math.cos(a), rr * math.sin(a), z, size * (1 - .45 * t) * rnd.uniform(.8, 1.1), mat, 6, 3)


def aim(origin, direction, spin=0):
    d = Vector(direction).normalized()
    rot = Vector((0, 0, 1)).rotation_difference(d).to_matrix().to_4x4()
    return Matrix.Translation(origin) @ rot @ Matrix.Rotation(spin, 4, 'Z')


def palette():
    m = {}
    m['red'] = material('Crimson rose petals', 'B3112C', .55, sheen=.12)
    m['red_deep'] = material('Rose heart', '7A0619', .55, sheen=.12)
    m['pink'] = material('Blush rose petals', 'F08AA5', .55, sheen=.12)
    m['pink_deep'] = material('Blush rose heart', 'D2587A', .55, sheen=.12)
    m['yellow'] = material('Yellow tulip', 'F7C02B', .45, sheen=.3)
    m['orange'] = material('Apricot tulip', 'F28A3A', .45, sheen=.3)
    m['tulip_pink'] = material('Pink tulip', 'F06C8A', .45, sheen=.3)
    m['aster'] = material('Lilac aster', '9B7BD8', .5, sheen=.3)
    m['sun'] = material('Golden daisy', 'F8C531', .5, sheen=.3)
    m['eye'] = material('Daisy eye', 'C77A16', .7)
    m['lavender'] = material('Lavender florets', '7A5BC4', .6)
    m['delphinium'] = material('Delphinium blue', '4E6FD8', .55)
    m['gyp'] = material('Babys breath', 'F4F1F6', .7)
    m['stem'] = material('Flower stems', '4E8A2F', .55)
    m['leaf'] = material('Bouquet leaves', '3F7B2B', .5)
    m['leaf2'] = material('Fresh leaves', '6A9E3A', .5)
    return m


def head(kind, size, m, seed):
    rnd = random.Random(seed)
    if kind == 'red':
        rose(size, m['red'], m['red_deep'])
    elif kind == 'pink':
        rose(size, m['pink'], m['pink_deep'])
    elif kind in ('yellow', 'orange', 'tulip_pink'):
        tulip(size * .55, m[kind], m['stem'])
    elif kind in ('aster', 'sun'):
        daisy(size * .85, m[kind], m['eye'], 13 + rnd.randrange(4))
    elif kind == 'gyp':
        for k in range(7):
            a = k * 2.4
            ball(.018 * math.cos(a) * (k % 3) / 2, .018 * math.sin(a) * (k % 3) / 2, .005 * (k % 2), .0055,
                 m['gyp'], 6, 3)


def arrangement(centre, radius, cone, kinds, m, seed, stems_to=None, spikes=0, leaves=0, spike_length=.16, leaf_size=1):
    """Heads spread over a dome (Fibonacci spiral within `cone` degrees of +Z).

    stems_to=(tie, bottom, spread) draws each stem down through the tie point to the bottom.
    """
    rnd = random.Random(seed)
    n = len(kinds)
    tips = []
    for i, (kind, size) in enumerate(kinds):
        h = 1 - (1 - math.cos(math.radians(cone))) * (i + .5) / n
        a = i * 2.39996 + rnd.uniform(-.2, .2)
        s = math.sqrt(max(0, 1 - h * h))
        d = Vector((s * math.cos(a), s * math.sin(a), h))
        p = Vector(centre) + d * radius * rnd.uniform(.92, 1.04)
        with frame(aim(p, d.lerp(Vector((0, 0, 1)), .25), rnd.uniform(0, TAU))):
            head(kind, size, m, seed + i)
        tips.append(p)
    for k in range(spikes):
        a = TAU * k / spikes + rnd.uniform(-.3, .3)
        d = Vector((.42 * math.cos(a), .42 * math.sin(a), 1)).normalized()
        p = Vector(centre) + d * radius * .7
        with frame(aim(p, d, 0)):
            spike(spike_length * rnd.uniform(.85, 1.15), m['lavender' if k % 3 else 'delphinium'], m['stem'],
                  .0075 if k % 3 else .010, seed * 7 + k)
        tips.append(p)
    for k in range(leaves):
        a = TAU * k / leaves + rnd.uniform(-.2, .2)
        d = Vector((math.cos(a), math.sin(a), rnd.uniform(-.1, .35))).normalized()
        p = Vector(centre) + Vector((math.cos(a), math.sin(a), 0)) * radius * .55 + Vector((0, 0, -radius * .25))
        rot = Vector((0, 0, 1)).rotation_difference(d).to_matrix().to_4x4()
        # Turn each leaf so its curl faces down/outward.
        with frame(Matrix.Translation(p) @ rot @ Matrix.Rotation(-a + math.pi / 2, 4, 'Z')):
            leaf(leaf_size * rnd.uniform(.085, .12), leaf_size * rnd.uniform(.020, .028), m['leaf' if k % 2 else 'leaf2'])
    if stems_to:
        tie, bottom, spread = stems_to
        for i, p in enumerate(tips):
            a = i * 2.39996
            r = spread * math.sqrt((i + .5) / len(tips))
            off = Vector((r * math.cos(a), r * math.sin(a), 0))
            cord([p - (p - Vector(tie)).normalized() * .01, Vector(tie) + off * .8 + (p - Vector(tie)) * .45,
                  Vector(tie) + off * .8, Vector((0, 0, (tie[2] + bottom[2]) / 2)) + off * .9, Vector(bottom) + off * .75],
                 .0032, m['stem'], sides=5)
