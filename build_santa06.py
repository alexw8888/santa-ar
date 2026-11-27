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
from mathutils import Matrix, Quaternion  # noqa: E402

import santa_kit as kit  # noqa: E402
from santa_kit import (TAU, aim_eyes, around, bound, cord, decal, ellipsoid, hold, look,  # noqa: E402
                       material, place, profile, ramp, recolor, rigid, rings, sheet, steam, turn)

FOOT = Vector((.12, -.52, 1.12))       # centre of the bowl's foot ring
CENTRE = FOOT + Vector((0, 0, .08))    # the left glove wraps the bowl's side level with this point
BOWL_GRIP = Vector((.177, -.02, 0))   # cupped glove rests against the outside of the wall
BROTH = .196
DUCK = Vector((.70, -.24, 0))
DUCK_YAW = Matrix.Rotation(math.radians(-8), 3, 'Z')
DUCK_HEAD = DUCK + Vector((0, 0, .48))
WING_PIVOTS = {side: DUCK + DUCK_YAW @ Vector((sign*.208, -.01, .50))
               for side, sign in (('L', 1), ('R', -1))}
FEATHER_PIVOT = DUCK + Vector((0, 0, .915))

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
    ('duck_head', DUCK_HEAD, DUCK_HEAD + Vector((0, 0, .18)), 'duck'),
    ('duck_feathers', FEATHER_PIVOT, FEATHER_PIVOT + Vector((0, 0, .09)), 'duck_head'),
    *[(f'duck_wing.{side}', pivot, pivot + Vector((0, 0, -.10)), 'duck')
      for side, pivot in WING_PIVOTS.items()],
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
emblem = porcelain.copy()
emblem.name = 'Yunqueen emblem'
emblem_nodes = emblem.node_tree
emblem_texture = emblem_nodes.nodes.new('ShaderNodeTexImage')
emblem_texture.image = bpy.data.images.load(str(kit.ROOT / 'assets/yunqueen-emblem.png'))
emblem_texture.image.name = 'yunqueen-emblem'
emblem_texture.image.pack()
emblem_shader = emblem_nodes.nodes['Principled BSDF']
emblem_nodes.links.new(emblem_texture.outputs['Color'], emblem_shader.inputs['Base Color'])
emblem_nodes.links.new(emblem_texture.outputs['Alpha'], emblem_shader.inputs['Alpha'])
broth = material('Rich noodle broth', 'B8561E', .12, coat=.6)
oil = material('Chilli oil', 'E0451A', .1, coat=.8)
noodle = material('Rice noodles', 'F2E6C4', .35, sheen=.2)
mince = material('Braised pork mince', '6A3417', .55)
cilantro = material('Cilantro', '3E8E2A', .45)
scallion = material('Scallion', '7DB548', .45)
vapour = material('Noodle_steam', 'F1EEE8', .9, alpha=.12)
plush = recolor('Ivory_plush_fur', 'Duck yellow plush', 'FFDA65', .16)
bill = material('Duck bill', 'FF984F', .55)
feather_red = material('Duck red feathers', 'E3361B', .55)
bill_dark = material('Duck lower bill', 'C42A15', .6)
feet = material('Duck feet', 'E9461E', .55, sheen=.3)
eye_white = material('Duck eye whites', 'FBFBF7', .3)
pupil = material('Duck pupils', '3A2218', .25)
blush = material('Duck blush', 'F7A7B0', .38)

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
    width, height = emblem_texture.image.size
    decal(around(wall, .139, lift=.001), .170 * width / height, .170, emblem, rows=40)
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
    # Continuous plush silhouette: head and body share a connected neck surface.
    body_start = len(kit.verts)
    profile([(z, r, r * .9) for z, r in BODY], plush, n=48)
    body_end = len(kit.verts)
    # Assign the upper section to the head bone; adjacent rings remain connected.
    for i in range(body_start, body_end):
        if kit.verts[i][2] >= .56:
            kit.bones[i] = 'duck_head'
    with bound('duck_head'):
        # A single compact orange bill, with tiny nostrils like the reference.
        ellipsoid(0, -.245, .625, .079, .057, .048, bill, 32, 16)
        for side in (-1, 1):
            ellipsoid(side * .015, -.298, .641, .006, .0035, .008, pupil, 16, 8)
        for side in (-1, 1):
            # Small flush pink cheeks, placed outside and below the eyes.
            x, z = side * .153, .642
            front = -girth(z) * .9 * math.sqrt(1 - (x / girth(z)) ** 2)
            with place(x, front, z, yaw=side * 24):
                ellipsoid(0, 0, 0, .035, .009, .022, blush, 24, 12)
            # Dark button eyes directly on the yellow face: no white sclera.
            x, z = side * .122, .725
            front = -girth(z) * .9 * math.sqrt(1 - (x / girth(z)) ** 2)
            with place(x, front - .006, z, yaw=side * 22):
                ellipsoid(0, 0, 0, .039, .021, .043, pupil, 32, 16)
                ellipsoid(-.012, -.019, .014, .010, .0045, .010, eye_white, 20, 12)
                ellipsoid(.009, -.020, -.010, .0045, .003, .0045, eye_white, 16, 8)
    with bound('duck_feathers'):
        for side in (-1, 1):
            cord([(side * .012, 0, .915), (side * .030, -.008, .975), (side * .065, -.010, 1.012), (side * .098, -.008, 1.004),
                  (side * .110, -.006, .980)], .030, feather_red, [1, 1, .95, .8, .45], sides=12)
    for side, name in ((-1, 'R'), (1, 'L')):
        with bound('duck_wing.' + name), place(side * .222, -.01, .42, tilt=-side * 16, yaw=side * 8):
            ellipsoid(0, 0, 0, .045, .085, .125, plush, 20, 10)
        # Feet and legs remain fixed to the ground; no bouncing root.
        cord([(side * .075, -.01, .02), (side * .075, -.01, .13)], .03, feet, sides=10)
        with place(side * .08, -.07, .022, yaw=side * 12):
            for toe in (-1, 0, 1):
                with place(toe * .028, -.02, 0, yaw=-toe * 14):
                    ellipsoid(0, -.04, 0, .026, .065, .022, feet, 16, 8)


