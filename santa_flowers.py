"""Flowers for the Bouquet Café edition (Santa 03), modelled on the café's wrapped bouquet
(photos/03 Bouquet Cafe bouquet *.jpg): deep red roses, ruffled peach-pink spray roses with buds,
silver-dollar eucalyptus and airy limonium sprays.

Heads are modelled around their own origin, opening toward +Z, inside the current santa_kit frame,
so an arrangement only has to aim each head along its direction.
"""
import math
import random

from mathutils import Matrix, Vector

from santa_kit import TAU, ball, cord, ellipsoid, frame, leaf, material, sheet

GOLDEN = 2.39996  # radians between successive petals, as in a real rose


def palette():
    m = {}
    m['red'] = material('Crimson rose petals', '8A0A1C', .48, sheen=.25)
    m['red_deep'] = material('Rose heart', '520410', .5, sheen=.25)
    m['pink'] = material('Blush rose petals', 'F4B3A6', .55, sheen=.2)
    m['pink_deep'] = material('Blush rose heart', 'E48C82', .55, sheen=.2)
    m['sepal'] = material('Rose sepals', '3E6B2A', .55)
    m['stem'] = material('Flower stems', '4E7A30', .55)
    m['eucalyptus'] = material('Silver dollar eucalyptus', '7A8C78', .6, sheen=.35)
    m['eucalyptus2'] = material('Blue eucalyptus', '6C8277', .6, sheen=.35)
    m['eucalyptus_stem'] = material('Eucalyptus stems', '8C6B50', .6)
    m['limonium'] = material('Limonium sprays', 'F1ECDF', .75)
    m['limonium_stem'] = material('Limonium stems', 'A2A77E', .7)
    for mat in m.values():
        tinted(mat)
    return m


def tinted(mat):
    """Tint a material's sheen with its own colour, so deep reds and greens don't go dusty pale."""
    mat.node_tree.nodes['Principled BSDF'].inputs['Sheen Tint'].default_value = (*mat.diffuse_color[:3], 1)
    return mat


def petal(a0, base, length, half, opening, reflex, mat, curl=0., ruffle=0., phase=0., rows=5, cols=5):
    """One petal growing from radius `base` at angle `a0`, wrapped around the flower's axis.

    half: half-width as an angle around the axis; opening: lean out from upright (radians);
    reflex: how far the tip rolls back outward; curl: the edges flare out near the tip;
    ruffle: a wavy rim, as on spray roses."""
    grid = []
    for j in range(rows + 1):
        t = j / rows
        row = []
        for i in range(cols):
            u = 2 * i / (cols - 1) - 1
            s = t * (1 - .22 * u * u * t ** 3)  # the corners stop short: a rounded petal tip
            w = half * (.38 + .62 * math.sin(math.pi * (.08 + .72 * s)))
            rad = (base + length * (math.sin(opening) * s + reflex * s ** 3) + curl * length * u * u * s * s
                   + ruffle * length * math.sin(3 * math.pi * u + phase) * s ** 3)
            z = length * (math.cos(opening) * s - reflex * .5 * s ** 4)
            a = a0 + u * w
            row.append((rad * math.cos(a), rad * math.sin(a), z))
        grid.append(row)
    sheet(grid, mat)


def sepals(r, mat, count=5, seed=0):
    rnd = random.Random(seed)
    ellipsoid(0, 0, -r * .10, r * .22, r * .22, r * .20, mat, 8, 4)
    for k in range(count):
        a = TAU * k / count + rnd.uniform(-.2, .2)
        d = Vector((math.cos(a), math.sin(a), -.55)).normalized()
        rot = Vector((0, 0, 1)).rotation_difference(d).to_matrix().to_4x4()
        with frame(Matrix.Translation((0, 0, -r * .1)) @ rot @ Matrix.Rotation(-a + math.pi / 2, 4, 'Z')):
            leaf(r * rnd.uniform(.55, .75), r * .09, mat, fold=.4, curl=.25, segments=4)


def rose(r, mat, deep, sepal, seed=0, petals=20, bloom=1., ruffle=0.):
    """A rose `r` across its open outer petals: a tight spiral of upright inner petals that open
    and roll back toward the outside, on green sepals."""
    rnd = random.Random(seed)
    ellipsoid(0, 0, r * .22, r * .16, r * .16, r * .26, deep, 8, 4)
    for k in range(petals):
        f = k / (petals - 1)
        petal(k * GOLDEN + rnd.uniform(-.12, .12), r * (.03 + .24 * f), r * (.46 + .44 * f) * rnd.uniform(.94, 1.05),
              1.30 - .62 * f, bloom * (.10 + 1.05 * f ** 1.5), bloom * .55 * max(0, f - .45),
              deep if f < .3 else mat, curl=.30 * f * f, ruffle=ruffle, phase=rnd.uniform(0, TAU),
              rows=5 if f > .3 else 4)
    sepals(r, sepal, seed=seed)


def bud(r, mat, deep, sepal, seed=0):
    """A closed spray-rose bud: a tight teardrop of petals hugged by sepals."""
    rnd = random.Random(seed)
    ellipsoid(0, 0, r * .55, r * .36, r * .36, r * .62, deep, 8, 5)
    for k in range(4):
        petal(k * GOLDEN + rnd.uniform(0, 1), r * .20, r * 1.05, 1.1, .12, .05, mat, rows=4, cols=4)
    sepals(r * 1.2, sepal, seed=seed)


