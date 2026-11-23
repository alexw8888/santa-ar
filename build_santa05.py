"""Build the Mello edition from the base character made by build_santa_base.py.

blender -b --factory-startup --python-exit-code 1 -P build_santa05.py -- previews
The optional directory receives front, raise, bite, side, bitten, bun and sack previews and the page poster.
"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mathutils import Matrix, Vector  # noqa: E402

import santa_kit as kit  # noqa: E402
from santa_kit import (TAU, aim_eyes, ball, bound, cord, ellipsoid, frame, hold, label, look,  # noqa: E402
                       material, place, profile, ramp, recolor, rigid, surface, turn)

BUN = Vector((-.10, -.50, 1.33))      # rest centre of the cream bun: held low, in front of his chest
RX, RY, RZ = .15, .135, .13
TOP = Vector((.55, 0, .835))          # the bite comes off the top of the bun, on the side away from the cream
BITE = .080                           # depth of the bite's floor along TOP
GRIP = .10                            # each glove wraps the lower side of the bun
SACK = Vector((.74, .14, 0))
kit.start(5, 'Mello', 'photos/05 Mello Santa.jpg', [
    ('bun', BUN, BUN + Vector((0, 0, .2)), 'root'),
    # The piece he bites off: part of the bun until the bite, then gone into his mouth.
    ('chunk', BUN + TOP * BITE, BUN + TOP * (BITE + .1), 'bun'),
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


with bound('bun'), place(*BUN):
    n, m = 64, 30
    whole, grid, carved = [], [], []
    for j in range(m + 1):
        lat = -math.pi / 2 + math.pi * j / m
        row = [bun_point(TAU * i / n, lat) for i in range(n)]
        whole.append(row)
        row = [bitten(p) for p in row]
        grid.append([p for p, _ in row])
        carved.append([c for _, c in row])
    quads = {False: [], True: []}
    piece = []
    for j in range(m):
        for i in range(n):
            quad = [(j, i), (j, (i + 1) % n), (j + 1, (i + 1) % n), (j + 1, i)]
            polygon = tuple(a * n + b for a, b in quad)
            quads[all(carved[a][b] for a, b in quad)].append(polygon)
            if any(carved[a][b] for a, b in quad):
                piece.append(polygon)
    surface([p for row in grid for p in row], quads[False], crust, rounded=True)
    surface([p for row in grid for p in row], quads[True], crumb)
    # The piece he bites off is the uncarved crust over the bite, meeting the bun along its rim.
    with bound('chunk'):
        surface([p for row in whole for p in row], piece, crust, rounded=True)
    # Cream filling shows in the floor of the bite (hidden under the piece until he takes it).
    with frame(Matrix.Translation(TOP * (BITE - .026)) @ TOP.to_track_quat('Z', 'Y').to_matrix().to_4x4()):
        ellipsoid(0, 0, 0, .050, .042, .034, cream, 20, 10,
                  wobble=lambda a, z: 1 + .06 * math.cos(6 * a + 9 * z))
    # A ridge of cream bursts from a split across the top-left of the bun, with two piped swirls.
    for k in range(7):
        t = k / 6
        ellipsoid(-.120 + .085 * t, -.012 + .02 * t, RZ * (.80 + .12 * math.sin(math.pi * t)), .040, .040,
                  .034 + .010 * math.sin(math.pi * t), cream, 20, 8,
                  wobble=lambda a, z, k=k: 1 + .12 * math.cos(7 * a + k))
    for x, y, z, r in ((-.105, -.030, RZ + .012, .030), (-.060, -.035, RZ + .024, .026)):
        with place(x, y, z):
            profile([(-.01, r, r), (.006, r * 1.05, r * 1.05), (.020, r * .75, r * .75), (.034, r * .30, r * .30),
                     (.044, .002, .002)], cream, n=32,
                    wobble=lambda a, zz: 1 + .16 * math.cos(8 * a + 18 * zz))
    # Strawberry, tip up, nestled in the cream with its seeds.
    with place(-.085, -.005, RZ + .040, tilt=-12, roll=8):
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
        if p.z > RZ * .6 and -.17 < p.x < 0 and abs(p.y) < .06:
            continue
        p = p * 1.004
        with bound('chunk' if bitten(p)[1] else 'bun'):
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


ACTION = 5                            # seconds: raise, bite, lower and chew
REST = 3                              # seconds holding the bitten bun before the loop brings back a whole one
FRAMES = (ACTION + REST) * 24 + 1
LIP = Vector((0, -.205, 1.600))       # his lower lip at rest: the bitten edge of the bun comes up to here
MOUTH = Vector((0, -.15, 1.625))      # just behind his lips, where the bitten piece disappears
EDGE = .125                           # from the bun's centre out along TOP to its crust over the bite
LOW = (BUN, turn(8, 'X'))             # held in front of his chest, the top tipped a little to the viewer
# Raised under his chin: rolled so the bite site is the highest point of the bun, then tipped back and
# turned in, so the bun's top edge meets his lips while his mouth stays in view above it.
HIGH = turn(20, 'Z') @ turn(-25, 'X') @ turn(-25, 'Y')
CHOMP = .44                           # the share of ACTION where his teeth close on the bun


def head_deform():
    head = rig.pose.bones['head']
    return head.matrix @ rig.data.bones['head'].matrix_local.inverted()


def pose_at(loop):
    f = round(loop * (FRAMES - 1)) + 1
    # Gestures are timed as shares of ACTION; past it (t > 1) he just holds the bitten bun low.
    t = loop * (FRAMES - 1) / (ACTION * 24)
    lift = ramp(t, .08, .34) * (1 - ramp(t, .54, .80))
    push = math.sin(math.pi * ramp(t, .34, .52))
    chew = math.sin(TAU * 3 * ramp(t, .54, .94)) * (1 - ramp(t, .88, .94))
    spin = LOW[1].to_quaternion().slerp(HIGH.to_quaternion(), lift).to_matrix()
    # His head turns toward where the bun is going and leans in for the bite; the bun then rises to
    # wherever his lips are, and his teeth close on its top edge.
    target = CAMERA.lerp(LIP, min(1, lift * 1.3))
    look(target, math.radians(4) * push + math.radians(2.5) * chew, turn_share=.45)
    aim_eyes(target + Vector((0, 0, -.08)) * lift)
    lip = head_deform() @ LIP
    centre = LOW[0].lerp(lip - HIGH @ (TOP * EDGE), lift) + Vector((0, .018, .012)) * push
    rigid('bun', centre, spin)
    on_bun = centre + spin @ (TOP * BITE)
    if t < CHOMP or f == FRAMES:
        rigid('chunk', on_bun, spin)                       # still part of the bun
    elif f == FRAMES - 1:
        rigid('chunk', on_bun, spin * .01)                 # back on the bun, too small to see, ready to loop
    else:
        gone = ramp(t, CHOMP, CHOMP + .06)
        rigid('chunk', on_bun.lerp(head_deform() @ MOUTH, gone), spin * (1 - .99 * gone))
    for side, sign in (('L', 1), ('R', -1)):
        hold(side, centre + spin @ Vector((sign * GRIP, -.01, -.055)), spin)


kit.attach('Mello props')
kit.bake('Santa05_Cream_Bun_Bite', FRAMES, pose_at,
         ['bun', 'chunk', 'head', 'eye.L', 'eye.R'] + [f'{n}.{s}' for s in 'LR' for n in ('upper_arm', 'forearm', 'hand')])
FRONT = ((.12, -5.85, 1.98), (.12, -.03, 1.06), 77, (800, 900))
CLOSE = ((-.30, -1.45, 1.70), (-.05, -.35, 1.50), 62, (640, 640))
BITE_FRAME = round(CHOMP * ACTION * 24) + 1
kit.finish('santa05', FRONT, [
    ('front', 1, FRONT),
    ('raise', 40, FRONT),
    ('bite', BITE_FRAME, CLOSE),
    ('side', BITE_FRAME, ((-1.6, -.9, 1.65), (-.03, -.25, 1.55), 70, (640, 640))),
    ('bitten', 90, FRONT),
    ('bun', 90, CLOSE),
    ('sack', 1, ((.95, -1.9, .85), (.74, .1, .45), 70, (640, 640))),
])
