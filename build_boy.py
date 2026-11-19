"""
Procedural, rigged boy for Blender (tested on Blender 4.3).

Run headless:
    blender -b --factory-startup -P build_boy.py -- [preview_dir]

Produces boy_rigged.blend next to this script:
  * "Boy"      - one mesh, multiple materials, vertex groups per bone,
                   Armature + Subdivision modifiers
  * "Boy_Rig"  - armature (root, hips, spine, chest, neck, head,
                   shoulder/upper_arm/forearm/hand .L/.R, thigh/shin/foot .L/.R)
  * "Boy_Wave" - a small waving animation (frames 1-60)
  * camera + sun light
If preview_dir is given, a few Workbench renders are written there.
"""
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix, Quaternion, Euler

HERE = os.path.dirname(os.path.abspath(__file__))
ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
PREVIEW_DIR = ARGV[0] if ARGV else None
BLEND_PATH = os.path.join(HERE, "boy_rigged.blend")

# ---------------------------------------------------------------- clean scene
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.armatures,
             bpy.data.cameras, bpy.data.lights, bpy.data.actions):
    for block in list(coll):
        coll.remove(block)
scene = bpy.context.scene

# ---------------------------------------------------------------- skeleton
# name, head, tail, parent, deform, connected   (left side = +X, Boy faces -Y)
CENTER_BONES = [
    ("root",  (0, 0, 0),     (0, 0.2, 0),   None,    False, False),
    ("hips",  (0, 0, 0.66),  (0, 0, 0.78),  "root",  True,  False),
    ("spine", (0, 0, 0.78),  (0, 0, 0.94),  "hips",  True,  True),
    ("chest", (0, 0, 0.94),  (0, 0, 1.065), "spine", True,  True),
    ("neck",  (0, 0, 1.065), (0, 0, 1.13),  "chest", True,  True),
    ("head",  (0, 0, 1.13),  (0, 0, 1.36),  "neck",  True,  True),
]
LEFT_BONES = [
    ("shoulder",  (0.035, 0, 1.015),   (0.155, 0, 1.015),  "chest",     False),
    ("upper_arm", (0.155, 0, 1.015),   (0.32, 0, 0.845),   "shoulder",  True),
    ("forearm",   (0.32, 0, 0.845),    (0.40, -0.025, 0.68), "upper_arm", True),
    ("hand",      (0.40, -0.025, 0.68), (0.425, -0.03, 0.60), "forearm", True),
    ("thigh",     (0.085, 0, 0.66),   (0.09, 0, 0.36),    "hips",      False),
    ("shin",      (0.09, 0, 0.36),    (0.09, 0.015, 0.10), "thigh",    True),
    ("foot",      (0.09, 0.015, 0.10), (0.09, -0.09, 0.045), "shin",   True),
]
CENTER_PARENTS = {"hips", "chest", "spine", "head", "neck", "root"}

BONES = list(CENTER_BONES)
for side, s in (("L", 1), ("R", -1)):
    for name, h, t, parent, conn in LEFT_BONES:
        par = parent if parent in CENTER_PARENTS else f"{parent}.{side}"
        BONES.append((f"{name}.{side}", (h[0] * s, h[1], h[2]), (t[0] * s, t[1], t[2]),
                      par, True, conn))

SEG = {b[0]: (Vector(b[1]), Vector(b[2])) for b in BONES}
DEFORM = [b[0] for b in BONES if b[4]]
GIDX = {n: i for i, n in enumerate(DEFORM)}

