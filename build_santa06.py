"""Build the Yunqueen edition from the base character made by build_santa_base.py.

blender -b --factory-startup --python-exit-code 1 -P build_santa06.py -- previews
The optional directory receives front, lift, chopsticks, bowl and duck previews and the page poster.
"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mathutils import Vector  # noqa: E402

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix  # noqa: E402

import santa_kit as kit  # noqa: E402
from santa_kit import (TAU, aim_eyes, around, bound, cord, ellipsoid, hold, label, look,  # noqa: E402
                       material, place, profile, ramp, recolor, rigid, rings, sheet, steam, turn)

FOOT = Vector((.12, -.52, 1.12))       # centre of the bowl's foot ring
CENTRE = FOOT + Vector((0, 0, .08))    # the left glove wraps the bowl's side level with this point
SPAN = .150
BROTH = .196
DUCK = Vector((.70, -.24, 0))

# The right glove holds the chopsticks the usual way. It is modelled in its own frame from the wrist:
# x runs to the knuckles, y to the thumb side and z out of the back of the hand (the palm faces -z).
# The lower stick lies in the web between thumb and index finger and rests on the ring fingertip; it
# never moves in the hand. The upper stick is held like a pencil between the thumb tip and the index
# and middle fingertips, and pivots against the side of the index finger to open and pinch.
WRIST_R = Vector((-.44, -.32, 1.55))   # the base's right wrist (hand.R head)
LOWER_TOP = Vector((.025, .060, .005))
LOWER_DIR = Vector((1, -.40, -.50)).normalized()
LENGTH = .27
TIPS = LOWER_TOP + LOWER_DIR * LENGTH  # both tips meet here when pinched
UPPER_TOP = Vector((.030, .065, .040))
UPPER_DIR = (TIPS - UPPER_TOP).normalized()
WEB = LOWER_TOP + LOWER_DIR * .05      # where the lower stick sits in the web of the thumb
PIVOT = UPPER_TOP + UPPER_DIR * .06    # where the upper stick bears on the side of the index finger
HINGE_AXIS = UPPER_DIR.cross(LOWER_DIR).normalized()   # turning about it swings the upper tip open
# The lifted noodles: a bundle of strands on a chain of bones, modelled hanging straight down from NOODLES.
NOODLES = Vector((-.45, -.90, 1.60))
LINKS, LINK = 16, .018
kit.start(6, 'Yunqueen', 'photos/06 Yunqueen Santa.jpg', [
    ('bowl', CENTRE, CENTRE + Vector((0, 0, .2)), 'root'),
    ('steam', FOOT + Vector((0, 0, BROTH)), FOOT + Vector((0, 0, BROTH + .2)), 'bowl'),
    ('duck', DUCK, DUCK + Vector((0, 0, .3)), 'root'),
    ('sticks', WRIST_R + WEB, WRIST_R + WEB + LOWER_DIR * .1, 'root'),
    ('stick', WRIST_R + PIVOT, WRIST_R + PIVOT + UPPER_DIR * .1, 'sticks'),
] + [(f'noodle.{j:02d}', NOODLES - Vector((0, 0, j * LINK)), NOODLES - Vector((0, 0, j * LINK + .01)), 'root')
     for j in range(LINKS)])
rig = kit.rig
santa = kit.santa
assert (rig.data.bones['hand.R'].head_local - WRIST_R).length < .001

# The base mirrors the cupped left glove onto the right hand; this edition's right glove holds chopsticks.
mesh = bmesh.new()
mesh.from_mesh(santa.data)
skin = mesh.verts.layers.deform.active
right = santa.vertex_groups['hand.R'].index
bmesh.ops.delete(mesh, geom=[v for v in mesh.verts if v[skin].get(right, 0) > .5], context='VERTS')
mesh.to_mesh(santa.data)
mesh.free()

porcelain = material('White porcelain bowl', 'F6F4EF', .14, coat=.7)
broth = material('Rich noodle broth', 'B8561E', .12, coat=.6)
oil = material('Chilli oil', 'E0451A', .1, coat=.8)
noodle = material('Rice noodles', 'F2E6C4', .35, sheen=.2)
mince = material('Braised pork mince', '6A3417', .55)
cilantro = material('Cilantro', '3E8E2A', .45)
scallion = material('Scallion', '7DB548', .45)
gold_ink = material('Yunqueen gold', 'F3A818', .35)
dark_ink = material('Yunqueen brown outline', '45200B', .5)
white_ink = material('Rice Noodles white', 'FFFFFF', .4)
vapour = material('Noodle_steam', 'F1EEE8', .9, alpha=.12)
plush = recolor('Ivory_plush_fur', 'Duck yellow plush', 'FAD51C', .16)
bill = material('Duck bill', 'E3361B', .55)
bill_dark = material('Duck lower bill', 'C42A15', .6)
feet = material('Duck feet', 'E9461E', .55, sheen=.3)
eye_white = material('Duck eye whites', 'FBFBF7', .3)
pupil = material('Duck pupils', '1A1A1A', .25)

# ---------------------------------------------------------------- the Yunqueen bowl of rice noodles
WALL = [(0, .084), (.012, .090), (.020, .100), (.060, .145), (.120, .188), (.180, .216), (.232, .229)]


def wall(z):
    for (z0, r0), (z1, r1) in zip(WALL, WALL[1:]):
        if z <= z1:
            return r0 + (r1 - r0) * (z - z0) / (z1 - z0)
    return WALL[-1][1]


rnd = random.Random(6)
with bound('bowl'), place(*FOOT):
    profile([(z, r, r) for z, r in WALL] + [(.242, .232, .232), (.246, .226, .226), (.238, .218, .218),
                                            (.180, .204, .204), (.100, .158, .158), (.040, .100, .100),
                                            (.028, .080, .080)], porcelain, n=64)
    label('Yunqueen', gold_ink, around(wall, .168, lift=.002), .27, bold=.04, outline=(dark_ink, .06), step=.0015)
    label('Rice Noodles', white_ink, around(wall, .120, lift=.002), .20, bold=.03, outline=(dark_ink, .07),
          step=.0015)
    profile([(BROTH - .004, .207, .207), (BROTH, .209, .209)], broth, n=48)
    for _ in range(14):
        a, r = rnd.uniform(0, TAU), rnd.uniform(.03, .18)
        with place(r * math.cos(a), r * math.sin(a), BROTH + .0006):
            profile([(0, .010, .010), (.0008, .009, .009)], oil, n=10)
    # Noodles: loose arcs heaped toward the middle, tucked under the broth at their ends.
    for k in range(40):
        a = rnd.uniform(0, TAU)
        r0 = rnd.uniform(.02, .16)
        sweep = rnd.uniform(.9, 2.2) * rnd.choice((-1, 1))
        lift = rnd.uniform(.004, .028)
        bulge, wave, phase = rnd.uniform(.02, .05), rnd.uniform(.004, .008), rnd.uniform(0, TAU)
        path = []
        for j in range(36):
            t = j / 35
            rr = min(.195, r0 + bulge * math.sin(math.pi * t) + wave * math.sin(5 * math.pi * t + phase))
            aa = a + sweep * t
            path.append((rr * math.cos(aa), rr * math.sin(aa),
                         BROTH + .002 + lift * math.sin(math.pi * t) * (1 - rr / .25)))
        cord(path, .0042, noodle, sides=6)
    # Savoury pork mince heaped in the centre, topped with cilantro and scallion.
    for k in range(130):
        a, r = rnd.uniform(0, TAU), .058 * math.sqrt(rnd.random())
        h = .040 * (1 - (r / .062) ** 2)
        s = rnd.uniform(.0055, .0085)
        ellipsoid(r * math.cos(a) - .01, r * math.sin(a) - .015, BROTH + .010 + h * rnd.uniform(.5, 1),
                  s * rnd.uniform(.8, 1.3), s, s * .8, mince, 6, 3)
    for k in range(9):
        a = TAU * k / 9 + rnd.uniform(-.3, .3)
        r = rnd.uniform(.03, .10)
        with place(r * math.cos(a) - .01, r * math.sin(a) - .015, BROTH + .03 + .02 * (1 - r / .1), yaw=math.degrees(a),
                   tilt=rnd.uniform(-30, 30)):
            for lobe in range(3):
                with place(yaw=lobe * 120):
                    sheet([[(-.009 * math.sin(math.pi * t), .022 * t, .002 * math.sin(math.pi * t)),
                            (0, .022 * t, .004 * math.sin(math.pi * t)),
                            (.009 * math.sin(math.pi * t), .022 * t, .002 * math.sin(math.pi * t))]
                           for t in [j / 4 for j in range(5)]], cilantro)
    for k in range(12):
        a, r = rnd.uniform(0, TAU), rnd.uniform(.06, .16)
        with place(r * math.cos(a), r * math.sin(a), BROTH + .012, tilt=rnd.uniform(-40, 40), yaw=rnd.uniform(0, 360)):
            cord([(.008 * math.cos(TAU * j / 10), .008 * math.sin(TAU * j / 10), 0) for j in range(11)], .0025,
                 scallion, sides=4)
with bound('steam'):
    steam(FOOT.x, FOOT.y, FOOT.z + BROTH + .01, 6, .30, .028, vapour, 6)

# ---------------------------------------------------------------- bamboo chopsticks and the noodles they lift
bamboo = material('Bamboo chopsticks', 'D8B57A', .45, coat=.3)
band = material('Chopstick red band', 'B3202A', .35, coat=.5)
leather = bpy.data.materials['Brown_glove_leather']
kit.TILE[leather] = .20


def smooth(points, n=6):
    """A Catmull-Rom curve through `points`, n samples per span."""
    p = [Vector(q) for q in points]
    p = [2 * p[0] - p[1]] + p + [2 * p[-1] - p[-2]]
    out = []
    for i in range(1, len(p) - 2):
        a, b, c, d = p[i - 1:i + 3]
        for k in range(n):
            t = k / n
            out.append(.5 * (2 * b + (c - a) * t + (2 * a - 5 * b + 4 * c - d) * t * t + (3 * b - a - 3 * c + d) * t ** 3))
    return out + [p[-2]]


def finger(points, base, tip):
    path = smooth(points)
    cord(path, base, leather, [1 - (1 - tip / base) * (k / (len(path) - 1)) ** 1.5 for k in range(len(path))],
         sides=12)


with place(*WRIST_R):
    for bone, top, direction, length in (('sticks', LOWER_TOP, LOWER_DIR, LENGTH),
                                         ('stick', UPPER_TOP, UPPER_DIR, (TIPS - UPPER_TOP).length)):
        with bound(bone):
            tip = top + direction * length
            cord([top.lerp(tip, k / 8) for k in range(9)], .0042, bamboo, [1, .97, .92, .86, .78, .70, .61, .52, .42],
                 sides=8)
            cord([top.lerp(tip, k / 40) for k in (0, 1, 2)], .0046, band, sides=8)
    with bound('hand.R'):
        # Back of the hand and palm, flatter than the cupped gloves.
        ellipsoid(.052, 0, -.004, .056, .048, .030, leather, 24, 14)
        # Index on top of the upper stick, middle fingertip beside it, ring fingertip under the lower stick,
        # little finger curled beneath; the thumb tip presses the upper stick against them.
        finger([(.082, .032, .010), (.116, .036, .010), (.138, .030, .002), (.146, .022, -.012)], .0155, .0105)
        finger([(.088, .010, .004), (.124, .010, -.004), (.146, .006, -.022), (.150, .004, -.038)], .0160, .0105)
        finger([(.085, -.012, -.002), (.116, -.014, -.018), (.130, -.012, -.040), (.128, -.009, -.060)], .0150, .0100)
        finger([(.076, -.030, -.008), (.100, -.033, -.026), (.108, -.030, -.044), (.100, -.026, -.056)], .0130, .0090)
        finger([(.018, .040, -.012), (.052, .066, -.016), (.088, .068, -.014), (.112, .050, -.018)], .0190, .0115)

with bound('noodle.00'), place(*NOODLES):
    rnd = random.Random(66)
    strands = []
    for k in range(6):
        a = TAU * k / 6 + rnd.uniform(-.3, .3)
        spread = rnd.uniform(.003, .006)
        phase, kink = rnd.uniform(0, TAU), rnd.uniform(.003, .005)
        strands.append((a, spread, phase, kink, rnd.uniform(.80, 1.0)))
    for a, spread, phase, kink, reach in strands:
        offset = len(kit.verts)
        last = max(2, round(reach * (LINKS - 1)))
        rows = []
        for j in range(last + 1):
            # Strands leave the chopstick tips together and fan out a little as they hang; rice noodles are wavy.
            r = spread * (1 + 2.2 * j / LINKS)
            centre = Vector((r * math.cos(a) + kink * math.sin(1.7 * j + phase),
                             r * math.sin(a) + kink * math.cos(1.3 * j + phase), -j * LINK))
            rows.append([centre + Vector((.0042 * math.cos(TAU * i / 6), .0042 * math.sin(TAU * i / 6), 0))
                         for i in range(6)])
        rings(rows, noodle)
        for j in range(last + 1):
            for i in range(6):
                kit.bones[offset + j * 6 + i] = f'noodle.{j:02d}'

# ---------------------------------------------------------------- the yellow duck
BODY = [(.10, .06), (.12, .15), (.18, .205), (.28, .228), (.38, .22), (.46, .232), (.56, .262), (.66, .278),
        (.76, .262), (.84, .214), (.90, .145), (.935, .065), (.945, .01)]


def girth(z):
    for (z0, r0), (z1, r1) in zip(BODY, BODY[1:]):
        if z <= z1:
            return r0 + (r1 - r0) * (z - z0) / (z1 - z0)
    return .01


with bound('duck'), place(*DUCK, yaw=-8):
    profile([(z, r, r * .9) for z, r in BODY], plush, n=48)
    # Bill: a broad upper bill over a smaller lower one.
    ellipsoid(0, -.262, .588, .135, .090, .046, bill, 32, 12)
    ellipsoid(0, -.240, .538, .108, .070, .034, bill_dark, 28, 10)
    # Deadpan eyes: whites with a heavy lid line and pupils glancing toward Santa.
    for side in (-1, 1):
        x = side * .088
        front = -girth(.70) * .9 * math.sqrt(max(0, 1 - (x / girth(.70)) ** 2))
        with place(x, front + .012, .705, yaw=side * 20):
            ellipsoid(0, 0, 0, .062, .022, .036, eye_white, 24, 10)
            ellipsoid(0, .004, .016, .068, .024, .022, plush, 24, 8)
            cord([(-.060 + .12 * j / 10, -.019 - .004 * math.sin(math.pi * j / 10), .006 - .004 * math.sin(math.pi * j / 10))
                  for j in range(11)], .0028, pupil, sides=5)
            ellipsoid(-.030, -.019, -.006, .012, .006, .011, pupil, 12, 6)
    # Two red head feathers curling outward.
    for side in (-1, 1):
        cord([(side * .012, 0, .915), (side * .030, -.008, .975), (side * .065, -.010, 1.012), (side * .098, -.008, 1.004),
              (side * .110, -.006, .980)], .030, bill, [1, 1, .95, .8, .45], sides=12)
    # Stubby wings and webbed feet.
    for side in (-1, 1):
        with place(side * .222, -.01, .42, tilt=-side * 16, yaw=side * 8):
            ellipsoid(0, 0, 0, .045, .085, .125, plush, 20, 10)
        cord([(side * .075, -.01, .02), (side * .075, -.01, .13)], .03, feet, sides=10)
        with place(side * .08, -.07, .022, yaw=side * 12):
            for toe in (-1, 0, 1):
                with place(toe * .028, -.02, 0, yaw=-toe * 14):
                    ellipsoid(0, -.04, 0, .026, .065, .022, feet, 16, 8)


# ---------------------------------------------------------------- six-second loop
CAMERA = Vector((0, -3.2, 1.6))
FRAMES = 6 * 24 + 1
TILT = turn(10, 'X')                   # the bowl's top tipped a little toward the viewer
# Chopstick tip positions on the bowl (from the foot ring) and stick directions (tips toward grip).
DIP = Vector((-.04, -.02, BROTH + .004))           # where the tips pinch the noodles
POISE = DIP + Vector((-.02, -.01, .10))            # resting just above the bowl
LIFTED = DIP + Vector((-.02, -.05, .20))           # noodles held up above the bowl to admire, not to eat
ANCHOR = Vector((.05, .05, BROTH + .002))          # where the lifted strands still trail into the broth
LOW_DIR = Vector((-.83, .46, .32)).normalized()      # from the tips back up the chopsticks
HIGH_DIR = Vector((-.80, .46, .40)).normalized()
OPEN = 7                                           # degrees the upper stick opens
BACK = Vector((-.61, -.61, .51)).normalized()      # back of the right hand out and up, thumb on top


def aligned(a, b, a_to, b_to):
    """The rotation taking direction a to a_to, with b turned as near to b_to as that allows."""
    def basis(x, y):
        x = x.normalized()
        y = (y - x * y.dot(x)).normalized()
        return Matrix((x, y, x.cross(y))).transposed()
    return basis(a_to, b_to) @ basis(a, b).transposed()


def on_bowl(centre, tilt, p):
    return centre + tilt @ (FOOT + p - CENTRE)


def blend(t, poise, dip, lifted):
    """Poise above the bowl, dip in and pinch, lift, lower back in, release and return to poise."""
    a, b, c, d = ramp(t, .06, .20), ramp(t, .30, .50), ramp(t, .70, .82), ramp(t, .88, 1)
    value = poise.lerp(dip, a).lerp(lifted, b).lerp(dip, c).lerp(poise, d)
    return value, b * (1 - c), a * (1 - d)


def chain(t, top, anchor, rest, hang):
    """Points along the noodle bundle from the chopstick tips (s = 0) to where it trails into the broth."""
    sway = math.sin(TAU * 3 * t) * hang
    side = (anchor - rest).cross(Vector((0, 0, 1))).normalized()
    points = []
    for j in range(LINKS):
        s = j / (LINKS - 1)
        # Lying in the bowl: a loose curl over the broth between the two ends.
        lying = rest.lerp(anchor, s) + side * .05 * math.sin(math.pi * s)
        # Hanging: straight down from the tips at first, then curving away into the broth.
        hanging = top.lerp(anchor, s)
        hanging.xy = (top + (anchor - top) * s * s).xy
        hanging += side * .014 * math.sin(math.pi * s) * sway
        points.append(lying.lerp(hanging, hang))
    return points


def pose_at(t):
    tip_at, lifted, engaged = blend(t, POISE, DIP, LIFTED)
    pinch = ramp(t, .20, .26) * (1 - ramp(t, .82, .86))
    centre = CENTRE + Vector((0, 0, .02)) * lifted
    rigid('bowl', centre, TILT)
    hold('L', centre + TILT @ Vector((SPAN, -.02, 0)), TILT)
    # Right glove: turned so the chopsticks point down into the bowl with the back of the hand up and out;
    # the arm then reaches to wherever that puts the wrist.
    bounce = Vector((0, 0, .008 * math.sin(TAU * 2 * t))) * lifted
    tip = on_bowl(centre, TILT, tip_at) + bounce
    direction = LOW_DIR.lerp(HIGH_DIR, lifted).normalized()
    spin = aligned(LOWER_DIR, Vector((0, 0, 1)), -direction, BACK)
    wrist = tip - spin @ TIPS
    kit.reach('R', wrist)
    rigid('hand.R', wrist, spin)
    rigid('sticks', wrist + spin @ WEB, spin)
    rigid('stick', wrist + spin @ PIVOT, spin @ Matrix.Rotation(-math.radians(OPEN) * (1 - pinch), 3, HINGE_AXIS))
    # The noodles follow the tips once pinched; otherwise they lie curled in the broth.
    rest = on_bowl(centre, TILT, DIP)
    top = rest.lerp(tip, pinch)
    anchor = on_bowl(centre, TILT, ANCHOR)
    hang = max(0, min(1, (top - rest).length / .08))
    points = chain(t, top, anchor, rest, hang)
    for j, p in enumerate(points):
        tangent = points[min(j + 1, LINKS - 1)] - points[max(j - 1, 0)]
        rigid(f'noodle.{j:02d}', p, Vector((0, 0, -1)).rotation_difference(tangent).to_matrix())
    k = rig.pose.bones['steam']
    k.scale = (.8, .85 * (1 + .07 * math.sin(TAU * 3 * t)), .8)
    k.rotation_quaternion = turn(7 * math.sin(TAU * 2 * t), 'Z').to_quaternion()
    # He watches the chopsticks dip in and lift the noodles up, then looks back to the viewer.
    target = CAMERA.lerp(tip, .35 + .65 * engaged)
    look(target, math.radians(3) * lifted)
    aim_eyes(target)
    # The duck sways happily beside him.
    rigid('duck', DUCK + Vector((0, 0, .012 * abs(math.sin(TAU * 2 * t)))),
          turn(5 * math.sin(TAU * 2 * t), 'Y') @ turn(-6 * lifted, 'Z'))


kit.attach('Yunqueen props')
kit.bake('Santa06_Noodle_Chopsticks', FRAMES, pose_at,
         ['bowl', 'steam', 'duck', 'sticks', 'stick', 'head', 'eye.L', 'eye.R'] +
         [f'noodle.{j:02d}' for j in range(LINKS)] +
         [f'{n}.{s}' for s in 'LR' for n in ('upper_arm', 'forearm', 'hand')])
FRONT = ((.14, -5.85, 1.98), (.14, -.03, 1.06), 77, (800, 900))
LIFT_FRAME = round(.6 * (FRAMES - 1)) + 1
CLOSE = ((-.25, -1.75, 1.85), (-.01, -.53, 1.55), 58, (640, 640))
kit.finish('santa06', FRONT, [
    ('front', 1, FRONT),
    ('lift', LIFT_FRAME, FRONT),
    ('chopsticks', LIFT_FRAME, CLOSE),
    ('grip', LIFT_FRAME, ((-.75, -1.05, 1.62), (-.10, -.47, 1.45), 75, (640, 640))),
    ('pinch', round(.24 * (FRAMES - 1)) + 1, ((-.30, -1.20, 1.70), (-.05, -.50, 1.38), 70, (640, 640))),
    ('bowl', 1, CLOSE),
    ('duck', 1, ((.95, -2.4, .80), (.70, -.24, .55), 58, (640, 640))),
])
