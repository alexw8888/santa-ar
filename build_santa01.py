"""Build Santa 01 on the base character: Santa pours chai from a brass kettle, then sips it.

blender -b --factory-startup --python-exit-code 1 -P build_santa01.py -- [preview_dir] [shot ...]

Needs santa_base.blend (build_santa_base.py). Writes santa01.blend, and with a preview folder the
previews and docs/santa01-poster.webp; name shots after the folder to render only those.

Santa 01 is modelled on photos/01 Chaiiwala Santa.jpg: a golden brass kettle with a plaque
printed with the Chaiiwala logo in his right glove, its own kettle grip, and an engraved brass
teacup that his left glove holds by its handle (both gloves replace the base's cupped ones). The
328-frame loop runs at 24 fps and combines five layers per frame.

1. The pour: the kettle lifts and pours a timed stream into the cup, then lowers; the cup rises
   toward his face; arms solve from the shoulders; head and eyes follow the cup. It is evaluated
   at an eased time, so each gesture eases in and out (EASE_STRENGTH).
2. The shared secondary sway from santa_motion.py (body, coat, sleeves, hat tip, feet) at that
   eased time, with the kettle, stream and cup following the gloves that hold them.
3. A subtle torso counterlean while the kettle is up: its shoulder rises and the cup shoulder
   drops; the arms re-solve to the same wrists, so neither prop moves.
4. The sip: the cup comes to his lips and tips about 17 degrees, the left glove holding it. The
   chai fills while it is poured and drains while he sips, so the cup is empty at both ends of
   the loop, and the steam fades with the last sip.
5. Santa dips the empty cup below his face, nods twice, then pauses half a second before lowering it.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bmesh  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import santa_engraving as engraving  # noqa: E402
import santa_kit as kit  # noqa: E402
import santa_model as model  # noqa: E402
import santa_motion  # noqa: E402
from santa_model import (BRASS, CUP, GOLD, KETTLE, LEATHER, SHOULDERS, TAU, add_bone,  # noqa: E402
                         ellipsoid, finish, lathe, material, torus, tube, uv_face)

# -------------------- the teacup's shape
# A polished brass teacup: a rounded bowl on a short foot with a rolled lip, a plain band under the
# rim, flowers and leaves engraved below it (santa_engraving.py) and an ear-shaped strap handle.
# Profiles are (height above the foot, radius) in metres for a teacup of real proportions, which
# CUP_SCALE enlarges to suit Santa. The outer WALL is engraved from the foot to the lip; the
# underside, foot, lip and inside are plain polished brass.
CUP_SCALE = 1.6


def scaled(rows):
    return [(h * CUP_SCALE, r * CUP_SCALE) for h, r in rows]


FOOT = scaled([(.0050, .0015), (.0050, .0290), (.0022, .0302), (.0004, .0318), (.0000, .0335), (.0000, .0360),
               (.0010, .0369), (.0030, .0358), (.0046, .0352), (.0058, .0362), (.0066, .0378)])
WALL = scaled([(.0076, .0405), (.0100, .0458), (.0140, .0508), (.0190, .0550), (.0250, .0583), (.0320, .0608),
               (.0400, .0626), (.0500, .0637), (.0600, .0643), (.0700, .0648), (.0780, .0656), (.0840, .0666),
               (.0876, .0675)])
LIP = scaled([(.0889, .0681), (.0898, .0678), (.0902, .0670), (.0899, .0661), (.0890, .0655)])
INSIDE = scaled([(.0870, .0651), (.0820, .0641), (.0760, .0633), (.0700, .0626), (.0600, .0619), (.0500, .0612),
                 (.0400, .0600), (.0320, .0581), (.0250, .0553), (.0190, .0517), (.0150, .0470), (.0122, .0405),
                 (.0106, .0310), (.0098, .0180), (.0096, .0020)])
BOTTOM, FULL = INSIDE[-1][0], .0745 * CUP_SCALE  # heights of the inside of the bowl and of a full cup of chai
ENGRAVING_TOP = .066 * CUP_SCALE  # where the engraved ground gives way to the plain band under the rim
# The strap handle's centreline in its plane: (distance from the cup's axis along OUT, height). Both
# ends sink into the wall; the first five points make the top of the handle.
HANDLE = scaled([(.0640, .0776), (.0700, .0790), (.0809, .0848), (.0974, .0862), (.1125, .0802), (.1160, .0690),
                 (.1151, .0604), (.1103, .0491), (.1020, .0388), (.0901, .0294), (.0763, .0234), (.0640, .0204),
                 (.0535, .0188)])
STRAP_HALF_WIDTH, STRAP_HALF_THICKNESS = .0055 * CUP_SCALE, .003 * CUP_SCALE

# -------------------- prop bones, on top of the base rig
# The handle points toward Santa's left. His wrist sits beside the outer edge of the handle.
HANDLE_AZIMUTH = math.radians(0)
OUT = Vector((math.cos(HANDLE_AZIMUTH), math.sin(HANDLE_AZIMUTH), 0))
SIDE = Vector((-OUT.y, OUT.x, 0))  # normal to the handle plane, pointing away from the front camera
UP = Vector((0, 0, 1))
CUP_BASE = CUP + Vector((.0256, -.0903, -.0685))
CUP_WRIST = CUP_BASE + .276 * OUT + .112 * SIDE + .081 * UP
LIQUID_BOTTOM = CUP_BASE + BOTTOM * UP
FILL_DEPTH = FULL - BOTTOM
END = CUP_BASE + FULL * UP  # where the stream meets a full cup
POUR_GRIP = Vector((-.18, -.49, 1.73)) + (CUP_BASE - CUP) * Vector((1, 1, 0))  # the spout above the cup
POUR_ROT = Matrix.Rotation(math.radians(25), 3, 'Y')
SPOUT_LOCAL = Vector((.44, -.012, -.16))
STREAM_START = POUR_GRIP + POUR_ROT @ SPOUT_LOCAL


def solve_arm(side, shoulder, wrist):
    """Two-bone arm from `shoulder` to `wrist` with the base's elbow guide (out and down)."""
    upper, lower = model.UPPER, model.LOWER
    direction = wrist - shoulder
    d = min(direction.length, upper + lower - .001)
    along = direction.normalized()
    a = (upper * upper - lower * lower + d * d) / (2 * d)
    guide = Vector((1 if side == 'L' else -1, .08, -.5))
    elbow = (shoulder + along * a
             + (guide - along * guide.dot(along)).normalized() * math.sqrt(max(0, upper * upper - a * a)))
    for name, start, end in ((f'upper_arm.{side}', shoulder, elbow), (f'forearm.{side}', elbow, wrist)):
        rest = rig.data.bones[name]
        kit.rigid(name, start, (rest.tail_local - rest.head_local).rotation_difference(end - start).to_matrix())


