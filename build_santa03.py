"""Build the Bouquet Café edition from the base character made by build_santa_base.py.

blender -b --factory-startup --python-exit-code 1 -P build_santa03.py -- previews
The optional directory receives front (the offer, also the page poster), start, mug, bouquet,
grip and sack previews.

Follows the café's suggested changes (photos/03 Bouquet Cafe suggested changes.jpg): their real
logo on the mug, their wrapped bouquet (photos/03 Bouquet Cafe bouquet *.jpg) offered to a guest
standing on Santa's left, and the flower sack moved behind him so the guest has room.
"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import santa_kit as kit  # noqa: E402
import santa_flowers as fl  # noqa: E402
from santa_kit import (TAU, around, bound, cord, decal, ellipsoid, hold, label, look, aim_eyes, material,  # noqa: E402
                       place, printed, profile, ramp, rigid, sheet, steam, turn)

MUG = Vector((-.15, -.47, 1.34))      # mug axis, half way up; held in the right glove
MUG_SCALE = 1.72                      # a big cafe mug, wider than the glove
PALM = Vector((-.032, 0, 0))          # the glove wraps the mug's handle side (-X)
# The left glove supports the lower wrapping from its inner/rear side, as in the reference.
# In the hand frame x runs from wrist to knuckles, z out of the back, and the thumb lies toward -y.
# The stem crosses the relaxed palm; short, gently bent fingers stay on one side of the paper
# instead of forming a fist or a continuous band around the bouquet.
STEM_ANGLE = math.radians(68)
STEM = Vector((math.cos(STEM_ANGLE), -math.sin(STEM_ANGLE), 0))   # the stem's direction in the hand
WRIST_L = Vector((.31, -.44, 1.12))   # the base's left wrist (hand.L head)
GRIPPED = .052                         # the outside of both paper layers at the support point
PALM_DEPTH = .024                      # half the thickness of the glove's palm
AXIS = Vector((.075, 0, -(PALM_DEPTH + GRIPPED)))   # where the stem's axis passes under the palm


def hand_to_bouquet():
    """The hand frame in the bouquet frame, with the palm behind the lower paper and the bouquet's
    open front and bow unobstructed. The stem runs along +Z through the support point."""
    back = Vector((math.cos(math.radians(12)), math.sin(math.radians(12)), 0))
    hand = Matrix((STEM, Vector((0, 0, 1)), STEM.cross(Vector((0, 0, 1))))).transposed()
    bunch = Matrix((Vector((0, 0, 1)), back, Vector((0, 0, 1)).cross(back))).transposed()
    return bunch @ hand.transposed()


TO_BOUQUET = hand_to_bouquet()


BOUQUET = WRIST_L + TO_BOUQUET @ AXIS  # modelled so the glove's wrist sits on the base's wrist
SACK = Vector((-.45, .56, 0))         # behind Santa's right side, leaving his left side free for a guest
kit.start(3, 'BouquetCafe', 'photos/03 Bouquet Cafe suggested changes.jpg', [
    ('mug', MUG, MUG + Vector((0, 0, .12)), 'root'),
    ('steam', MUG + Vector((0, 0, .07)), MUG + Vector((0, 0, .22)), 'mug'),
    ('bouquet', BOUQUET, BOUQUET + Vector((0, 0, .15)), 'root'),
])

ceramic = material('Glazed white ceramic', 'F3F0EA', .16, coat=.6)
logo = printed(ceramic, 'Bouquet Cafe logo', 'assets/bouquet-cafe-logo.jpg', '7E1E20')
coffee = material('Fresh coffee', '3A2013', .12)
vapour = material('Coffee_steam', 'EEE9E2', .9, alpha=.16)
assert (kit.rig.data.bones['hand.L'].head_local - WRIST_L).length < .001
# Replace the base's cupped mug glove with a relaxed bouquet support (glove() below).
mesh = bmesh.new()
mesh.from_mesh(kit.santa.data)
skin = mesh.verts.layers.deform.active
left = kit.santa.vertex_groups['hand.L'].index
bmesh.ops.delete(mesh, geom=[v for v in mesh.verts if v[skin].get(left, 0) > .5], context='VERTS')
mesh.to_mesh(kit.santa.data)
mesh.free()
leather = kit.bpy.data.materials['Brown_glove_leather']
kit.TILE[leather] = .20

m = fl.palette()
paper_dark = fl.tinted(material('Burgundy wrapping paper', '4E0915', .34, sheen=.15))
paper_red = fl.tinted(material('Red wrapping paper', 'A90F1A', .3, sheen=.15))
organza = material('Sheer white ribbon', 'F4ECEC', .45, sheen=.5)
satin = fl.tinted(material('Burgundy satin ribbon', '7A1025', .25, sheen=.3))

# ---------------------------------------------------------------- mug with the Bouquet Café logo
R, H = .046, .052
with bound('mug'), place(*MUG, scale=MUG_SCALE):
    profile([(-H, R - .006, R - .006), (-H + .004, R - .001, R - .001), (-H + .012, R, R), (H - .004, R, R),
             (H, R - .0015, R - .0015), (H - .001, R - .0045, R - .0045), (H - .012, R - .0050, R - .0050),
             (-H + .012, R - .0055, R - .0055)], ceramic, n=48)
    profile([(H - .016, R - .0052, R - .0052), (H - .015, R - .0052, R - .0052)], coffee, n=48)
    # Handle loops through the palm of the right glove (-X).
    cord([(-(R - .004 + .034 * math.sin(math.pi * k / 12) ** .8), 0, .030 * math.cos(math.pi * k / 12))
          for k in range(13)], .0065, ceramic, sides=8)
    # The café's logo file, printed on the side facing the guest (turned away from the handle).
    decal(around(R, .002, lift=.0003, spin=.22), .070, .070 * 864 / 1600, logo, columns=48, rows=8)
with bound('steam'):
    steam(MUG.x, MUG.y, MUG.z + MUG_SCALE * H - .012, 4, .27, .022, vapour, 3)


# ---------------------------------------------------------------- the café's wrapped bouquet
def cone(z):
    """Radius of the wrapped bundle: pinched at the supported stems (z = 0), opening into a cone
    above the hand and flaring a little below."""
    return .034 + .12 * -z if z < 0 else .034 + .48 * z * z / (z + .06)


def wrap(centre, span, tops, mat, inset, flare, crease, bottom=-.17):
    """One sheet of wrapping paper centred on angle `centre` (radians; 0 = +X, -pi/2 = the front),
    `span` either side, rising from the tail to a top edge given as (u, height) points from
    u = 0 at `centre - span` to u = 1, folding outward by `flare` near the top, with a soft
    crease down its middle."""
    def edge(u):
        for (u0, h0), (u1, h1) in zip(tops, tops[1:]):
            if u <= u1:
                return h0 + (h1 - h0) * (u - u0) / (u1 - u0)
        return tops[-1][1]

    rows = []
    for j in range(13):
        t = j / 12
        row = []
        for i in range(17):
            u = i / 16
            a = centre + span * (2 * u - 1)
            ridge = 1 - abs(2 * u - 1)
            peak = edge(u)
            z = bottom + (peak - bottom) * t
            fold = max(0, (z - peak * .62) / (peak * .38)) if peak > .12 else 0
            r = cone(z) + inset + flare * fold ** 2 + crease * ridge * t
            row.append((r * math.cos(a), r * math.sin(a), z + .02 * fold * ridge))
        rows.append(row)
    sheet(rows, mat)


def ribbon(path, width, across, mat):
    """A flat ribbon along `path`, `width` wide in direction `across` (one vector or one per point)."""
    rows = []
    for i, p in enumerate(path):
        w = Vector(across[i] if isinstance(across, list) else across).normalized() * width / 2
        rows.append([tuple(Vector(p) - w), tuple(Vector(p)), tuple(Vector(p) + w)])
    sheet(rows, mat)


def along(path, across, lift):
    """Map lettering onto a ribbon: u runs down the ribbon from its middle, v across it, on the face
    toward the guest."""
    pts = [Vector(p) for p in path]
    lengths = [0]
    for a, b in zip(pts, pts[1:]):
        lengths.append(lengths[-1] + (b - a).length)

    def mapper(u, v, depth=0):
        d = min(max(lengths[-1] / 2 + u, 0), lengths[-1] - 1e-6)
        i = next(k for k in range(len(pts) - 1) if lengths[k + 1] >= d)
        f = (d - lengths[i]) / (lengths[i + 1] - lengths[i])
        p = pts[i].lerp(pts[i + 1], f)
        tangent = (pts[i + 1] - pts[i]).normalized()
        side = Vector(across[i]).normalized()
        normal = tangent.cross(side).normalized()
        if normal.y > 0:
            normal = -normal
        side = normal.cross(tangent).normalized()
        return tuple(p + side * v + normal * (lift - depth))
    return mapper


def bow(z):
    """A wide sheer white bow with a burgundy satin bow over it, tied just below the hand, its long
    tails hanging down past the end of the paper."""
    front = -(cone(z) + .024)
    for mat, width, size, lift in ((organza, .046, 1.0, 0), (satin, .026, .80, -.006)):
        r = cone(z) + .020 - lift
        cord([(r * math.cos(TAU * k / 24), r * math.sin(TAU * k / 24), z) for k in range(25)], .0045, mat, sides=6)
        for s in (-1, 1):
            loop = [(s * .062 * size * (1 - math.cos(a)), front + lift - .006 * math.sin(a),
                     z + .030 * size * math.sin(a) + .016 * size * (1 - math.cos(a))) for a in
                    [TAU * k / 18 for k in range(19)]]
            ribbon(loop, width, (0, 1, 0), mat)
            tail = [(s * (.008 + .045 * k / 9) * size + .006 * math.sin(1.3 * k), front + lift - .003 * k,
                     z - .012 - .026 * k * size) for k in range(10)]
            across = [(1, .3 * s, .15 * math.sin(k)) for k in range(10)]
            ribbon(tail, width * .9, across, mat)
            if mat is satin:  # the café's name printed down each satin tail, as on their ribbon
                label('bouquet café', organza, along(tail, across, .0012), .15, bold=.01)
    ellipsoid(0, front - .008, z, .014, .008, .012, satin, 10, 5)


with bound('bouquet'), place(*BOUQUET):
    rnd = random.Random(33)
    # Tall burgundy sheets fanned behind and beside the flowers, open at the front...
    for centre, span, tops in ((math.pi / 2, .85, [(0, .40), (.5, .48), (1, .40)]),
                               (math.pi / 2 - 1.15, .8, [(0, .17), (.55, .42), (1, .44)]),
                               (math.pi / 2 + 1.15, .8, [(0, .44), (.45, .42), (1, .17)])):
        wrap(centre, span, tops, paper_dark, 0, .08, .014)
    # ...inside a bright red cone of two sheets, one round each side, whose edges sweep down to a
    # deep V at the front, so the flowers show above the supporting hand.
    wrap(0, math.pi / 2 + .15, [(0, .07), (.30, .20), (.62, .33), (.78, .36), (1, .28)], paper_red, .011, .05, .02)
    wrap(math.pi, math.pi / 2 + .15, [(0, .27), (.22, .35), (.38, .32), (.70, .20), (1, .07)], paper_red, .016, .05,
         .02)
    # Ten deep red roses, peach-pink spray roses and their buds on a low dome...
    reds = {0, 3, 6, 9, 12, 15, 18, 21, 24, 27}
    buds = {5, 11, 17, 23, 29}
    kinds = [('red', rnd.uniform(.054, .060)) if k in reds else ('bud', rnd.uniform(.016, .019)) if k in buds
             else ('pink', rnd.uniform(.032, .037)) for k in range(30)]
    fl.arrangement((0, 0, .29), .175, 74, kinds, m, 31, height=.85, stems_to=((0, 0, 0), (0, 0, -.13), .03))
    # ...and more tumbling down the front opening, facing out toward the guest.
    for k, (da, z, kind, size) in enumerate(((-.35, .21, 'red', .052), (.32, .18, 'red', .050), (0, .25, 'pink', .034),
                                             (-.12, .13, 'pink', .032), (.15, .10, 'pink', .030),
                                             (.48, .25, 'pink', .033), (-.55, .27, 'bud', .017), (.05, .17, 'bud', .016))):
        a = -math.pi / 2 + da
        p = Vector((math.cos(a), math.sin(a), 0)) * cone(z) * .72 + Vector((0, 0, z))
        with kit.frame(fl.aim(p, (math.cos(a), math.sin(a), .9), rnd.uniform(0, TAU))):
            fl.head(kind, size, m, 120 + k)
        cord([p, p * .5 + Vector((0, 0, p.z * .2)), Vector((0, 0, 0)), Vector((0, 0, -.12))], .0032, m['stem'], sides=5)
    for k, da in enumerate((-.6, .05, .6)):
        a = -math.pi / 2 + da
        fl.eucalyptus(m, (.04 * math.cos(a), .04 * math.sin(a), .08), (math.cos(a), math.sin(a), .8), .17, 5, .026,
                      130 + k)
        fl.limonium(m, (.03 * math.cos(a + .3), .03 * math.sin(a + .3), .10),
                    (.8 * math.cos(a + .3), .8 * math.sin(a + .3), 1), .20, 140 + k)
    # Silver-dollar eucalyptus around the rim and between the flowers.
    for k in range(14):
        a = TAU * k / 14 + rnd.uniform(-.15, .15)
        fl.eucalyptus(m, (.11 * math.cos(a), .11 * math.sin(a), .27),
                      (math.cos(a), math.sin(a), rnd.uniform(.25, .9)), rnd.uniform(.17, .23), 5, .028, 50 + k)
    for k in range(5):
        a = TAU * k / 5 + .5
        fl.eucalyptus(m, (.03 * math.cos(a), .03 * math.sin(a), .30),
                      (.45 * math.cos(a), .45 * math.sin(a), 1), .19, 4, .022, 65 + k)
    # Airy limonium sprays rising through the flowers.
    for k in range(16):
        a = TAU * k / 16 + .4
        fl.limonium(m, (.05 * math.cos(a), .05 * math.sin(a), .26),
                    (.62 * math.cos(a), .62 * math.sin(a), 1), rnd.uniform(.22, .28), 70 + k)
    bow(-.075)

assert abs(GRIPPED - (cone(0) + .018)) < 1e-6


def around_stem(start, degrees, radius, steps=8):
    """Points curling `degrees` round the stem from beside `start`, `radius` from its axis; positive
    turns the way the fingers close (over the far side), negative the way the thumb does."""
    foot = AXIS + STEM * (start - AXIS).dot(STEM)
    out = (start - foot).normalized()
    side = STEM.cross(out)
    if side.x < 0:  # fingers close forward, toward the knuckles' side, then under the stem
        side = -side
    return [foot + (out * math.cos(a) + side * math.sin(a)) * radius
            for a in [math.radians(degrees) * k / steps for k in range(steps + 1)]]


def glove():
    """A relaxed left glove supporting one side of the lower paper, below all the flower heads."""
    ellipsoid(.049, 0, 0, .057, .045, PALM_DEPTH, leather, 24, 14)
    for y, size in ((-.030, 1.0), (-.010, 1.04), (.010, .98), (.029, .86)):  # index to little finger
        fr = .0145 * size
        knuckle = Vector((.097 - .008 * abs(y) / .03, y, -.004))
        ring = around_stem(knuckle, 62 * size, GRIPPED + fr)
        cord([knuckle - Vector((.012, 0, 0))] + ring, fr, leather,
             [1, 1, 1, .98, .96, .93, .9, .86, .8, .74], sides=12)
        ellipsoid(knuckle.x, knuckle.y, knuckle.z + .004, fr * 1.05, fr, fr, leather, 12, 6)
        tip = ring[-1]
        ellipsoid(tip.x, tip.y, tip.z, fr * .72, fr * .72, fr * .72, leather, 10, 5)
    # A resting thumb touches the paper beside the index finger, without closing across its front.
    base = Vector((.030, -.044, -.014))
    ring = [base] + around_stem(Vector((.060, -.050, -.040)), -42, GRIPPED + .017, 6)
    cord(ring, .018, leather, [1, 1, .98, .95, .9, .85, .78, .72], sides=12)
    tip = ring[-1]
    ellipsoid(tip.x, tip.y, tip.z, .013, .013, .013, leather, 10, 5)


with bound('hand.L'), place(*BOUQUET), kit.frame((Matrix.Translation(-(TO_BOUQUET @ AXIS)) @ TO_BOUQUET.to_4x4())):
    glove()

# ---------------------------------------------------------------- velvet sack brimming with flowers
velvet = kit.bpy.data.materials['Crimson_velvet']
kit.TILE[velvet] = .36
rnd = random.Random(3)
bulges = [rnd.uniform(0, TAU) for _ in range(4)]


def slump(a, z):
    return 1 + .07 * math.sin(3 * a + bulges[0]) * math.sin(math.pi * min(1, z / .5)) + .04 * math.cos(5 * a + bulges[1])


with place(*SACK, yaw=25, scale=1.2):
    profile([(.004, .12, .11), (.02, .25, .23), (.08, .31, .29), (.18, .33, .31), (.30, .31, .29), (.40, .26, .25),
             (.47, .215, .205), (.51, .20, .19), (.56, .23, .215), (.60, .255, .235), (.62, .25, .23)],
            velvet, n=40, close=False, wobble=slump, two_sided=True)
    # Two soft folds where the sack gathers under its load.
    for a in (.5, 2.6, 4.4):
        cord([((.30 - .1 * k / 4) * math.cos(a), (.28 - .1 * k / 4) * math.sin(a), .12 + .09 * k) for k in range(5)],
             .012, velvet, [.3, .9, 1, .9, .3])
    sack = [(rnd.choice(['red', 'red', 'pink']), rnd.uniform(.070, .080)) for _ in range(12)]
    fl.arrangement((0, 0, .60), .17, 78, sack, m, 77, height=.8)
    for k in range(8):
        a = TAU * k / 8 + .3
        fl.eucalyptus(m, (.12 * math.cos(a), .12 * math.sin(a), .62), (math.cos(a), math.sin(a), .6), .19, 5, .028,
                      90 + k)


# ---------------------------------------------------------------- eight-second loop
FRAMES = 193
CAMERA = Vector((-.05, -3.2, 1.55))
# Elbow direction, forearm direction, flower guide, and wrist bend (degrees), from the low side
# hold through a lift and forward offer to the viewer. The shoulder and elbow carry the reach;
# the wrist stays relaxed while the flower heads tip toward the camera.
ARM = {'low': ((.50, .08, -.86), (.25, -.94, -.15), (.45, .04, .90), 4),
       'lifted': ((.58, -.30, -.75), (.28, -.95, .12), (.40, -.45, .80), 0),
       'offer': ((.64, -.70, -.32), (.16, -.985, -.05), (.30, -.55, .78), -10)}


def blend(lift, reach):
    """Nlerp each of the arm's directions from low to lifted (lift) and on to the offer (reach)."""
    out = []
    for lo, li, of in zip(ARM['low'][:3], ARM['lifted'][:3], ARM['offer'][:3]):
        v = Vector(lo) + (Vector(li) - Vector(lo)) * lift + (Vector(of) - Vector(li)) * reach
        out.append(v.normalized())
    lo, li, of = ARM['low'][3], ARM['lifted'][3], ARM['offer'][3]
    return out + [lo + (li - lo) * lift + (of - li) * reach]