def head(kind, size, m, seed):
    if kind == 'red':
        rose(size, m['red'], m['red_deep'], m['sepal'], seed, petals=22, bloom=.85)
    elif kind == 'pink':
        rose(size, m['pink'], m['pink_deep'], m['sepal'], seed, petals=15, bloom=1.25, ruffle=.07)
    elif kind == 'bud':
        bud(size, m['pink'], m['pink_deep'], m['sepal'], seed)


def aim(origin, direction, spin=0):
    d = Vector(direction).normalized()
    rot = Vector((0, 0, 1)).rotation_difference(d).to_matrix().to_4x4()
    return Matrix.Translation(origin) @ rot @ Matrix.Rotation(spin, 4, 'Z')


def eucalyptus(m, base, direction, length, leaves, size, seed):
    """A silver-dollar eucalyptus sprig: a woody stem with round, cupped leaves in opposite pairs,
    each lying flat beside the stem so its face shows from outside the bouquet."""
    rnd = random.Random(seed)
    d = Vector(direction).normalized()
    side = d.cross(Vector((0, 0, 1)) if abs(d.z) < .95 else Vector((1, 0, 0))).normalized()
    sag = Vector((0, 0, -.18 * length))
    path = [Vector(base) + d * length * k / 6 + sag * (k / 6) ** 2 for k in range(7)]
    cord(path, .0022, m['eucalyptus_stem'], [1, 1, .9, .8, .7, .6, .5], sides=5)
    mat = m['eucalyptus' if seed % 3 else 'eucalyptus2']
    for k in range(leaves):
        t = .2 + .8 * k / max(1, leaves - 1)
        i = min(5, int(t * 6))
        p = path[i].lerp(path[i + 1], t * 6 - i)
        axis = (path[i + 1] - path[i]).normalized()
        for s in (-1, 1):
            r = size * rnd.uniform(.85, 1.1) * (1.15 - .45 * t)
            twist = Matrix.Rotation(rnd.uniform(-.45, .45), 3, axis)
            u = twist @ (side * s)
            v = (axis + u * .15).normalized()
            normal = u.cross(v).normalized() * s
            centre = p + u * r * 1.02
            rows = []
            for j in range(7):
                b = 2 * j / 6 - 1
                rows.append([tuple(centre + u * (r * a * math.sqrt(max(0, 1 - b * b))) + v * (r * b)
                                   + normal * (r * .22 * (a * a + b * b)) - u * (r * .12 * (1 - b * b)))
                             for a in (-1, -.5, 0, .5, 1)])
            sheet(rows, mat)


def limonium(m, base, direction, length, seed, twigs=8, florets=11):
    """A limonium (caspia) spray: fine branching twigs ending in clusters of tiny cream florets."""
    rnd = random.Random(seed)
    d = Vector(direction).normalized()
    tip = Vector(base) + d * length
    cord([Vector(base), Vector(base).lerp(tip, .5), tip], .0013, m['limonium_stem'], sides=4)
    ends = [tip]
    for k in range(twigs):
        start = Vector(base).lerp(tip, .5 + .45 * k / max(1, twigs - 1))
        twig = (d + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-.2, .5)))).normalized()
        end = start + twig * length * rnd.uniform(.16, .28)
        cord([start, end], .0009, m['limonium_stem'], sides=3)
        ends.append(end)
    for end in ends:
        for j in range(florets):
            q = end + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-.6, 1))) * .014
            ball(q.x, q.y, q.z, .0030 * rnd.uniform(.7, 1.25), m['limonium'], 3, 2)


def arrangement(centre, radius, cone, kinds, m, seed, height=1., stems_to=None):
    """Heads spread over a dome (a Fibonacci spiral within `cone` degrees of +Z, squashed by
    `height`), each facing out from the dome, part way toward straight up.

    stems_to=(tie, bottom, spread) draws each stem down through the tie point to the bottom."""
    rnd = random.Random(seed)
    n = len(kinds)
    tips = []
    for i, (kind, size) in enumerate(kinds):
        h = 1 - (1 - math.cos(math.radians(cone))) * (i + .5) / n
        a = i * GOLDEN + rnd.uniform(-.15, .15)
        s = math.sqrt(max(0, 1 - h * h))
        d = Vector((s * math.cos(a), s * math.sin(a), h))
        p = Vector(centre) + Vector((d.x, d.y, d.z * height)) * radius * rnd.uniform(.94, 1.03)
        with frame(aim(p, d.lerp(Vector((0, 0, 1)), .3), rnd.uniform(0, TAU))):
            head(kind, size, m, seed + i)
        tips.append(p)
    if stems_to:
        tie, bottom, spread = stems_to
        for i, p in enumerate(tips):
            a = i * GOLDEN
            r = spread * math.sqrt((i + .5) / len(tips))
            off = Vector((r * math.cos(a), r * math.sin(a), 0))
            cord([p - (p - Vector(tie)).normalized() * .01, Vector(tie) + off * .8 + (p - Vector(tie)) * .45,
                  Vector(tie) + off * .8, Vector((0, 0, (tie[2] + bottom[2]) / 2)) + off * .9, Vector(bottom) + off * .75],
                 .0032, m['stem'], sides=5)
    return tips