def bind_cup_arm():
    """Fit the left sleeve and its bones to the grip in the rig's default pose."""
    solve_arm('L', SHOULDERS['L'], CUP_WRIST)
    kit.rigid('hand.L', CUP_WRIST)
    names = ('upper_arm.L', 'forearm.L', 'hand.L', 'sleeve_sway.L')
    sleeve_matrices = {name: rig.pose.bones[name].matrix.copy() for name in names}
    posed = santa.evaluated_get(bpy.context.evaluated_depsgraph_get())
    coords = np.empty(len(santa.data.vertices) * 3, dtype=np.float32)
    posed.data.vertices.foreach_get('co', coords)
    santa.data.vertices.foreach_set('co', coords)
    santa.data.update()
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    for name, matrix in sleeve_matrices.items():
        rig.data.edit_bones[name].matrix = matrix
    bpy.ops.object.mode_set(mode='OBJECT')
    for name in names:
        rig.pose.bones[name].matrix_basis = Matrix.Identity(4)


TEA_BONES = [
    ('kettle', KETTLE, KETTLE + Vector((0, 0, .12)), 'root'),
    ('cup', CUP, CUP + Vector((0, 0, .12)), 'root'),
    ('liquid', LIQUID_BOTTOM, LIQUID_BOTTOM + Vector((0, 0, .1)), 'cup'),
    ('aroma', END, END + Vector((0, 0, .1)), 'cup'),
    ('stream', STREAM_START, STREAM_START + Vector((0, 0, -.2)), 'root'),
]
scene, rig, santa = kit.start(1, 'ChaiBreak', 'photos/01 Chaiiwala Santa.jpg', TEA_BONES)
for bone in TEA_BONES:
    add_bone(*bone)

# The base's cupped gloves wrap a round prop; Santa 01 models its own: one grips the kettle, one the cup.
mesh = bmesh.new()
mesh.from_mesh(santa.data)
skin = mesh.verts.layers.deform.active
hands = [santa.vertex_groups[name].index for name in ('hand.L', 'hand.R')]
bmesh.ops.delete(mesh, geom=[v for v in mesh.verts if any(v[skin].get(g, 0) > .5 for g in hands)], context='VERTS')
mesh.to_mesh(santa.data)
mesh.free()
bind_cup_arm()

model.reuse_materials()
CHAI = material('Masala_chai', (.50, .23, .085), .2)
STEAM = material('Chai_aroma', (.63, .59, .54), .9, alpha=.18)
MOUTH = material('Mouth_interior', (.085, .010, .007), .8)
model.new_mesh()

# -------------------- the right glove gripping the kettle handle
hand = 'hand.R'
ellipsoid(KETTLE + Vector((0, .022, .035)), (.080, .054, .052), LEATHER, hand, seg=24, rings=16)
for i in range(4):
    x = (i - 1.5) * .030
    s = 1 - .08 * abs(i - 1.5)
    points = [KETTLE + Vector((x, -.002, .062)), KETTLE + Vector((x, -.040 * s, .046)),
              KETTLE + Vector((x, -.047 * s, .008)), KETTLE + Vector((x, -.025 * s, -.012))]
    tube(points, [.0185, .019, .016, .011], LEATHER, hand, sides=12, sub=3)
    ellipsoid(points[1] + Vector((0, -.008, .004)), (.012, .006, .008), LEATHER, hand, seg=12, rings=8)
tube([KETTLE + Vector((.079, .012, .035)), KETTLE + Vector((.069, -.024, .005)), KETTLE + Vector((.036, -.039, -.011))],
     [.024, .022, .012], LEATHER, hand, sides=12, sub=3)

# -------------------- golden brass chai kettle with a Chaiiwala logo plaque
body = KETTLE + Vector((0, 0, -.31))
lathe(body, [(-.14, .105), (-.13, .14), (-.105, .164), (.07, .17), (.105, .155), (.12, .125), (.125, .10)],
      BRASS, 'kettle', sides=56)
for z, r in ((-.12, .149), (.089, .162), (.124, .105)):
    torus(body + Vector((0, 0, z)), (0, 0, 1), r, .0055, GOLD, 'kettle', sides=48, cross=6)
lathe(body, [(.125, .12), (.137, .11), (.156, .072), (.163, .025)], GOLD, 'kettle', sides=40)
ellipsoid(body + Vector((0, 0, .177)), (.026, .026, .022), BRASS, 'kettle', seg=20, rings=12)
spout = [body + Vector((.135, 0, -.04)), body + Vector((.215, -.004, -.015)), body + Vector((.253, -.008, .06)),
         body + Vector((.326, -.012, .13)), KETTLE + SPOUT_LOCAL]