# ---------------------------------------------------------------- materials
MAT_DEFS = {
    "Shirt_Blue": dict(color=(0.035, 0.30, 0.66), rough=0.8),
    "Rib_Blue":   dict(color=(0.025, 0.19, 0.44), rough=0.85),
    "Denim":      dict(color=(0.035, 0.075, 0.17), rough=0.9),
    "Skin":       dict(color=(0.72, 0.44, 0.27), rough=0.65),
    "Cheek":      dict(color=(0.73, 0.33, 0.24), rough=0.7),
    "Hair":       dict(color=(0.075, 0.032, 0.018), rough=0.85),
    "Hair_Light": dict(color=(0.12, 0.055, 0.028), rough=0.85),
    "White":      dict(color=(0.94, 0.95, 0.93), rough=0.7),
    "Sneaker":    dict(color=(0.045, 0.12, 0.23), rough=0.8),
    "Yellow":     dict(color=(1.0, 0.65, 0.06), rough=0.65),
    "Eye":        dict(color=(0.012, 0.008, 0.006), rough=0.25),
    "Smile":      dict(color=(0.24, 0.075, 0.045), rough=0.8),
}
MAT_NAMES = list(MAT_DEFS)
for name, d in MAT_DEFS.items():
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*d["color"], 1.0)
    m.roughness = d["rough"]
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = getattr(m, "node_tree", None)
    bsdf = nt.nodes.get("Principled BSDF") if nt else None
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*d["color"], 1.0)
        bsdf.inputs["Roughness"].default_value = d["rough"]
        bsdf.inputs["Metallic"].default_value = d.get("metal", 0.0)

# ---------------------------------------------------------------- geometry helpers
bm = bmesh.new()
DL = bm.verts.layers.deform.verify()


def seg_dist(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
    return (a + ab * t - p).length


def auto_weights(p, cands, power=4):
    ws = {c: 1.0 / (seg_dist(p, *SEG[c]) ** power + 1e-9) for c in cands}
    tot = sum(ws.values())
    ws = {k: v / tot for k, v in ws.items() if v / tot > 0.01}
    tot = sum(ws.values())
    return {k: v / tot for k, v in ws.items()}


def finish(verts, mat, cands=None, wfn=None, smooth=True):
    mi = MAT_NAMES.index(mat)
    faces = set()
    for v in verts:
        faces.update(v.link_faces)
        w = wfn(v.co) if wfn else auto_weights(v.co, cands)
        for k, val in w.items():
            v[DL][GIDX[k]] = val
    for f in faces:
        f.material_index = mi
        f.smooth = smooth


def rot_from(direction=None, euler=None):
    if direction is not None:
        return Vector(direction).normalized().to_track_quat('Z', 'Y').to_matrix()
    if euler is not None:
        return Euler([math.radians(a) for a in euler]).to_matrix()
    return Matrix.Identity(3)


def ellipsoid(center, radii, mat, cands=None, wfn=None, direction=None, euler=None,
              segs=24, rings=14):
    M = Matrix.Translation(center) @ rot_from(direction, euler).to_4x4() \
        @ Matrix.Diagonal((*radii, 1.0))
    res = bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings,
                                    radius=1.0, matrix=M)
    finish(res["verts"], mat, cands, wfn)


def tube(points, radii, mat, cands=None, wfn=None, subdiv=4, segs=16):
    pts = [Vector(p) for p in points]
    P, R = [], []
    for i in range(len(pts) - 1):
        for k in range(subdiv):
            t = k / subdiv
            P.append(pts[i].lerp(pts[i + 1], t))
            R.append(radii[i] + (radii[i + 1] - radii[i]) * t)
    P.append(pts[-1]); R.append(radii[-1])
    T = [(P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]).normalized() for i in range(len(P))]
    up = Vector((0, 0, 1)) if abs(T[0].z) < 0.9 else Vector((1, 0, 0))
    n = T[0].cross(up).normalized()
    rings_v = []
    for p, r, t in zip(P, R, T):
        n = (n - t * n.dot(t)).normalized()          # parallel transport
        b = t.cross(n)
        rings_v.append([bm.verts.new(p + (n * math.cos(a) + b * math.sin(a)) * r)
                        for a in (2 * math.pi * j / segs for j in range(segs))])
    verts = [v for ring in rings_v for v in ring]
    for r0, r1 in zip(rings_v, rings_v[1:]):
        for j in range(segs):
            bm.faces.new((r0[j], r0[(j + 1) % segs], r1[(j + 1) % segs], r1[j]))
    for ring, p in ((rings_v[0], P[0]), (rings_v[-1], P[-1])):
        c = bm.verts.new(p)
        verts.append(c)
        for j in range(segs):
            bm.faces.new((ring[j], ring[(j + 1) % segs], c))
    finish(verts, mat, cands, wfn)