def left_arm(elbow_dir, forearm, flowers, bend):
    """Pose the upper arm, forearm, glove and bouquet; returns the bouquet's grip point and rotation."""
    upper, fore = rig.data.bones['upper_arm.L'], rig.data.bones['forearm.L']
    shoulder = kit.attached('upper_arm.L')
    elbow = shoulder + elbow_dir * upper.length
    wrist = elbow + forearm * fore.length
    for bone, a, b in ((upper, shoulder, elbow), (fore, elbow, wrist)):
        rigid(bone.name, a, (bone.tail_local - bone.head_local).rotation_difference(b - a).to_matrix())
    # A left hand: the thumb points along hand x back-of-hand, so back = thumb x hand. The wrist bends
    # the hand `bend` degrees toward the thumb from the line of the forearm.
    toward = (flowers - forearm * flowers.dot(forearm)).normalized()
    b = math.radians(bend)
    along = forearm * math.cos(b) + toward * math.sin(b)
    thumb = toward * math.cos(b) - forearm * math.sin(b)
    back = thumb.cross(along).normalized()
    hand = Matrix((along, back.cross(along), back)).transposed()
    rot = hand @ TO_BOUQUET.transposed()
    grip = wrist + hand @ AXIS
    rigid('bouquet', grip, rot)
    rigid('hand.L', wrist, rot)
    return grip, rot