tube(spout, [.038, .031, .024, .018, .015], BRASS, 'kettle', sides=16, sub=4, cap=False)
torus(KETTLE + SPOUT_LOCAL, spout[-1] - spout[-2], .015, .0035, GOLD, 'kettle', sides=24, cross=6)
ellipsoid(KETTLE + SPOUT_LOCAL - (spout[-1] - spout[-2]).normalized() * .006, (.012, .012, .004), MOUTH, 'kettle', seg=16, rings=8,
          direction=spout[-1] - spout[-2])
arc = [KETTLE + Vector((.163 * math.cos(a), 0, -.18 + .18 * math.sin(a))) for a in [math.pi * i / 24 for i in range(25)]]
tube(arc, [.009] * 25, GOLD, 'kettle', sides=8, sub=1)
grip = [KETTLE + Vector((.16 * math.cos(a), 0, -.18 + .18 * math.sin(a))) for a in [math.pi * .30 + math.pi * .40 * i / 16 for i in range(17)]]
tube(grip, [.015] * 17, LEATHER, 'kettle', sides=10, sub=1)
for sign in (-1, 1):
    ellipsoid(KETTLE + Vector((sign * .16, 0, -.18)), (.014, .017, .020), GOLD, 'kettle', seg=16, rings=10)
# The logo plaque's outline, in metres from its centre (x along the kettle's curve, z up): a band
# with concave notched corners, an arched crest top and bottom and a pointed tip at each end.
PLAQUE_A, PLAQUE_B = .122, .046  # half-width and half-height of the band
CREST, CREST_SPAN = .012, .055  # how far the crest rises above the band, and its half-width
TIP, TIP_SPAN = .020, .032  # how far each end's point reaches past the band, and its half-height
NOTCH = .014  # radius of the circular notch cut from each corner
LOGO_WIDTH = .205
CW = PLAQUE_A + TIP  # half-width of the whole plaque, kept clear of the scrollwork
for z in (-.085, .052):
    for k in range(12):
        a = math.pi + math.pi * k / 11
        if abs(.166 * (a - 1.5 * math.pi)) < CW + .014:
            continue  # leave room for the plaque
        c = body + Vector((.166 * math.cos(a), .166 * math.sin(a), z))
        tangent = Vector((-math.sin(a), math.cos(a), 0))
        points = [c + tangent * (j - .5) * .018 + Vector((0, 0, .006 * math.sin(j * TAU))) for j in (0, .25, .5, .75, 1)]
        tube(points, [.0012] * 5, GOLD, 'kettle', sides=4, sub=1)
# The plaque faces the viewer. It is modelled flat on the plane y = -R0 and then wrapped onto the
# kettle's curve.
R0 = .168
def kettle_radius(z):
    return float(np.interp(z, (-.105, .07), (.164, .17)))
def wrapped(build):
    count = len(model.bm.verts)
    build()
    model.bm.verts.ensure_lookup_table()
    for v in model.bm.verts[count:]:
        rel = v.co - body
        radius = kettle_radius(rel.z)
        d, a = radius + (-rel.y - R0), -math.pi / 2 + rel.x / radius
        v.co = body + Vector((d * math.cos(a), d * math.sin(a), rel.z))

def plaque_inside(x, z, inset=0.0):
    """Whether (x, z) lies inside the plaque outline, shrunk by roughly `inset`."""
    X, Z = abs(x), abs(z)
    top = PLAQUE_B - inset + (CREST * math.cos(math.pi * X / (2 * CREST_SPAN)) ** 2 if X < CREST_SPAN else 0)
    side = PLAQUE_A - inset + (TIP * (1 - Z / TIP_SPAN) ** 2 if Z < TIP_SPAN else 0)
    notch = (PLAQUE_A - X) ** 2 + (PLAQUE_B - Z) ** 2 >= (NOTCH + inset) ** 2
    return Z <= top and X <= side and notch


def plaque_outline(inset=0.0):
    """The outline as points running anticlockwise from the right-hand tip, thinned on straight runs."""
    traced = []
    for i in range(720):
        t = TAU * i / 720
        dx, dz = math.cos(t), math.sin(t)
        r = 0.0
        while plaque_inside(r * dx, r * dz, inset):
            r += .001
        lo, hi = r - .001, r
        for _ in range(24):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if plaque_inside(mid * dx, mid * dz, inset) else (lo, mid)
        traced.append(Vector((lo * dx, lo * dz)))
    kept = [traced[0]]
    for i, p in enumerate(traced[1:-1], 1):
        before, after = (p - kept[-1]).normalized(), (traced[i + 1] - p).normalized()
        if (p - kept[-1]).length > .008 or before.angle(after, 0) > math.radians(5):
            kept.append(p)
    return kept