# ---------------------------------------------------------------- twelve-second loop
CAMERA = Vector((0, -3.2, 1.6))
FRAMES = 12 * 24 + 1
kit.santa_motion.BODY_TILT_DEG = 4.0
kit.santa_motion.CLOTHING_SWAY_DEG = 4.0
kit.santa_motion.FOOT_ADJUST_DEG = 1.4
kit.santa_motion.HAT_FOLLOW_DEG = 4.0
TILT = turn(10, 'X')                   # the bowl's top tipped a little toward the viewer
# Chopstick tip positions on the bowl (from the foot ring) and stick directions (tips toward grip).
DIP = Vector((-.04, -.02, BROTH + .004))           # where the tips pinch the noodles
POISE = DIP + Vector((-.02, -.01, .10))            # resting just above the bowl
LIFTED = DIP + Vector((-.02, -.05, .20))           # noodles held up above the bowl to admire, not to eat
ANCHOR = Vector((.05, .05, BROTH + .002))          # where the lifted strands still trail into the broth
LOW_DIR = Vector((-.83, .46, .32)).normalized()      # from the tips back up the chopsticks
HIGH_DIR = Vector((-.80, .46, .40)).normalized()
DIP_DIR = Vector((-.60, .35, .75)).normalized()
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


def ease(t, a, b):
    u = max(0., min(1., (t-a)/(b-a)))
    return u**3 * (10 + u*(-15 + 6*u))


def pulse(t, a, b, c, d):
    return ease(t,a,b)*(1-ease(t,c,d))


def activity(t):
    return pulse(t, .10, .25, .78, .94)


def blend(t, poise, dip, lifted):
    a = ease(t, .125, .23)
    b = ease(t, .267, .433)
    c = ease(t, .708, .858)
    d = ease(t, .90, .98)
    value = poise.lerp(dip,a).lerp(lifted,b).lerp(dip,c).lerp(poise,d)
    # A tiny search in the broth, ending before the chopsticks close.
    search = pulse(t,.17,.19,.21,.245)
    value += Vector((.012*search, -.006*search, .002*search))
    return value, b*(1-c), a*(1-d)


def chain(t, top, anchor, rest, hang):
    side = (anchor-rest).cross(Vector((0,0,1))).normalized()
    # A damped response to the lift and return, rather than a constant swing.
    elapsed = max(0., (t-.267)*12)
    swing = math.sin(2*math.pi*.9*elapsed)*math.exp(-1.1*elapsed)
    lowering = pulse(t,.708,.76,.82,.858)
    points = []
    for j in range(LINKS):
        u = j/(LINKS-1)
        lying = rest.lerp(anchor,u) + side*.045*math.sin(math.pi*u)
        hanging = top.lerp(anchor,u)
        hanging.xy = (top+(anchor-top)*u*u).xy
        lag = math.sin(2*math.pi*.9*elapsed-1.8*u)*math.exp(-1.1*elapsed)
        hanging += side * (.012*(.35*swing+.65*lag)+.009*lowering) * math.sin(math.pi*u)
        point = lying.lerp(hanging,hang)
        # Keep the upper strand attached to the chopstick tips even at low lift.
        point += (top-rest)*(1-hang)*(1-u)**3
        points.append(point)
    return points


