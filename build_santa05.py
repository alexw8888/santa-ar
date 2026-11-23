"""Build the Mello edition from the base character made by build_santa_base.py.

blender -b --factory-startup --python-exit-code 1 -P build_santa05.py -- previews
The optional directory receives front, bite, bun and sack previews and the page poster.
"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mathutils import Vector  # noqa: E402

import santa_kit as kit  # noqa: E402
from santa_kit import (TAU, aim_eyes, ball, bound, cord, ellipsoid, hold, label, look,  # noqa: E402
                       material, place, profile, ramp, recolor, rigid, surface, turn)

BUN = Vector((-.16, -.40, 1.60))      # centre of the cream bun, held up in both gloves
RX, RY, RZ = .15, .135, .13
BITE = .085                           # the bite is taken from the side facing his mouth (+X)
GRIP = .10                            # each glove wraps the lower side of the bun
SACK = Vector((.74, .14, 0))
kit.start(5, 'Mello', 'photos/05 Mello Santa.jpg', [
    ('bun', BUN, BUN + Vector((0, 0, .2)), 'root'),
])
rig = kit.rig

crust = material('Golden brioche crust', 'C07A34', .5, coat=.25)
crumb = material('Soft brioche crumb', 'F2D79B', .85)
cream = material('Whipped cream', 'FFF8EE', .5, sheen=.3)
sugar = material('Sugar crystals', 'FFFFFF', .2)
berry = material('Strawberry', 'D6162B', .25, coat=.8)
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


# ---------------------------------------------------------------- cream bun with a bite
def bun_point(a, lat):
    s = math.sin(lat)
    z = RZ * (s if s > -.7 else -.7 - .4 * (-.7 - s))
    k = 1 + .025 * math.cos(3 * a + .4) * math.cos(lat)
    return Vector((RX * k * math.cos(lat) * math.cos(a), RY * k * math.cos(lat) * math.sin(a), z))


def bitten(p):
    """Carve a scalloped bite from the +X side; returns the point and whether it was carved."""
    angle = math.atan2(p.z, p.y)
    wall = BITE + .045 * ((p.y / RY) ** 2 + (p.z / RZ) ** 2) + .006 * abs(math.sin(5 * angle))
    if p.x > wall:
        return Vector((wall, p.y, p.z)), True
    return p, False


with bound('bun'), place(*BUN):
    n, m = 48, 22
    grid, carved = [], []
    for j in range(m + 1):
        lat = -math.pi / 2 + math.pi * j / m
        row = [bitten(bun_point(TAU * i / n, lat)) for i in range(n)]
        grid.append([p for p, _ in row])
        carved.append([c for _, c in row])
    points = [p for row in grid for p in row]
    quads = {False: [], True: []}
    for j in range(m):
        for i in range(n):
            quad = [(j, i), (j, (i + 1) % n), (j + 1, (i + 1) % n), (j + 1, i)]
            quads[all(carved[a][b] for a, b in quad)].append(tuple(a * n + b for a, b in quad))
    surface(points, quads[False], crust, rounded=True)
    surface(points, quads[True], crumb)
    # Cream filling shows in the bite; the rest swirls out of the split top with piped peaks.
    ellipsoid(BITE - .022, -.005, .012, .040, .075, .062, cream, 20, 10,
              wobble=lambda a, z: 1 + .06 * math.cos(6 * a + 9 * z))
    # A ridge of cream bursts from a split across the top-left of the bun, with two piped swirls.
    for k in range(7):
        t = k / 6
        ellipsoid(-.095 + .10 * t, -.012 + .02 * t, RZ * (.80 + .12 * math.sin(math.pi * t)), .042, .040,
                  .036 + .010 * math.sin(math.pi * t), cream, 20, 8,
                  wobble=lambda a, z, k=k: 1 + .12 * math.cos(7 * a + k))
    for x, y, z, r in ((-.085, -.030, RZ + .012, .030), (-.035, -.035, RZ + .028, .028)):
        with place(x, y, z):
            profile([(-.01, r, r), (.006, r * 1.05, r * 1.05), (.020, r * .75, r * .75), (.034, r * .30, r * .30),
                     (.044, .002, .002)], cream, n=32,
                    wobble=lambda a, zz: 1 + .16 * math.cos(8 * a + 18 * zz))
    # Strawberry, tip up, nestled in the cream with its seeds.
    with place(-.060, -.005, RZ + .040, tilt=-12, roll=8):
        profile([(0, .024, .024), (.012, .031, .031), (.030, .029, .029), (.048, .020, .020), (.064, .009, .009),
                 (.071, .002, .002)], berry, n=24)
        for k in range(34):
            z = .022 + .040 * ((k * .618) % 1)
            a = k * 2.4
            r = (.031 if z < .03 else .031 - (z - .03) * .55) + .0004
            ball(r * math.cos(a), r * math.sin(a), z, .0017, seeds, 4, 2)
    rnd = random.Random(5)
    for _ in range(280):
        a, lat = rnd.uniform(0, TAU), math.asin(rnd.uniform(-.2, 1))
        p = bun_point(a, lat)
        if bitten(p)[1] or (p.z > RZ * .6 and -.15 < p.x < .03 and abs(p.y) < .06):
            continue
        p = p * 1.004
        ball(p.x, p.y, p.z, rnd.uniform(.0022, .0035), sugar, 4, 2)

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


# ---------------------------------------------------------------- five-second loop
CAMERA = Vector((-.05, -3.2, 1.6))


def pose_at(t):
    bite = ramp(t, .16, .36) * (1 - ramp(t, .52, .72))
    chomp = math.sin(math.pi * ramp(t, .36, .52))
    chew = math.sin(TAU * 3 * ramp(t, .60, 1)) * (1 - ramp(t, .92, 1))
    centre = BUN + Vector((.05, .04, .05)) * bite
    spin = turn(16 * bite, 'Z') @ turn(-6 * bite, 'Y')
    rigid('bun', centre, spin)
    for side, sign in (('L', 1), ('R', -1)):
        hold(side, centre + spin @ Vector((sign * GRIP, -.01, -.055)), spin)
    target = CAMERA.lerp(centre + spin @ Vector((BITE, 0, 0)), min(1, bite * 1.3))
    look(target, math.radians(5) * chomp + math.radians(2.5) * chew, turn_share=.45)
    aim_eyes(target)


kit.attach('Mello props')
kit.bake('Santa05_Cream_Bun_Bite', 121, pose_at,
         ['bun', 'head', 'eye.L', 'eye.R'] + [f'{n}.{s}' for s in 'LR' for n in ('upper_arm', 'forearm', 'hand')])
FRONT = ((.12, -5.85, 1.98), (.12, -.03, 1.06), 77, (800, 900))
kit.finish('santa05', FRONT, [
    ('front', 1, FRONT),
    ('bite', 42, FRONT),
    ('bun', 1, ((-.30, -1.30, 1.75), (-.13, -.40, 1.62), 70, (640, 640))),
    ('sack', 1, ((.95, -1.9, .85), (.74, .1, .45), 70, (640, 640))),
])