def logo_plaque():
    """A shaped white enamel plaque printed with the Chaiiwala logo in black, with gold rims and beads."""
    source = bpy.data.images.load(str(kit.ROOT / 'photos' / 'chaiiwala_logo_black.png'))
    w, h = source.size
    px = np.empty(w * h * 4, dtype=np.float32)
    source.pixels.foreach_get(px)
    bpy.data.images.remove(source)
    px = px.reshape(h, w, 4)
    if px[:, :, 3].min() < .99:
        ink = px[:, :, 3]
    else:  # opaque artwork: dark marks on a pale ground (or the reverse)
        luma = px[:, :, :3] @ np.array([.2126, .7152, .0722])
        paper, dark = np.percentile(luma, 90), np.percentile(luma, .5)
        ink = np.clip((paper - luma) / (paper - dark), 0, 1)
    rows, cols = np.nonzero(ink > .05)
    ink = ink[rows.min():rows.max() + 1, cols.min():cols.max() + 1]
    # The print covers the plaque's bounding box, with the logo LOGO_WIDTH wide in the middle.
    half_u, half_v = PLAQUE_A + TIP, PLAQUE_B + CREST
    per_metre = ink.shape[1] / LOGO_WIDTH
    width, height = round(2 * half_u * per_metre) // 2 * 2, round(2 * half_v * per_metre) // 2 * 2
    top, left = (height - ink.shape[0]) // 2, (width - ink.shape[1]) // 2
    canvas = np.zeros((height, width), dtype=np.float32)
    canvas[top:top + ink.shape[0], left:left + ink.shape[1]] = ink
    canvas = canvas.reshape(height // 2, 2, width // 2, 2).mean((1, 3))[:, :, None]
    plate_color, plate_rough, plate_metal = np.array((.82, .81, .78)), .3, 0  # white enamel
    # Jet-black ink. A plain (non-metal) black still reflects about 4% of the gold kettle and red coat
    # around it and reads brown; as a near-zero-reflectance metal it stays a neutral black in every viewer.
    ink_color, ink_rough = np.array((.006, .006, .006)), .5
    name = model.material('Chaiiwala logo', tuple(plate_color), plate_rough, plate_metal)
    mat = bpy.data.materials[name]
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes['Principled BSDF']
    color = nodes.new('ShaderNodeTexImage')
    color.image = kit.image(name + ' print', kit.to_srgb(plate_color * (1 - canvas) + ink_color * canvas))
    links.new(color.outputs['Color'], bsdf.inputs['Base Color'])
    orm = np.concatenate([np.ones_like(canvas), plate_rough * (1 - canvas) + ink_rough * canvas,
                          plate_metal * (1 - canvas) + canvas], axis=2)
    surface = nodes.new('ShaderNodeTexImage')
    surface.image = kit.image(name + ' surface', orm)
    surface.image.colorspace_settings.name = 'Non-Color'
    separate = nodes.new('ShaderNodeSeparateColor')
    links.new(surface.outputs['Color'], separate.inputs['Color'])
    links.new(separate.outputs['Green'], bsdf.inputs['Roughness'])
    links.new(separate.outputs['Blue'], bsdf.inputs['Metallic'])

    plate = body + Vector((0, -R0 - .003, -.012))
    outline = plaque_outline()

    def at(p, lift=0.0):
        return plate + Vector((p.x, -lift, p.y))

    def enamel():
        # Rings shrinking toward the centre, so the face bends smoothly round the kettle.
        rings_ = [[model.bm.verts.new(at(p * (k / 4))) for p in outline] for k in range(1, 5)]
        centre = model.bm.verts.new(at(Vector((0, 0))))
        uv = lambda p: ((p.x + half_u) / (2 * half_u), (p.y + half_v) / (2 * half_v))
        n = len(outline)
        for i in range(n):
            a, b = outline[i], outline[(i + 1) % n]
            uv_face([centre, rings_[0][i], rings_[0][(i + 1) % n]], [uv(Vector((0, 0))), uv(a / 4), uv(b / 4)])
            for k in range(3):
                uv_face([rings_[k][i], rings_[k + 1][i], rings_[k + 1][(i + 1) % n], rings_[k][(i + 1) % n]],
                        [uv(a * (k + 1) / 4), uv(a * (k + 2) / 4), uv(b * (k + 2) / 4), uv(b * (k + 1) / 4)])
        finish([centre] + [v for ring in rings_ for v in ring], name, 'kettle')
    wrapped(enamel)

    def gilding():
        # A rolled rim that reaches down to the kettle and closes the plaque's edge.
        tube([at(p, .0004) for p in outline + outline[:1]], [.0042] * (len(outline) + 1), GOLD, 'kettle', sides=8, sub=1)
        # A fine inner line following the outline.
        inner = plaque_outline(.0075)
        tube([at(p, .0006) for p in inner + inner[:1]], [.0011] * (len(inner) + 1), GOLD, 'kettle', sides=5, sub=1,
             cap=False)
        # Beads on the end tips and the crests, and a smaller one sitting on the kettle in each notch.
        for x, z, r in ((PLAQUE_A + TIP, 0, .0068), (-PLAQUE_A - TIP, 0, .0068),
                        (0, PLAQUE_B + CREST, .0056), (0, -PLAQUE_B - CREST, .0056)):
            ellipsoid(at(Vector((x, z)), .0004), (r, r * .8, r), GOLD, 'kettle', seg=14, rings=9)
        for sx in (-1, 1):
            for sz in (-1, 1):
                ellipsoid(at(Vector((sx * PLAQUE_A, sz * PLAQUE_B)), -.0015), (.0038, .0035, .0038), GOLD, 'kettle',
                          seg=12, rings=8)
    wrapped(gilding)


logo_plaque()

# -------------------- the engraved brass teacup, held by its handle, with rising chai and a timed stream
REPEATS = 4  # the engraving's repeats round the cup
STRAP_REPEAT = .088 * CUP_SCALE  # handle length covered by one width of the strip texture


def inner_radius(h):
    return float(np.interp(h, [row[0] for row in INSIDE[::-1]], [row[1] for row in INSIDE[::-1]]))


def arc_lengths(rows):
    arc = [0.0]
    for (h0, r0), (h1, r1) in zip(rows, rows[1:]):
        arc.append(arc[-1] + math.hypot(h1 - h0, r1 - r0))
    return arc


def engraved_brass():
    """Polished brass with the engraving's colour, roughness/metal and normal maps."""
    rows = FOOT[-1:] + WALL
    arc = arc_lengths(rows)
    top = float(np.interp(ENGRAVING_TOP, [h for h, r in rows], arc))
    color, orm, normal = engraving.maps(round(top / arc[-1] * engraving.BAND_ROWS))
    name = material('Engraved_brass', engraving.POLISHED, .2, 1)
    nodes, links = bpy.data.materials[name].node_tree.nodes, bpy.data.materials[name].node_tree.links
    bsdf = nodes['Principled BSDF']

    def texture(suffix, pixels, data=True):
        node = nodes.new('ShaderNodeTexImage')
        node.image = kit.image(f'{name} {suffix}', pixels)
        if data:
            node.image.colorspace_settings.name = 'Non-Color'
        return node.outputs['Color']
    links.new(texture('color', kit.to_srgb(color), data=False), bsdf.inputs['Base Color'])
    separate = nodes.new('ShaderNodeSeparateColor')
    links.new(texture('surface', orm), separate.inputs['Color'])
    links.new(separate.outputs['Green'], bsdf.inputs['Roughness'])
    links.new(separate.outputs['Blue'], bsdf.inputs['Metallic'])
    bump = nodes.new('ShaderNodeNormalMap')
    links.new(texture('normal', normal), bump.inputs['Color'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return name


ENGRAVED = engraved_brass()


def cup_body(sides=96):
    """The bowl, foot and lip as one turned shell; the outer wall carries the engraved band."""
    rows = FOOT + WALL + LIP + INSIDE
    first, last = len(FOOT) - 1, len(FOOT) + len(WALL) - 1  # the engraved faces run between these rows
    arc = arc_lengths(rows)
    band_v = engraving.BAND_ROWS / engraving.SIZE
    v = [(a - arc[first]) / (arc[last] - arc[first]) * band_v for a in arc]
    rings = [[model.bm.verts.new(CUP_BASE + Vector((r * math.cos(a), r * math.sin(a), h)))
              for a in (HANDLE_AZIMUTH + TAU * j / sides for j in range(sides))] for h, r in rows]
    engraved = []
    for i in range(len(rows) - 1):
        for j in range(sides):
            u0, u1 = j / sides * REPEATS, (j + 1) / sides * REPEATS
            face = uv_face((rings[i][j], rings[i][(j + 1) % sides], rings[i + 1][(j + 1) % sides], rings[i + 1][j]),
                           ((u0, v[i]), (u1, v[i]), (u1, v[i + 1]), (u0, v[i + 1])))
            if first <= i < last:
                engraved.append(face)
    model.bm.faces.new(tuple(reversed(rings[0])))
    model.bm.faces.new(tuple(rings[-1]))
    finish([vert for ring in rings for vert in ring], GOLD, 'cup')
    index = next(k for k, m in enumerate(model.MATS) if m.name == ENGRAVED)
    for face in engraved:
        face.material_index = index


def catmull_rom(points, steps=6):
    padded = [points[0], *points, points[-1]]
    smooth = []
    for p0, p1, p2, p3 in zip(padded, padded[1:], padded[2:], padded[3:]):
        for k in range(steps):
            t = k / steps
            smooth.append(.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                                + (3 * p1 - p0 - 3 * p2 + p3) * t ** 3))
    return smooth + [points[-1]]


def strap(sides=20):
    """The handle: a squarish strap swept along HANDLE, with the leafy strip on both faces."""
    points = catmull_rom([CUP_BASE + s * OUT + h * UP for s, h in HANDLE])
    lengths = [0.0]
    for a, b in zip(points, points[1:]):
        lengths.append(lengths[-1] + (b - a).length)
    v0, v1 = engraving.STRIP[0] / engraving.SIZE, engraving.STRIP[1] / engraving.SIZE
    rings, coords = [], []
    for k, p in enumerate(points):
        along = (points[min(k + 1, len(points) - 1)] - points[max(k - 1, 0)]).normalized()
        across = SIDE.cross(along)
        # Widen the strap where it meets the wall, so it flows into the cup.
        flare = 1 + .35 * max(0.0, 1 - min(lengths[k], lengths[-1] - lengths[k]) / .007)
        ring, uv = [], []
        for j in range(sides):
            c, s = math.cos(TAU * j / sides), math.sin(TAU * j / sides)
            w, d = math.copysign(abs(c) ** .5, c), math.copysign(abs(s) ** .5, s)
            ring.append(model.bm.verts.new(p + across * STRAP_HALF_WIDTH * flare * w + SIDE * STRAP_HALF_THICKNESS * d))
            uv.append((lengths[k] / STRAP_REPEAT, v0 + (w + 1) / 2 * (v1 - v0)))
        rings.append(ring)
        coords.append(uv)
    for k in range(len(rings) - 1):
        for j in range(sides):
            jj = (j + 1) % sides
            uv_face((rings[k][j], rings[k][jj], rings[k + 1][jj], rings[k + 1][j]),
                    (coords[k][j], coords[k][jj], coords[k + 1][jj], coords[k + 1][j]))
    model.bm.faces.new(tuple(reversed(rings[0])))
    model.bm.faces.new(tuple(rings[-1]))
    finish([vert for ring in rings for vert in ring], ENGRAVED, 'cup')


cup_body()
strap()

# The chai is a thin disc just inside the bowl; `sip` slides it down and narrows it as it drains.
lathe(CUP_BASE, [(FULL - .003, inner_radius(FULL - .003) - .0014), (FULL, inner_radius(FULL) - .0008)],
      CHAI, 'liquid', sides=80)
tube([STREAM_START, STREAM_START + Vector((.001, .002, -.065)), END + Vector((.001, 0, .045)), END],
     [.0065, .0075, .007, .006], CHAI, 'stream', sides=9, sub=4)
torus(END, (0, 0, 1), .018, .0024, CHAI, 'stream', sides=24, cross=5)
for i in range(3):
    points = []
    for j in range(10):
        t = j / 9
        points.append(END + Vector(((i - 1) * .026 + .009 * math.sin(t * TAU + i),
                                    -.016 + .005 * math.cos(t * TAU + i), .008 + .14 * t)))
    tube(points, [.0012, .0018, .0022, .0024, .0024, .0022, .002, .0016, .001, .0003],
         STEAM, 'aroma', sides=6, sub=1)

uv_name = santa.data.uv_layers.active.name
props = model.props_object('Chai props', scene, uv_name)
model.new_mesh()


# Model the fingers in the handle's frame, with the cup foot as the origin.
def glove_point(out, side, height):
    return CUP_BASE + out * OUT + side * SIDE + height * UP


def glove_section(rows, sides=16, flat=1):
    profile = catmull_rom([Vector(row) for row in rows], steps=4)
    tube([glove_point(*row[:3]) for row in profile], [row[3] for row in profile],
         LEATHER, 'hand.L', sides=sides, sub=1, flat=flat)


# Each row is (out, depth, height, radius). The palm tapers into the fur cuff.
glove_section(((.241, -.028, .072, .002), (.238, -.023, .072, .038), (.238, -.009, .073, .060),
               (.241, .017, .073, .069), (.249, .044, .074, .066), (.258, .071, .077, .058),
               (.270, .093, .080, .046), (.278, .115, .081, .038), (.284, .139, .081, .032),
               (.287, .156, .081, .003)), sides=28, flat=.82)
# The thumb sits over the upper bar. The index crosses its front and hooks back through the
# opening. The other three fingers curl beneath the index, leaving the lower bar visible.
for finger in (
        ((.238, .028, .109, .030), (.220, .018, .140, .027), (.192, .004, .156, .022),
         (.166, -.003, .162, .018), (.151, -.004, .163, .015), (.141, -.003, .163, .008),
         (.138, -.002, .163, .002)),  # thumb
        ((.248, .027, .107, .028), (.221, -.024, .111, .026), (.179, -.034, .108, .023),
         (.152, -.026, .103, .021), (.140, -.010, .105, .017), (.141, .006, .118, .0135),
         (.147, .013, .125, .004)),  # index
        ((.251, .025, .082, .027), (.226, -.028, .073, .023), (.191, -.039, .069, .021),
         (.171, -.035, .066, .018), (.167, -.025, .067, .013), (.172, -.011, .067, .004)),  # middle
        ((.252, .025, .059, .025), (.228, -.029, .041, .021), (.199, -.039, .035, .019),
         (.182, -.027, .035, .015), (.181, -.015, .036, .010), (.186, -.005, .038, .003)),  # ring
        ((.250, .028, .042, .022), (.233, -.019, .018, .017), (.206, -.029, .010, .014),
         (.195, -.020, .012, .011), (.198, -.007, .018, .003))):  # little
    glove_section(finger)

# Blend the finger roots into a continuous leather surface and keep it light for mobile AR.
glove = model.props_object('Cup glove', scene, uv_name)
bpy.ops.object.select_all(action='DESELECT')
bpy.context.view_layer.objects.active = glove
glove.select_set(True)
remesh = glove.modifiers.new('Join finger roots', 'REMESH')
remesh.mode = 'VOXEL'
remesh.voxel_size = .0018
bpy.ops.object.modifier_apply(modifier=remesh.name)
smooth = glove.modifiers.new('Soften finger roots', 'SMOOTH')
smooth.factor, smooth.iterations = .55, 3
bpy.ops.object.modifier_apply(modifier=smooth.name)
glove.data.calc_loop_triangles()
decimate = glove.modifiers.new('Mobile mesh', 'DECIMATE')
decimate.ratio = min(1, 5000 / len(glove.data.loop_triangles))
bpy.ops.object.modifier_apply(modifier=decimate.name)
glove.vertex_groups['hand.L'].add(range(len(glove.data.vertices)), 1, 'REPLACE')

# Wrap the leather at fabric scale, with the UV seam on the back of the wrist.
center = glove_point(.237, .040, .072)
offsets = [v.co - center for v in glove.data.vertices]
angles = [math.atan2(v.dot(OUT), -v.dot(SIDE)) for v in offsets]
tile = .85 * model.TILE[LEATHER]
leather_index = glove.data.materials.find(LEATHER)
uv = glove.data.uv_layers.get(uv_name) or glove.data.uv_layers.new(name=uv_name)
for face in glove.data.polygons:
    face.use_smooth = True
    face.material_index = leather_index
    ring = [angles[i] for i in face.vertices]
    if max(ring) - min(ring) > math.pi:
        ring = [a % TAU for a in ring]
    for loop, index, angle in zip(face.loop_indices, face.vertices, ring):
        uv.data[loop].uv = (angle * .072 / tile, offsets[index].z / tile)

# Join the kettle, cup and both gloves onto Santa, bound rigidly to their bones.
bpy.ops.object.select_all(action='DESELECT')
props.select_set(True)
glove.select_set(True)
santa.select_set(True)
bpy.context.view_layer.objects.active = santa
bpy.ops.object.join()
santa.data.calc_loop_triangles()
assert all(v.groups and abs(sum(g.weight for g in v.groups) - 1) < 1e-4 for v in santa.data.vertices)
print(f'[model] Santa01 has {len(santa.data.vertices):,} vertices, {len(santa.data.loop_triangles):,} triangles',
      flush=True)


# -------------------- the loop
SOURCE_FRAMES = 300
FRAMES = 328
GAZE = END - CUP  # look at the chai surface, from the cup bone's origin
SIP_EYE_CONVERGENCE = .5  # soften the inward turn as the cup comes close
# Turn the raised cup with the forearm while keeping the broad side of the handle visible.
RAISE_TURN = -22.0


def smootherstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * t * (t * (6 * t - 15) + 10)


def ramp5(frame, a, b):
    return smootherstep((frame - a) / (b - a))


# 1. Easing: each gesture window is retimed toward a quintic ease in/out. A pose the pour reaches
# at time s appears at frame ease(s); `eased_source` inverts that for the frame being baked.
EASE_STRENGTH = .5
GESTURE_MARKERS = (1, 24, 60, 132, 168, 204, 240, 276, SOURCE_FRAMES)


def ease(u):
    """Eased progress for linear progress u through a gesture window."""
    lo, hi = 0.0, 1.0
    for _ in range(40):  # inverse of smootherstep
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if smootherstep(mid) < u else (lo, mid)
    return (1 - EASE_STRENGTH) * u + EASE_STRENGTH * (lo + hi) / 2


def eased_source(frame):
    for a, b in zip(GESTURE_MARKERS, GESTURE_MARKERS[1:]):
        if a <= frame <= b:
            target = (frame - a) / (b - a)
            lo, hi = 0.0, 1.0
            for _ in range(40):
                mid = (lo + hi) / 2
                lo, hi = (mid, hi) if ease(mid) < target else (lo, mid)
            return a + (lo + hi) / 2 * (b - a)
    return frame


def pour(s, frame):
    """Pose the pour and cup lift, then hold the cup through the nods and pause."""
    kettle_amount = kit.ramp(s, 24, 60) * (1 - kit.ramp(s, 132, 168))
    sip_settle = SIP_SETTLE * ramp5(frame, 244, DRINK_FINISH)
    cup_amount = kit.ramp(s, 168, 204) * (1 - sip_settle) * (1 - ramp5(frame, *CUP_RETURN))
    kpos = KETTLE.lerp(POUR_GRIP, kettle_amount)
    krot = Matrix.Rotation(math.radians(25) * kettle_amount, 3, 'Y')
    cpos = CUP.lerp(Vector((.002, -.347, 1.590)), cup_amount)
    crot = Matrix.Rotation(math.radians(RAISE_TURN) * cup_amount, 3, 'Z')
    kit.rigid('kettle', kpos, krot)
    kit.rigid('cup', cpos, crot)
    for side, pos, rot, origin in (('R', kpos, krot, KETTLE), ('L', cpos, crot, CUP)):
        hand = f'hand.{side}'
        grip_wrist = rig.data.bones[hand].head_local
        wrist = pos + rot @ (grip_wrist - origin)
        solve_arm(side, SHOULDERS[side], wrist)
        kit.rigid(hand, wrist, rot)
    inhale = math.sin(math.pi * max(0, min(1, (s - 204) / 36)))
    gaze_target = cpos + crot @ GAZE
    approval_nod = sum(degrees * window(frame, *timing) for timing, degrees in APPROVAL_NODS)
    kit.look(gaze_target, math.radians(1.5 * inhale * cup_amount + approval_nod))
    kit.aim_eyes(gaze_target, convergence=1 - (1 - SIP_EYE_CONVERGENCE) * cup_amount)
    warmth = kit.ramp(s, 128, 148) * (1 - kit.ramp(s, 270, 298))
    aroma = rig.pose.bones['aroma']
    aroma.scale = (max(.01, warmth), max(.01, warmth * (1 + .06 * math.sin(s * .12))), max(.01, warmth))
    aroma.rotation_quaternion = Matrix.Rotation(math.radians(5) * math.sin(s * .08) * warmth, 3, 'Y').to_quaternion()
    flow = kit.ramp(s, 62, 66) * (1 - kit.ramp(s, 125, 129))
    level = .42 + .58 * kit.ramp(s, 66, 125) - .58 * kit.ramp(s, 276, SOURCE_FRAMES)
    surface = LIQUID_BOTTOM.z + FILL_DEPTH * level
    length = (STREAM_START.z - surface) / (STREAM_START.z - END.z)
    rig.pose.bones['stream'].scale = (max(.01, flow), max(.01, flow * length), max(.01, flow))
    bpy.context.view_layer.update()
    return max(kettle_amount, cup_amount)


def sway(s, activity):
    """Layer 2: the shared secondary motion; the props follow the gloves that hold them."""
    held = {'hand.R': ('kettle', 'stream'), 'hand.L': ('cup',)}
    before = {n: rig.pose.bones[n].matrix.copy() for hand, props in held.items() for n in (hand, *props)}
    santa_motion.sway(rig, (s - 1) / (SOURCE_FRAMES - 1), activity)
    bpy.context.view_layer.update()
    for hand, props in held.items():
        delta = rig.pose.bones[hand].matrix @ before[hand].inverted()
        for name in props:
            rig.pose.bones[name].matrix = delta @ before[name]
    bpy.context.view_layer.update()


def chest_deform():
    chest = rig.pose.bones['chest']
    return chest.matrix @ chest.bone.matrix_local.inverted()


# 3. Counterlean while the kettle is up, in degrees about world Y at each bone's head.
SPINE_LEAN, CHEST_LEAN = .75, 1.2


def lean(frame):
    amount = ramp5(frame, 24, 60) * (1 - ramp5(frame, 132, 168))
    if amount < 1e-8:
        return
    hands = {side: rig.pose.bones['hand.' + side].matrix.copy() for side in 'LR'}
    for name, degrees in (('spine', SPINE_LEAN), ('chest', CHEST_LEAN)):
        bone = rig.pose.bones[name]
        pivot = bone.matrix.translation.copy()
        bone.matrix = (Matrix.Translation(pivot) @ Matrix.Rotation(math.radians(amount * degrees), 4, 'Y')
                       @ Matrix.Translation(-pivot) @ bone.matrix)
        bpy.context.view_layer.update()
    for side in 'RL':
        solve_arm(side, chest_deform() @ SHOULDERS[side], hands[side].translation.copy())
        rig.pose.bones['hand.' + side].matrix = hands[side]
        bpy.context.view_layer.update()


# 4. The sip. Santa faces -Y; a negative X rotation tips the rim toward his mouth. LIP_APPROACH puts
# the near side of the tipped rim in his open mouth, so from the front the cup hides the lower lip
# and its far side rises to the moustache.
CUP_TILT_DEGREES = 17.0
LIP_APPROACH = Vector((.018, .107, -.044))
APPROACH = (199, 217, 245, 257)  # rise, at the lips, then pull clear
TILT = (215, 229, 240, 255)
DRINK_START, DRINK_FINISH = 217, 248
FILL_START, FILL_FINISH = 65, 127
SIP_SETTLE = .063  # follow the rim down slightly as the last sip levels out
# Draw the cup forward, then dip it below the lower lip while Santa nods.
APPROVAL_CUP_OFFSET = Vector((.040, -.061, -.034))
APPROVAL_CUP_DROP = .10
APPROVAL_NODS = (((257, 266, 266, 276), 6.0), ((278, 287, 287, 297), 4.5))
CUP_RETURN = (309, 327)  # 12 frames of pause after the second nod recovers


def window(frame, a, b, c, d):
    return ramp5(frame, a, b) * (1 - ramp5(frame, c, d))


def chai_level(frame):
    """Empty before the pour and at the loop boundary; drains while he sips."""
    return max(0.0, ramp5(frame, FILL_START, FILL_FINISH) * (1 - ramp5(frame, DRINK_START, DRINK_FINISH)))


def sip(frame):
    cup, hand = rig.pose.bones['cup'], rig.pose.bones['hand.L']
    cup_before, hand_before = cup.matrix.copy(), hand.matrix.copy()
    pivot = cup_before.translation.copy()
    angle = math.radians(-CUP_TILT_DEGREES * window(frame, *TILT))
    withdrawal = window(frame, APPROACH[2], APPROACH[3], *CUP_RETURN)
    shift = LIP_APPROACH * window(frame, *APPROACH) + APPROVAL_CUP_OFFSET * withdrawal
    shift.z -= APPROVAL_CUP_DROP * window(frame, 249, APPROACH[3], *CUP_RETURN)
    # One rigid transform moves both the cup and the glove, so the grip cannot slip.
    delta = (Matrix.Translation(shift) @ Matrix.Translation(pivot)
             @ Matrix.Rotation(angle, 4, 'X') @ Matrix.Translation(-pivot))
    cup.matrix = delta @ cup_before
    bpy.context.view_layer.update()
    solve_arm('L', chest_deform() @ SHOULDERS['L'], (delta @ hand_before).translation)
    hand.matrix = delta @ hand_before
    level = chai_level(frame)
    # The chai's disc follows the bowl's inner wall down as it drains, and the last of it fades out.
    height = BOTTOM + FILL_DEPTH * level
    width = inner_radius(height) / inner_radius(FULL) * smootherstep(level / .08)
    rig.pose.bones['liquid'].scale = (max(.001, width), max(.001, level), max(.001, width))
    bpy.context.view_layer.update()
    # Stretch the stream from the spout down to the chai surface where the cup actually is now.
    stream = rig.pose.bones['stream']
    surface = cup.matrix @ cup.bone.matrix_local.inverted() @ (CUP_BASE + height * UP)
    flow = stream.scale.x
    stream.scale = (flow, flow * (stream.head.z - surface.z) / (STREAM_START.z - END.z), flow)
    if frame >= DRINK_START:
        aroma = rig.pose.bones['aroma']
        fade = 1 - ramp5(frame, 235, 255)
        # Collapse to the same 1% the pour uses at the start, so the loop closes exactly.
        aroma.scale = tuple(max(.01, a * fade) for a in aroma.scale)
    bpy.context.view_layer.update()


def pose_at(t):
    frame = round(1 + t * (FRAMES - 1))
    # Ease the extra time into the source motion after the cup clears his lips.
    source_frame = frame - (FRAMES - SOURCE_FRAMES) * ramp5(frame, APPROACH[3], FRAMES)
    s = eased_source(source_frame)
    sway(s, pour(s, frame))
    lean(frame)
    sip(frame)


kit.bake('Santa01_Natural_Shoulders_Drink_Cup_Tilt', FRAMES, pose_at, [b.name for b in rig.pose.bones], sway=False)

FRONT = ((2.15, -6.3, 2.75), (-.035, -.12, 1.05), 82, (800, 1000))
kit.finish('santa01', FRONT, [
    ('front', 1, FRONT),
    ('pour', 92, FRONT),
    ('sip', 229, FRONT),
    ('face', 1, ((-.20, -1.60, 1.85), (0, -.04, 1.75), 78, (600, 600))),
    ('kettle', 1, ((-.36, -1.45, 1.26), (-.43, -.52, 1.21), 85, (600, 600))),
    ('fabric', 229, ((.85, -1.35, 1.35), (.16, -.19, 1.18), 90, (700, 700))),
])
