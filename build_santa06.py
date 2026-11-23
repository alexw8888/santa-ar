"""Build the Yunqueen edition from the base character made by build_santa_base.py.

blender -b --factory-startup --python-exit-code 1 -P build_santa06.py -- previews
The optional directory receives front, aroma, bowl and duck previews and the page poster.
"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mathutils import Vector  # noqa: E402

import santa_kit as kit  # noqa: E402
from santa_kit import (TAU, aim_eyes, around, bound, cord, ellipsoid, hold, label, look,  # noqa: E402
                       material, place, profile, ramp, recolor, rigid, sheet, steam, turn)

FOOT = Vector((-.03, -.53, 1.34))      # centre of the bowl's foot ring
CENTRE = FOOT + Vector((0, 0, .08))    # both gloves wrap the lower bowl either side of this point
SPAN = .150
BROTH = .196
DUCK = Vector((.70, -.24, 0))
kit.start(6, 'Yunqueen', 'photos/06 Yunqueen Santa.jpg', [
    ('bowl', CENTRE, CENTRE + Vector((0, 0, .2)), 'root'),
    ('steam', FOOT + Vector((0, 0, BROTH)), FOOT + Vector((0, 0, BROTH + .2)), 'bowl'),
    ('duck', DUCK, DUCK + Vector((0, 0, .3)), 'root'),
])
rig = kit.rig

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


# ---------------------------------------------------------------- five-second loop
CAMERA = Vector((0, -3.2, 1.6))


def pose_at(t):
    lift = ramp(t, .14, .34) * (1 - ramp(t, .66, .86))
    inhale = math.sin(math.pi * ramp(t, .36, .64)) * lift
    centre = CENTRE + Vector((0, .03, .05)) * lift
    tilt = turn(5 - 10 * lift, 'X')
    rigid('bowl', centre, tilt)
    for side, sign in (('L', 1), ('R', -1)):
        hold(side, centre + tilt @ Vector((sign * SPAN, -.02, 0)), tilt)
    k = rig.pose.bones['steam']
    k.scale = (.65 + .35 * lift, (.6 + .4 * lift) * (1 + .07 * math.sin(TAU * 3 * t)), .65 + .35 * lift)
    k.rotation_quaternion = turn(7 * math.sin(TAU * 2 * t), 'Z').to_quaternion()
    soup = centre + tilt @ Vector((0, 0, BROTH - .06))
    target = CAMERA.lerp(soup, .35 + .65 * lift)
    look(target, math.radians(5) * inhale)
    aim_eyes(target)
    # The duck sways happily beside him.
    rigid('duck', DUCK + Vector((0, 0, .012 * abs(math.sin(TAU * 2 * t)))),
          turn(5 * math.sin(TAU * 2 * t), 'Y') @ turn(-6 * lift, 'Z'))


kit.attach('Yunqueen props')
kit.bake('Santa06_Noodle_Aroma', 121, pose_at,
         ['bowl', 'steam', 'duck', 'head', 'eye.L', 'eye.R'] +
         [f'{n}.{s}' for s in 'LR' for n in ('upper_arm', 'forearm', 'hand')])
FRONT = ((.14, -5.85, 1.98), (.14, -.03, 1.06), 77, (800, 900))
kit.finish('santa06', FRONT, [
    ('front', 1, FRONT),
    ('aroma', 61, FRONT),
    ('bowl', 1, ((-.10, -1.55, 1.95), (-.03, -.53, 1.50), 62, (640, 640))),
    ('duck', 1, ((.95, -2.4, .80), (.70, -.24, .55), 58, (640, 640))),
])