def torus(center, normal, major, minor, mat, cands=None, wfn=None, major_b=None,
          segs=32, msegs=10):
    rot = rot_from(direction=normal)
    c = Vector(center)
    a, bb = major, (major_b or major)
    rings = []
    for i in range(segs):
        u = 2 * math.pi * i / segs
        rc = Vector((a * math.cos(u), bb * math.sin(u), 0))
        radial = Vector((math.cos(u), math.sin(u), 0))
        rings.append([bm.verts.new(c + rot @ (rc + radial * minor * math.cos(v)
                                              + Vector((0, 0, minor * math.sin(v)))))
                      for v in (2 * math.pi * j / msegs for j in range(msegs))])
    for i in range(segs):
        r0, r1 = rings[i], rings[(i + 1) % segs]
        for j in range(msegs):
            bm.faces.new((r0[j], r0[(j + 1) % msegs], r1[(j + 1) % msegs], r1[j]))
    finish([v for r in rings for v in r], mat, cands, wfn)


# ---------------------------------------------------------------- body
# Child proportions: about 1.45 m tall, with a larger head and a slim torso.
TORSO = ["hips", "spine", "chest"]
# One continuous surface keeps the front of the sweatshirt smooth.
shirt_rings = []
for z, width, depth in ((0.68, 0.15, 0.102), (0.70, 0.16, 0.11),
                         (0.76, 0.165, 0.115), (0.86, 0.175, 0.125),
                         (0.96, 0.175, 0.12), (1.015, 0.16, 0.10),
                         (1.05, 0.10, 0.07), (1.065, 0.06, 0.052)):
    shirt_rings.append([bm.verts.new((width * math.cos(a), depth * math.sin(a), z))
                        for a in (math.tau * j / 32 for j in range(32))])
for lower, upper in zip(shirt_rings, shirt_rings[1:]):
    for j in range(32):
        bm.faces.new((lower[j], lower[(j + 1) % 32], upper[(j + 1) % 32], upper[j]))
bm.faces.new(tuple(reversed(shirt_rings[0])))
bm.faces.new(tuple(shirt_rings[-1]))
finish([v for ring in shirt_rings for v in ring], "Shirt_Blue", TORSO)
torus((0, 0, 0.695), (0, 0, 1), 0.154, 0.013, "Rib_Blue", TORSO, major_b=0.104)
ellipsoid((0, 0, 0.655), (0.145, 0.10, 0.10), "Denim", ["hips"])

# Neck, ribbed collar, and a small sunshine emblem on the sweatshirt.
ellipsoid((0, 0, 1.09), (0.055, 0.055, 0.075), "Skin", ["neck", "head"])
torus((0, 0, 1.06), (0, 0, 1), 0.065, 0.014, "Rib_Blue", ["chest", "neck"])
ellipsoid((0, -0.123, 0.94), (0.037, 0.008, 0.037), "Yellow", ["chest"], segs=20)
for i in range(8):
    angle = i * math.tau / 8
    dx, dz = math.cos(angle), math.sin(angle)
    tube([(dx * 0.044, -0.124, 0.94 + dz * 0.044),
          (dx * 0.055, -0.124, 0.94 + dz * 0.055)],
         [0.004, 0.004], "Yellow", ["chest"], subdiv=1, segs=8)

# ---------------------------------------------------------------- head
HEAD = ["head"]
ellipsoid((0, 0, 1.245), (0.143, 0.132, 0.17), "Skin", HEAD, segs=32, rings=20)
for side in (1, -1):
    ellipsoid((0.14 * side, 0, 1.245), (0.028, 0.027, 0.043), "Skin", HEAD)
    ellipsoid((0.158 * side, -0.017, 1.245), (0.011, 0.012, 0.025), "Cheek", HEAD)
    # Open eyes with dark pupils and small catchlights.
    ellipsoid((0.052 * side, -0.122, 1.272), (0.032, 0.018, 0.038), "White", HEAD)
    ellipsoid((0.049 * side, -0.139, 1.271), (0.015, 0.01, 0.022), "Eye", HEAD)
    ellipsoid((0.049 * side - 0.004, -0.148, 1.28), (0.005, 0.004, 0.006), "White", HEAD,
              segs=12, rings=8)
    ellipsoid((0.052 * side, -0.113, 1.323), (0.033, 0.012, 0.008), "Hair", HEAD,
              euler=(0, -8 * side, 0))
    ellipsoid((0.088 * side, -0.107, 1.218), (0.025, 0.009, 0.017), "Cheek", HEAD)