def reachable_centre(centre, tilt, tip_offset, spin):
    # Keep both hands and their props synchronized if the base rig limits reach.
    offsets = {'L': tilt @ (BOWL_GRIP-kit.GRIP['L']),
               'R': tip_offset-spin@TIPS}
    constraints = []
    for side, offset in offsets.items():
        upper = rig.data.bones['upper_arm.'+side]
        fore = rig.data.bones['forearm.'+side]
        constraints.append((kit.attached(upper.name)-offset, upper.length+fore.length-.012))
    centre = centre.copy()
    for _ in range(100):
        for anchor, limit in constraints:
            delta = centre-anchor
            if delta.length > limit:
                centre = anchor+delta.normalized()*limit
        if all((centre-a).length <= r+1e-6 for a,r in constraints):
            return centre
    raise RuntimeError('Santa06 bowl and chopstick reach constraints do not overlap')


def duck_pose(t):
    # Feet and main body stay planted; the character reacts with its head and wings.
    curiosity = pulse(t,.19,.32,.72,.86)
    upward = pulse(t,.29,.45,.68,.82)
    excited = pulse(t,.45,.48,.53,.56)
    nod = pulse(t,.54,.56,.58,.61)
    head_rot = turn(-12*curiosity,'Z') @ turn(-7*upward+3*nod,'X') @ turn(5*curiosity,'Y')
    rigid('duck', DUCK, Matrix.Identity(3))
    rigid('duck_head', DUCK_HEAD, head_rot)
    feather_pos = DUCK_HEAD+head_rot@(FEATHER_PIVOT-DUCK_HEAD)
    flutter = 4*excited*math.sin(TAU*2*(t-.45)/.11)
    rigid('duck_feathers', feather_pos, head_rot @ turn(flutter,'Y'))
    flap = excited*(.65+.35*math.cos(TAU*2*(t-.45)/.11))
    for side, sign in (('L',1),('R',-1)):
        # Wings lift away from the body around their own shoulders.
        rigid('duck_wing.'+side, WING_PIVOTS[side], turn(-sign*24*flap,'Y'))


def pose_at(t):
    phase = TAU*(0. if t>=1 else t)
    tip_at, lifted, engaged = blend(t, POISE, DIP, LIFTED)
    pinch = ease(t,.235,.267)*(1-ease(t,.862,.90))
    prepare = pulse(t,.07,.16,.26,.43)
    bowl_raise = pulse(t,.10,.24,.77,.94)
    breathe = math.sin(2*phase)
    # Layer a slow weight shift and a smaller, offset chest counter-motion
    # on top of the shared planted-foot idle. Keep food gestures unchanged.
    weight = math.sin(phase)
    counter = math.sin(phase + .45) - math.sin(.45)
    settle = pulse(t,.43,.49,.57,.66)
    for name, pitch, roll, yaw in (
        ('spine', 2.5*prepare-1.6*lifted+.65*breathe,
         1.3*weight, .8*weight),
        ('chest', 1.8*prepare-1.2*lifted+.85*breathe+.6*settle,
         .8*counter, -.65*counter)):
        pb = rig.pose.bones.get(name)
        if pb is not None:
            local = pb.bone.matrix_local.to_3x3().inverted()
            for axis, degrees in (((1,0,0),pitch), ((0,1,0),roll), ((0,0,1),yaw)):
                pb.rotation_quaternion = pb.rotation_quaternion @ Quaternion(
                    (local @ Vector(axis)).normalized(), math.radians(degrees))
    bpy.context.view_layer.update()
    # Bowl follows the body subtly; chopsticks and noodles use the same
    # transform and the existing two-arm reach protection below.
    tilt = turn(10+1.0*lifted+.6*breathe,'X')
    centre = CENTRE + Vector((.014*weight, -.006*bowl_raise,
                              .022*bowl_raise+.012*lifted+.005*breathe))
    direction = LOW_DIR.lerp(HIGH_DIR,lifted).normalized()
    # Pivot about the tips near the broth so the chopstick glove clears the rim on both passes.
    near_broth = 1 - ease(tip_at.z, DIP.z + .02, POISE.z)
    direction = direction.lerp(DIP_DIR, near_broth).normalized()
    spin = aligned(LOWER_DIR, Vector((0,0,1)), -direction, BACK)
    tip_offset = tilt @ (FOOT+tip_at-CENTRE)
    centre = reachable_centre(centre,tilt,tip_offset,spin)
    rigid('bowl',centre,tilt)
    hold('L',centre+tilt@BOWL_GRIP,tilt)
    tip = centre+tip_offset
    wrist = tip-spin@TIPS
    kit.reach('R',wrist)
    rigid('hand.R',wrist,spin)
    rigid('sticks',wrist+spin@WEB,spin)
    rigid('stick',wrist+spin@PIVOT,spin@Matrix.Rotation(-math.radians(OPEN)*(1-pinch),3,HINGE_AXIS))
    rest = on_bowl(centre,tilt,DIP)
    top = rest.lerp(tip,pinch)
    anchor = on_bowl(centre,tilt,ANCHOR)
    hang = max(0.,min(1.,(top-rest).length/.08))
    points = chain(t,top,anchor,rest,hang)
    for j,p in enumerate(points):
        tangent = points[min(j+1,LINKS-1)]-points[max(j-1,0)]
        if tangent.length<1e-6:
            tangent=Vector((0,0,-1))
        rigid(f'noodle.{j:02d}',p,Vector((0,0,-1)).rotation_difference(tangent).to_matrix())
    k = rig.pose.bones['steam']
    k.scale = (.8,.85*(1+.05*math.sin(TAU*3*t)),.8)
    k.rotation_quaternion = turn(4*math.sin(TAU*2*t),'Z').to_quaternion()
    # Eyes lead the head down, then look up to the guest for the photo hold.
    gaze = pulse(t,.067,.17,.43,.54)+.6*pulse(t,.71,.78,.91,.98)
    eyes = pulse(t,.05,.15,.41,.52)+.6*pulse(t,.69,.76,.89,.96)
    nod = pulse(t,.55,.59,.63,.68)
    look(CAMERA.lerp(tip,gaze), math.radians(1.6*lifted+2*nod))
    aim_eyes(CAMERA.lerp(tip,eyes))
    duck_pose(t)


