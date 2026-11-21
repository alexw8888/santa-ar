"""Build the Bouquet Cafe edition from the packed character made by build_santa01.py.

blender -b --factory-startup --python-exit-code 1 -P build_santa03.py -- previews
The optional directory receives front, aroma, mug and bouquet previews and the page poster.
"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mathutils import Vector  # noqa: E402

import santa_kit as kit  # noqa: E402
import santa_flowers as fl  # noqa: E402
from santa_kit import (TAU, around, bound, cord, hold, label, look, aim_eyes, material, place,  # noqa: E402
                       profile, ramp, rigid, steam, turn)

MUG = Vector((.06, -.47, 1.36))       # mug axis, half way up; held in the left glove
BOUQUET = Vector((-.33, -.42, 1.38))  # stem bundle inside the right fist
LEAN = -14                            # the bouquet leans out to Santa's right
SACK = Vector((.70, .22, 0))
MUG_SCALE = 1.42                      # a big cafe mug, as wide as the glove
PALM = Vector((.022, 0, 0))           # the glove wraps the mug's handle side
kit.start(3, 'BouquetCafe', 'photos/03 Bouquet Cafe Santa.jpg', [
    ('mug', MUG, MUG + Vector((0, 0, .12)), 'root'),
    ('steam', MUG + Vector((0, 0, .07)), MUG + Vector((0, 0, .22)), 'mug'),
    ('bouquet', BOUQUET, BOUQUET + Vector((0, 0, .15)), 'root'),
])

ceramic = material('Glazed white ceramic', 'F3F0EA', .16, coat=.6)
burgundy = material('Bouquet Cafe burgundy', '8A1A2C', .4)
coffee = material('Fresh coffee', '3A2013', .12)
vapour = material('Coffee_steam', 'EEE9E2', .9, alpha=.16)
m = fl.palette()

# ---------------------------------------------------------------- mug with the Bouquet Cafe mark
R, H = .046, .052
with bound('mug'), place(*MUG, scale=MUG_SCALE):
    profile([(-H, R - .006, R - .006), (-H + .004, R - .001, R - .001), (-H + .012, R, R), (H - .004, R, R),
             (H, R - .0015, R - .0015), (H - .001, R - .0045, R - .0045), (H - .012, R - .0050, R - .0050),
             (-H + .012, R - .0055, R - .0055)], ceramic, n=48)
    profile([(H - .016, R - .0052, R - .0052), (H - .015, R - .0052, R - .0052)], coffee, n=48)
    # Handle loops through the palm of the glove (+X).
    cord([(R - .004 + .034 * math.sin(math.pi * k / 12) ** .8, 0, .030 * math.cos(math.pi * k / 12))
          for k in range(13)], .0065, ceramic, sides=8)
    label('BOUQUET', burgundy, around(R, -.004, spin=-.42), .066, bold=.02)
    label('CAFE', burgundy, around(R, -.020, spin=-.42), .031, bold=.02)
    # Lotus emblem: a tall centre petal, two side petals and two low outer petals over a base arc.
    lotus = around(R, .022, spin=-.42)
    for cx, w, h, lean in ((0, .0062, .016, 0), (-.0085, .0058, .012, -.35), (.0085, .0058, .012, .35),
                           (-.0150, .0050, .0075, -.8), (.0150, .0050, .0075, .8)):
        path = []
        for k in range(15):
            s = math.pi * k / 14
            u = -w * math.cos(s)
            v = h * math.sin(s) ** 1.6
            path.append(lotus(cx + u * math.cos(lean) + v * math.sin(lean), -.008 + v * math.cos(lean) - u * math.sin(lean) * .4))
        cord(path, .0009, burgundy, sides=4)
    cord([lotus(.018 * (k / 8 - .5) * 2, -.0095 - .002 * math.sin(math.pi * k / 8)) for k in range(9)], .0009, burgundy,
         sides=4)
with bound('steam'):
    steam(MUG.x, MUG.y, MUG.z + MUG_SCALE * H - .012, 4, .27, .022, vapour, 3)

# ---------------------------------------------------------------- hand bouquet
with bound('bouquet'), place(*BOUQUET, tilt=LEAN):
    rnd = random.Random(33)
    kinds = [(rnd.choice(['red', 'red', 'pink', 'pink', 'yellow', 'orange', 'tulip_pink', 'aster', 'aster', 'sun',
                          'gyp']), rnd.uniform(.058, .068)) for _ in range(46)]
    fl.arrangement((0, 0, .29), .19, 102, kinds, m, 31, stems_to=((0, 0, .075), (0, 0, -.19), .05),
                   spikes=10, leaves=12, spike_length=.21, leaf_size=1.5)
    # Raffia tie just above the fist.
    cord([(.037 * math.cos(TAU * k / 16), .037 * math.sin(TAU * k / 16), .078) for k in range(17)], .005,
         material('Raffia tie', 'C9A56A', .8), sides=6)

# ---------------------------------------------------------------- velvet sack brimming with flowers
velvet = kit.bpy.data.materials['Crimson_velvet']
kit.TILE[velvet] = .36
rnd = random.Random(3)
bulges = [rnd.uniform(0, TAU) for _ in range(4)]


def slump(a, z):
    return 1 + .07 * math.sin(3 * a + bulges[0]) * math.sin(math.pi * min(1, z / .5)) + .04 * math.cos(5 * a + bulges[1])


with place(*SACK, yaw=-15, scale=1.3):
    profile([(.004, .12, .11), (.02, .25, .23), (.08, .31, .29), (.18, .33, .31), (.30, .31, .29), (.40, .26, .25),
             (.47, .215, .205), (.51, .20, .19), (.56, .23, .215), (.60, .255, .235), (.62, .25, .23)],
            velvet, n=40, close=False, wobble=slump, two_sided=True)
    # Two soft folds where the sack gathers under its load.
    for a in (.5, 2.6, 4.4):
        cord([((.30 - .1 * k / 4) * math.cos(a), (.28 - .1 * k / 4) * math.sin(a), .12 + .09 * k) for k in range(5)],
             .012, velvet, [.3, .9, 1, .9, .3])
    fl.arrangement((0, 0, .64), .20, 90, kinds[:38], m, 77, spikes=9, leaves=12, spike_length=.17)


# ---------------------------------------------------------------- six-second loop
CAMERA = Vector((-.05, -3.2, 1.55))


def pose_at(t):
    lift = ramp(t, .12, .32) * (1 - ramp(t, .70, .90))
    inhale = math.sin(math.pi * ramp(t, .34, .66)) * lift
    mug = MUG + Vector((-.03, .04, .15)) * lift
    tilt = turn(-9 * lift, 'X')
    rigid('mug', mug, tilt)
    hold('L', mug + tilt @ PALM, tilt)
    k = rig.pose.bones['steam']
    k.scale = (.6 + .4 * lift, (.55 + .45 * lift) * (1 + .08 * math.sin(TAU * 3 * t)), .6 + .4 * lift)
    k.rotation_quaternion = turn(6 * math.sin(TAU * 2 * t), 'Z').to_quaternion()
    sway = turn(5 * math.sin(TAU * t), 'Y') @ turn(3 * math.sin(TAU * 2 * t + .6), 'X')
    bunch = BOUQUET + Vector((0, 0, .012 * math.sin(TAU * 2 * t)))
    rigid('bouquet', bunch, sway)
    hold('R', bunch, sway @ turn(LEAN, 'Y'))
    target = CAMERA.lerp(mug + Vector((0, 0, .06)), lift)
    look(target, math.radians(4) * inhale)
    aim_eyes(target)


rig = kit.rig
kit.attach('Bouquet Cafe props')
kit.bake('Santa03_Coffee_and_Flowers', 145, pose_at,
         ['mug', 'steam', 'bouquet', 'head', 'eye.L', 'eye.R'] +
         [f'{n}.{s}' for s in 'LR' for n in ('upper_arm', 'forearm', 'hand')])
FRONT = ((.12, -5.85, 1.98), (.10, -.03, 1.06), 77, (800, 900))
kit.finish('santa03', FRONT, [
    ('front', 1, FRONT),
    ('aroma', 73, FRONT),
    ('mug', 1, ((.30, -1.45, 1.50), (.06, -.48, 1.38), 80, (640, 640))),
    ('bouquet', 1, ((-.70, -2.1, 1.85), (-.40, -.42, 1.62), 62, (640, 640))),
])