ellipsoid((0, -0.137, 1.235), (0.021, 0.027, 0.025), "Skin", HEAD)
tube([(-0.044, -0.115, 1.183), (-0.024, -0.124, 1.171),
      (0, -0.127, 1.167), (0.024, -0.124, 1.171), (0.044, -0.115, 1.183)],
     [0.004] * 5, "Smile", HEAD, subdiv=3, segs=8)

# Short brown hair: back, crown, sideburns, and a swept fringe above the eyebrows.
ellipsoid((0, 0.045, 1.29), (0.145, 0.105, 0.145), "Hair", HEAD)
ellipsoid((0, 0, 1.375), (0.15, 0.125, 0.07), "Hair", HEAD)
for side in (1, -1):
    ellipsoid((0.132 * side, 0.006, 1.298), (0.022, 0.08, 0.075), "Hair", HEAD)
ellipsoid((-0.058, -0.095, 1.365), (0.088, 0.048, 0.047), "Hair_Light", HEAD,
          euler=(0, -18, 0))
ellipsoid((0.047, -0.097, 1.382), (0.08, 0.044, 0.043), "Hair", HEAD,
          euler=(0, 22, 0))

# ---------------------------------------------------------------- limbs
for side, sign in (("L", 1), ("R", -1)):
    X = lambda p: (p[0] * sign, p[1], p[2])
    b = lambda n: f"{n}.{side}"
    # Sleeves, cuffs, bare hands, and thumbs.
    tube([X((0.14, 0, 1.015)), X((0.32, 0, 0.845)), X((0.393, -0.023, 0.695))],
         [0.065, 0.052, 0.043], "Shirt_Blue", [b("upper_arm"), b("forearm")], subdiv=5)
    torus(X((0.393, -0.023, 0.695)), X((0.08, -0.025, -0.165)),
          0.04, 0.011, "Rib_Blue", [b("forearm")])
    ellipsoid(X((0.415, -0.029, 0.635)), (0.035, 0.029, 0.055), "Skin", [b("hand")],
              direction=X((0.025, -0.005, -0.08)))
    ellipsoid(X((0.388, -0.052, 0.652)), (0.016, 0.017, 0.028), "Skin", [b("hand")],
              direction=X((-0.2, -0.3, -1)))
    # Jeans and low-top sneakers, including soles, tongues, and laces.
    tube([X((0.085, 0, 0.68)), X((0.09, 0, 0.36)), X((0.09, 0.015, 0.105))],
         [0.075, 0.061, 0.053], "Denim", ["hips", b("thigh"), b("shin")], subdiv=5)
    ellipsoid(X((0.09, -0.042, 0.037)), (0.065, 0.118, 0.035), "White", [b("foot")])
    ellipsoid(X((0.09, -0.035, 0.065)), (0.061, 0.11, 0.048), "Sneaker", [b("foot")])
    ellipsoid(X((0.09, -0.015, 0.104)), (0.025, 0.047, 0.014), "White", [b("foot")])
    for y in (-0.045, -0.025, -0.005):
        tube([X((0.069, y, 0.115)), X((0.111, y, 0.115))],
             [0.003, 0.003], "White", [b("foot")], subdiv=1, segs=8)

bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

# ---------------------------------------------------------------- objects
me = bpy.data.meshes.new("Boy_Mesh")
bm.to_mesh(me)
bm.free()
for n in MAT_NAMES:
    me.materials.append(bpy.data.materials[n])
boy = bpy.data.objects.new("Boy", me)
scene.collection.objects.link(boy)
for n in DEFORM:
    boy.vertex_groups.new(name=n)

arm_data = bpy.data.armatures.new("Boy_Rig")
rig = bpy.data.objects.new("Boy_Rig", arm_data)
scene.collection.objects.link(rig)
rig.show_in_front = True
bpy.context.view_layer.objects.active = rig
rig.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
for name, h, t, parent, deform, conn in BONES:
    eb = arm_data.edit_bones.new(name)
    eb.head, eb.tail, eb.use_deform = h, t, deform
    if parent:
        eb.parent = arm_data.edit_bones[parent]
        eb.use_connect = conn
bpy.ops.object.mode_set(mode='OBJECT')

boy.parent = rig
mod = boy.modifiers.new("Armature", 'ARMATURE')
mod.object = rig
sub = boy.modifiers.new("Subdivision", 'SUBSURF')
sub.levels, sub.render_levels = 1, 2

