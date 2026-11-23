"""Build Santa 01 on the base character: Santa pours chai from a brass kettle, then sips it.

blender -b --factory-startup --python-exit-code 1 -P build_santa01.py -- [preview_dir] [shot ...]

Needs santa_base.blend (build_santa_base.py). Writes santa01.blend, and with a preview folder the
previews and docs/santa01-poster.webp; name shots after the folder to render only those.

Santa 01 is modelled on photos/01 Chaiiwala Santa.jpg: a golden brass kettle with raised
"Chaiiwala / of London" lettering in his right glove, its own kettle grip, and a cutting-chai glass
in his cupped left glove. The 300-frame (12.5 s) loop is computed in one pass per frame, in layers:

1. The pour: the kettle lifts and pours a timed stream into the glass, then lowers; the glass rises
   toward his face; arms solve from the shoulders; head and eyes follow the glass. It is evaluated
   at an eased time, so each gesture eases in and out (EASE_STRENGTH).
2. The shared secondary sway from santa_motion.py (body, coat, sleeves, hat tip, feet) at that
   eased time, with the kettle, stream and glass following the gloves that hold them.
3. A subtle torso counterlean while the kettle is up: its shoulder rises and the glass shoulder
   drops; the arms re-solve to the same wrists, so neither prop moves.
4. The sip: the glass comes to his lips and tips about 17 degrees, the left glove gripping it. The
   chai fills while it is poured and drains while he sips, so the glass is empty at both ends of
   the loop, and the steam fades with the last sip.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bmesh  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import santa_kit as kit  # noqa: E402
import santa_model as model  # noqa: E402
import santa_motion  # noqa: E402
from santa_model import (BRASS, CUP, GOLD, KETTLE, LEATHER, SHOULDERS, TAU, WRISTS, add_bone,  # noqa: E402
                         ellipsoid, finish, lathe, material, torus, tube, uv_face)

# -------------------- prop bones, on top of the base rig
POUR_GRIP = Vector((-.18, -.49, 1.73))
POUR_ROT = Matrix.Rotation(math.radians(25), 3, 'Y')
SPOUT_LOCAL = Vector((.44, -.012, -.16))
STREAM_START = POUR_GRIP + POUR_ROT @ SPOUT_LOCAL
TEA_BONES = [
    ('kettle', KETTLE, KETTLE + Vector((0, 0, .12)), 'root'),
    ('cup', CUP, CUP + Vector((0, 0, .12)), 'root'),
    ('liquid', CUP + Vector((0, 0, -.075)), CUP + Vector((0, 0, .025)), 'cup'),
    ('aroma', CUP + Vector((0, 0, .09)), CUP + Vector((0, 0, .19)), 'cup'),
    ('stream', STREAM_START, STREAM_START + Vector((0, 0, -.2)), 'root'),
]
scene, rig, santa = kit.start(1, 'ChaiBreak', 'photos/01 Chaiiwala Santa.jpg', TEA_BONES)
for bone in TEA_BONES:
    add_bone(*bone)

# The base mirrors the cupped glove onto the right hand; Santa 01's right glove grips the kettle.
mesh = bmesh.new()
mesh.from_mesh(santa.data)
skin = mesh.verts.layers.deform.active
right = santa.vertex_groups['hand.R'].index
bmesh.ops.delete(mesh, geom=[v for v in mesh.verts if v[skin].get(right, 0) > .5], context='VERTS')
mesh.to_mesh(santa.data)
mesh.free()

model.reuse_materials()
CHAI = material('Masala_chai', (.50, .23, .085), .2)
GLASS = material('Clear_glass', (.45, .57, .62), .10, alpha=.14)
STEAM = material('Chai_aroma', (.63, .59, .54), .9, alpha=.18)
ENGRAVE = material('Engraved_lettering', (.075, .040, .014), .45, .4)
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

# -------------------- golden brass chai kettle with a decorative cartouche
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
CW, CH = .125, .078  # cartouche half-width (along the kettle's curve) and half-height
for z in (-.085, .052):
    for k in range(12):
        a = math.pi + math.pi * k / 11
        if abs(.166 * (a - 1.5 * math.pi)) < CW + .014:
            continue  # leave room for the cartouche
        c = body + Vector((.166 * math.cos(a), .166 * math.sin(a), z))
        tangent = Vector((-math.sin(a), math.cos(a), 0))
        points = [c + tangent * (j - .5) * .018 + Vector((0, 0, .006 * math.sin(j * TAU))) for j in (0, .25, .5, .75, 1)]
        tube(points, [.0012] * 5, GOLD, 'kettle', sides=4, sub=1)
# Raised oval cartouche with a beaded border, a kettle-and-glass emblem and "Chaiiwala / of London"
# lettering. Everything is modelled flat on the plane y = -R0 and then wrapped onto the kettle's curve.
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

def lettering(text, width, center, shear=0, depth=.0012):
    """Raised text from Blender's built-in font, scaled to `width` and centred on `center`."""
    curve = bpy.data.curves.new('lettering', 'FONT')
    curve.body = text; curve.align_x = 'CENTER'; curve.align_y = 'CENTER'; curve.shear = shear
    ob = bpy.data.objects.new('lettering', curve); scene.collection.objects.link(ob)
    def evaluate():
        bpy.context.view_layer.update()
        return bpy.data.meshes.new_from_object(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    flat = evaluate()
    xs = [v.co.x for v in flat.vertices]
    scale = width / (max(xs) - min(xs))
    bpy.data.meshes.remove(flat)
    curve.size = scale; curve.extrude = depth / 2
    mesh_data = evaluate()
    bpy.data.objects.remove(ob); bpy.data.curves.remove(curve)
    verts = [model.bm.verts.new(center + Vector((v.co.x, -(v.co.z + depth / 2), v.co.y))) for v in mesh_data.vertices]
    for poly in mesh_data.polygons:
        try:
            uv_face([verts[i] for i in poly.vertices], [(0, 0)] * len(poly.vertices))
        except ValueError:
            pass
    bpy.data.meshes.remove(mesh_data)
    finish(verts, ENGRAVE, 'kettle')

cart = body + Vector((0, -R0, -.012))
face_y = -.0050
wrapped(lambda: ellipsoid(cart, (CW, .005, CH), BRASS, 'kettle', seg=48, rings=16))
wrapped(lambda: torus(cart + Vector((0, face_y, 0)), (0, 1, 0), CW, .0040, GOLD, 'kettle', sides=64, cross=6, depth=CH))
def beads():
    for k in range(40):
        a = TAU * k / 40
        ellipsoid(cart + Vector(((CW - .011) * math.cos(a), face_y - .0015, (CH - .010) * math.sin(a))),
                  (.0026, .0019, .0026), GOLD, 'kettle', seg=8, rings=5)
wrapped(beads)
def emblem():
    # A tiny kettle pouring into a cutting-chai glass, drawn as raised wire lines.
    c = cart + Vector((-.010, face_y - .0008, .036))
    line = lambda pts, r=.0018: tube([c + Vector((px * 2.0, 0, pz * 2.0)) for px, pz in pts], [r] * len(pts), ENGRAVE, 'kettle', sides=6, sub=1)
    ring = [(-.010 + .0085 * math.cos(TAU * k / 16), .0075 * math.sin(TAU * k / 16)) for k in range(17)]
    line(ring)
    line([(-.010 + .0085 * math.cos(math.pi * k / 8), .0075 + .006 * math.sin(math.pi * k / 8)) for k in range(9)])
    line([(-.002, -.002), (.006, .002), (.010, .007)])
    line([(.012, -.009), (.020, -.009), (.022, .004), (.010, .004), (.012, -.009)])
lettering_center = cart + Vector((0, face_y, 0))
wrapped(emblem)
wrapped(lambda: lettering('Chaiiwala', .190, lettering_center + Vector((0, 0, -.008)), shear=.22, depth=.0022))
wrapped(lambda: lettering('of London', .088, lettering_center + Vector((0, 0, -.050)), shear=.15, depth=.0018))

# -------------------- cutting-chai glass, rising chai level and timed stream
profile = [(-.09, .045), (-.085, .05), (.078, .066), (.09, .066), (.09, .062), (.078, .062), (-.078, .047), (-.08, .006)]
lathe(CUP, profile, GLASS, 'cup', sides=48, flute=.0015)
torus(CUP + Vector((0, 0, .089)), (0, 0, 1), .064, .0028, GLASS, 'cup', sides=48, cross=8)
torus(CUP + Vector((0, 0, -.085)), (0, 0, 1), .047, .004, GLASS, 'cup', sides=40, cross=6)
lathe(CUP, [(-.075, .044), (.049, .059), (.052, .058)], CHAI, 'liquid', sides=48, flute=.0004)
end = CUP + Vector((0, 0, .048))
tube([STREAM_START, STREAM_START + Vector((.001, .002, -.065)), end + Vector((.001, 0, .045)), end],
     [.0065, .0075, .007, .006], CHAI, 'stream', sides=9, sub=4)
torus(end, (0, 0, 1), .018, .0024, CHAI, 'stream', sides=24, cross=5)
for i in range(3):
    points = []
    for j in range(10):
        t = j / 9
        points.append(CUP + Vector(((i - 1) * .018 + .009 * math.sin(t * TAU + i),
                                    -.012 + .005 * math.cos(t * TAU + i), .092 + .13 * t)))
    tube(points, [.0012, .0018, .0022, .0024, .0024, .0022, .002, .0016, .001, .0003],
         STEAM, 'aroma', sides=6, sub=1)

# Join the kettle, kettle grip and glass onto Santa, bound rigidly to their bones.
props = model.props_object('Chai props', scene, santa.data.uv_layers.active.name)
bpy.ops.object.select_all(action='DESELECT')
props.select_set(True)
santa.select_set(True)
bpy.context.view_layer.objects.active = santa
bpy.ops.object.join()
santa.data.calc_loop_triangles()
assert all(v.groups and abs(sum(g.weight for g in v.groups) - 1) < 1e-4 for v in santa.data.vertices)
print(f'[model] Santa01 has {len(santa.data.vertices):,} vertices, {len(santa.data.loop_triangles):,} triangles',
      flush=True)


# -------------------- the loop
FRAMES = 300
GAZE = Vector((0, 0, .06))  # look at the chai surface/rim, just above the glass's bone origin
END = CUP + Vector((0, 0, .048))  # where the stream meets a full glass


def smootherstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * t * (t * (6 * t - 15) + 10)


def ramp5(frame, a, b):
    return smootherstep((frame - a) / (b - a))


# 1. Easing: each gesture window is retimed toward a quintic ease in/out. A pose the pour reaches
# at time s appears at frame ease(s); `eased_source` inverts that for the frame being baked.
EASE_STRENGTH = .5
GESTURE_MARKERS = (1, 24, 60, 132, 168, 204, 240, 276, 300)


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


def pour(s):
    """Layer 1 at (eased) source time s: approach, pour, lower kettle, raise glass, return."""
    kettle_amount = kit.ramp(s, 24, 60) * (1 - kit.ramp(s, 132, 168))
    cup_amount = kit.ramp(s, 168, 204) * (1 - kit.ramp(s, 240, 276))
    kpos = KETTLE.lerp(POUR_GRIP, kettle_amount)
    krot = Matrix.Rotation(math.radians(25) * kettle_amount, 3, 'Y')
    cpos = CUP.lerp(Vector((.030, -.355, 1.590)), cup_amount)
    crot = Matrix.Identity(3)
    kit.rigid('kettle', kpos, krot)
    kit.rigid('cup', cpos, crot)
    for side, pos, rot, origin in (('R', kpos, krot, KETTLE), ('L', cpos, crot, CUP)):
        wrist = pos + rot @ (WRISTS[side] - origin)
        solve_arm(side, SHOULDERS[side], wrist)
        kit.rigid(f'hand.{side}', wrist, rot)
    inhale = math.sin(math.pi * max(0, min(1, (s - 204) / 36)))
    kit.look(cpos + GAZE, math.radians(1.5 * inhale) * cup_amount)
    kit.aim_eyes(cpos + GAZE)
    warmth = kit.ramp(s, 128, 148) * (1 - kit.ramp(s, 270, 298))
    aroma = rig.pose.bones['aroma']
    aroma.scale = (max(.01, warmth), max(.01, warmth * (1 + .06 * math.sin(s * .12))), max(.01, warmth))
    aroma.rotation_quaternion = Matrix.Rotation(math.radians(5) * math.sin(s * .08) * warmth, 3, 'Y').to_quaternion()
    flow = kit.ramp(s, 62, 66) * (1 - kit.ramp(s, 125, 129))
    level = .42 + .58 * kit.ramp(s, 66, 125) - .58 * kit.ramp(s, 276, 300)
    surface = CUP.z - .075 + .127 * level
    length = (STREAM_START.z - surface) / (STREAM_START.z - END.z)
    rig.pose.bones['stream'].scale = (max(.01, flow), max(.01, flow * length), max(.01, flow))
    bpy.context.view_layer.update()
    return max(kettle_amount, cup_amount)


def sway(s, activity):
    """Layer 2: the shared secondary motion; the props follow the gloves that hold them."""
    held = {'hand.R': ('kettle', 'stream'), 'hand.L': ('cup',)}
    before = {n: rig.pose.bones[n].matrix.copy() for hand, props in held.items() for n in (hand, *props)}
    santa_motion.sway(rig, (s - 1) / (FRAMES - 1), activity)
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


# 4. The sip. Santa faces -Y; a negative X rotation tips the rim toward his mouth.
CUP_TILT_DEGREES = 17.0
LIP_APPROACH = Vector((-.012, .075, -.015))
APPROACH = (199, 217, 248, 266)  # rise, at the lips, lower, back down
TILT = (215, 229, 240, 255)
DRINK_START, DRINK_FINISH = 217, 248
FILL_START, FILL_FINISH = 65, 127


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
    # One rigid transform moves both the glass and the glove, so the grip cannot slip.
    delta = (Matrix.Translation(LIP_APPROACH * window(frame, *APPROACH)) @ Matrix.Translation(pivot)
             @ Matrix.Rotation(angle, 4, 'X') @ Matrix.Translation(-pivot))
    cup.matrix = delta @ cup_before
    bpy.context.view_layer.update()
    solve_arm('L', chest_deform() @ SHOULDERS['L'], (delta @ hand_before).translation)
    hand.matrix = delta @ hand_before
    level = chai_level(frame)
    width = smootherstep(level / .06)  # narrow the last of the chai as the glass empties
    rig.pose.bones['liquid'].scale = (max(.001, width), max(.001, level), max(.001, width))
    bpy.context.view_layer.update()
    # Stretch the stream from the spout down to the chai surface where the glass actually is now.
    stream = rig.pose.bones['stream']
    surface = cup.matrix @ cup.bone.matrix_local.inverted() @ Vector((CUP.x, CUP.y, CUP.z - .075 + .127 * level))
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
    s = eased_source(frame)
    sway(s, pour(s))
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