def clean_elbow_seams():
    """Remove only the detached decorative elbow rings from this edition's base mesh.

    The shared model creates each ring with 24 x 5 vertices. Match topology,
    red fabric, arm-only skin weights and the rest elbow position before deleting.
    """
    import bmesh
    obj = kit.santa
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    layer = bm.verts.layers.deform.active
    names = {g.index: g.name for g in obj.vertex_groups}
    visited = set()
    remove = []
    count = 0
    if layer is not None:
        for seed in bm.verts:
            if seed in visited:
                continue
            stack, component = [seed], []
            visited.add(seed)
            while stack:
                v = stack.pop()
                component.append(v)
                for edge in v.link_edges:
                    other = edge.other_vert(v)
                    if other not in visited:
                        visited.add(other)
                        stack.append(other)
            if len(component) != 120 or any(len(v.link_edges) != 4 for v in component):
                continue
            faces = {f for v in component for f in v.link_faces}
            if len(faces) != 120 or any(len(f.verts) != 4 or obj.data.materials[f.material_index].name != 'Crimson_velvet' for f in faces):
                continue
            owners = {names.get(i) for v in component for i, w in v[layer].items() if w > .001}
            centre = sum((v.co for v in component), Vector((0, 0, 0))) / len(component)
            for side in ('L', 'R'):
                allowed = {n + '.' + side for n in ('upper_arm', 'forearm', 'sleeve_sway')}
                elbow = rig.data.bones['forearm.' + side].head_local
                if owners and owners <= allowed and (centre - elbow).length < .055:
                    remove.extend(component)
                    count += 1
                    break
    if remove:
        bmesh.ops.delete(bm, geom=remove, context='VERTS')
        bm.to_mesh(obj.data)
        obj.data.update()
    bm.free()
    print(f'[Santa06] Removed {count} detached elbow seam rings (expected 4).', flush=True)


clean_elbow_seams()
kit.attach('Yunqueen props')
kit.bake('Santa06_Noodle_Chopsticks', FRAMES, pose_at,
         ['bowl', 'steam', 'duck', 'duck_head', 'duck_feathers', 'duck_wing.L', 'duck_wing.R', 'sticks', 'stick', 'head', 'eye.L', 'eye.R'] +
         [f'noodle.{j:02d}' for j in range(LINKS)] +
         [f'{n}.{s}' for s in 'LR' for n in ('upper_arm', 'forearm', 'hand')],
         activity=activity)
FRONT = ((.14, -5.85, 1.98), (.14, -.03, 1.06), 77, (800, 900))
LIFT_FRAME = round(.58 * (FRAMES - 1)) + 1
CLOSE = ((-.25, -1.75, 1.85), (-.01, -.53, 1.55), 58, (640, 640))
kit.finish('santa06', FRONT, [
    ('front', 1, FRONT),
    ('lift', LIFT_FRAME, FRONT),
    ('chopsticks', LIFT_FRAME, CLOSE),
    ('grip', LIFT_FRAME, ((-.75, -1.05, 1.62), (-.10, -.47, 1.45), 75, (640, 640))),
    ('pinch', round(.24 * (FRAMES - 1)) + 1, ((-.30, -1.20, 1.70), (-.05, -.50, 1.38), 70, (640, 640))),
    ('bowl', 1, ((.02, -1.76, 1.56), (.12, -.58, 1.27), 56, (640, 640))),
    ('duck', 1, ((.95, -2.4, .80), (.70, -.24, .55), 58, (640, 640))),
])