for pb in rig.pose.bones:
    pb.rotation_mode = 'QUATERNION'

# sanity: every vertex weighted
unweighted = sum(1 for v in me.vertices if not v.groups)
print(f"[boy] verts={len(me.vertices)} faces={len(me.polygons)} unweighted={unweighted}")


# ---------------------------------------------------------------- wave animation
def q_world(bone, axis, deg):
    B = rig.data.bones[bone].matrix_local.to_3x3()
    return Quaternion((B.inverted() @ Vector(axis)).normalized(), math.radians(deg))


rig.animation_data_create()
KEYS = {  # frame: {bone: (axis, degrees)}
    1:  {"upper_arm.R": ((0, 1, 0), 0),   "forearm.R": ((0, 1, 0), 0),   "head": ((0, 1, 0), 0)},
    12: {"upper_arm.R": ((0, 1, 0), 115), "forearm.R": ((0, 1, 0), 10),  "head": ((0, 1, 0), 8)},
    20: {"forearm.R": ((0, 1, 0), 35)},
    28: {"forearm.R": ((0, 1, 0), -15)},
    36: {"forearm.R": ((0, 1, 0), 35)},
    44: {"forearm.R": ((0, 1, 0), -15), "head": ((0, 1, 0), -6)},
    52: {"upper_arm.R": ((0, 1, 0), 115), "forearm.R": ((0, 1, 0), 10)},
    60: {"upper_arm.R": ((0, 1, 0), 0),   "forearm.R": ((0, 1, 0), 0),   "head": ((0, 1, 0), 0)},
}
for f, bones in KEYS.items():
    for bone, (axis, deg) in bones.items():
        pb = rig.pose.bones[bone]
        pb.rotation_quaternion = q_world(bone, axis, deg)
        pb.keyframe_insert("rotation_quaternion", frame=f)
act = rig.animation_data.action
act.name = "Boy_Wave"
act.use_fake_user = True
scene.frame_start, scene.frame_end = 1, 60
scene.frame_set(1)

# ---------------------------------------------------------------- camera / light / world
cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
scene.collection.objects.link(cam)
cam.location = (1.45, -3.5, 1.25)
cam.data.lens = 65
cam.rotation_euler = (Vector((0, 0, 0.73)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam
sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", 'SUN'))
sun.data.energy = 3.5
sun.rotation_euler = (math.radians(50), 0, math.radians(35))
scene.collection.objects.link(sun)
world = bpy.data.worlds.new("World")
world.color = (0.25, 0.3, 0.38)
scene.world = world
try:
    wnt = world.node_tree
    if wnt and wnt.nodes.get("Background"):
        wnt.nodes["Background"].inputs["Color"].default_value = (0.25, 0.3, 0.38, 1)
except Exception:
    pass
for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try:
        scene.render.engine = eng
        break
    except TypeError:
        pass

rig.select_set(False)
bpy.context.view_layer.objects.active = rig
bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH, compress=True)
print(f"[boy] saved {BLEND_PATH}")

# ---------------------------------------------------------------- previews (not saved)
if PREVIEW_DIR:
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.display.shading.color_type = 'MATERIAL'
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.show_shadows = True
    scene.render.resolution_x, scene.render.resolution_y = 700, 900
    rig.hide_render = True

    def shot(name):
        scene.render.filepath = os.path.join(PREVIEW_DIR, name)
        bpy.ops.render.render(write_still=True)

    scene.frame_set(1); shot("rest.png")
    scene.frame_set(20); shot("wave.png")
    rig.animation_data.action = None
    for pb in rig.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
    pose = {"thigh.L": ((1, 0, 0), -45), "shin.L": ((1, 0, 0), 70),
            "upper_arm.L": ((0, 1, 0), -80), "forearm.L": ((0, 1, 0), -40),
            "upper_arm.R": ((1, 0, 0), -50), "head": ((0, 0, 1), 30)}
    for bone, (axis, deg) in pose.items():
        rig.pose.bones[bone].rotation_quaternion = q_world(bone, axis, deg)
    cam.location = (-2.4, -3.0, 1.25)
    cam.rotation_euler = (Vector((0, 0, 0.73)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    shot("pose.png")