def pose_at(t):
    # Hold the mug steady at the chest; it only breathes with him.
    mug = MUG + Vector((0, 0, .004 * math.sin(TAU * t)))
    tilt = turn(-2 - 1.5 * math.sin(TAU * t), 'X')
    rigid('mug', mug, tilt)
    hold('R', mug + tilt @ PALM, tilt)
    k = rig.pose.bones['steam']
    k.scale = (1, 1 + .08 * math.sin(TAU * 3 * t), 1)
    k.rotation_quaternion = turn(6 * math.sin(TAU * 2 * t), 'Z').to_quaternion()
    # Offer the bouquet: lift it from his side to chest height, then reach forward and tip it toward
    # the viewer (about 2 s), hold still for about four seconds so they can pose as if taking it,
    # then draw it back and lower it together (about 2 s), easing the longer forward reach home.
    lower = 1 - ramp(t, .76, 1)
    lift = ramp(t, .05, .21) * lower
    reach = ramp(t, .15, .28) * lower
    rest = 1 - lift
    elbow_dir, forearm, flowers, bend = blend(lift, reach)
    forearm = (forearm + Vector((0, 0, .02 * rest * math.sin(TAU * 2 * t)))).normalized()
    grip, rot = left_arm(elbow_dir, forearm, flowers, bend)
    # He glances at the bouquet as he raises it, and looks at the camera for the photo.
    glance = math.sin(math.pi * ramp(t, .04, .36))
    target = CAMERA.lerp(grip + rot @ Vector((0, 0, .25)), .8 * glance)
    look(target)
    aim_eyes(target)


rig = kit.rig
kit.attach('Bouquet Cafe props')
kit.bake('Santa03_Offer_Bouquet', FRAMES, pose_at,
         ['mug', 'steam', 'bouquet', 'head', 'eye.L', 'eye.R'] +
         [f'{n}.{s}' for s in 'LR' for n in ('upper_arm', 'forearm', 'hand')])
FRONT = ((.12, -5.85, 1.98), (.10, -.03, 1.06), 77, (800, 900))
kit.finish('santa03', FRONT, [
    ('front', 97, FRONT),
    ('start', 1, FRONT),
    ('mug', 1, ((-.30, -1.45, 1.50), (-.14, -.48, 1.36), 80, (640, 640))),
    ('bouquet', 97, ((.9, -2.1, 1.75), (.50, -.65, 1.55), 55, (640, 640))),
    ('grip', 97, ((1.1, .7, 1.7), (.46, -.57, 1.34), 65, (640, 640))),
    ('sack', 1, ((-1.6, -3.0, 1.4), (-.55, .2, .7), 60, (640, 640))),
])
