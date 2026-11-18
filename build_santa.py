"""
Procedural, rigged Santa Claus for Blender (tested on Blender 5.3).

Run headless:
    blender.exe -b --factory-startup -P build_santa.py -- [preview_dir]

Produces santa_rigged.blend next to this script:
  * "Santa"      - one mesh, multiple materials, vertex groups per bone,
                   Armature + Subdivision modifiers
  * "Santa_Rig"  - armature (root, hips, spine, chest, neck, head, hat,
                   shoulder/upper_arm/forearm/hand .L/.R, thigh/shin/foot .L/.R)
  * "Santa_Wave" - a small waving animation (frames 1-60)
  * camera + sun light
If preview_dir is given, a few Workbench renders are written there.
"""
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix, Quaternion, Euler

HERE = os.path.dirname(os.path.abspath(__file__))
ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
PREVIEW_DIR = ARGV[0] if ARGV else None
BLEND_PATH = os.path.join(HERE, "santa_rigged.blend")

# ---------------------------------------------------------------- clean scene
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.armatures,
             bpy.data.cameras, bpy.data.lights, bpy.data.actions):
    for block in list(coll):
        coll.remove(block)
scene = bpy.context.scene

# ---------------------------------------------------------------- skeleton
# name, head, tail, parent, deform, connected   (left side = +X, Santa faces -Y)
CENTER_BONES = [
    ("root",  (0, 0, 0),        (0, 0.3, 0),      None,    False, False),
    ("hips",  (0, 0, 0.97),     (0, 0, 1.10),     "root",  True,  False),
    ("spine", (0, 0, 1.10),     (0, 0, 1.33),     "hips",  True,  True),
    ("chest", (0, 0, 1.33),     (0, 0, 1.55),     "spine", True,  True),
    ("neck",  (0, 0, 1.55),     (0, 0, 1.63),     "chest", True,  True),
    ("head",  (0, 0, 1.63),     (0, 0, 1.86),     "neck",  True,  True),
    ("hat",   (0, 0.02, 1.93),  (0, 0.22, 2.02),  "head",  True,  False),
]
LEFT_BONES = [
    ("shoulder",  (0.04, 0, 1.50),     (0.19, 0, 1.50),      "chest",     False),
    ("upper_arm", (0.19, 0, 1.50),     (0.45, 0, 1.28),      "shoulder",  True),
    ("forearm",   (0.45, 0, 1.28),     (0.62, -0.04, 1.08),  "upper_arm", True),
    ("hand",      (0.62, -0.04, 1.08), (0.67, -0.05, 0.97),  "forearm",   True),
    ("thigh",     (0.12, 0, 0.97),     (0.13, 0, 0.52),      "hips",      False),
    ("shin",      (0.13, 0, 0.52),     (0.13, 0.02, 0.12),   "thigh",     True),
    ("foot",      (0.13, 0.02, 0.12),  (0.13, -0.14, 0.04),  "shin",      True),
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
    "Coat_Red":  dict(color=(0.55, 0.01, 0.015), rough=0.65),
    "Fur_White": dict(color=(0.92, 0.92, 0.90), rough=1.0),
    "Skin":      dict(color=(0.90, 0.60, 0.48), rough=0.5),
    "Rosy":      dict(color=(0.85, 0.32, 0.30), rough=0.5),
    "Black":     dict(color=(0.015, 0.015, 0.015), rough=0.35),
    "Gold":      dict(color=(0.95, 0.70, 0.15), rough=0.25, metal=1.0),
    "Eye":       dict(color=(0.005, 0.005, 0.01), rough=0.1),
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
CREASE = bm.edges.layers.float.new("crease_edge")


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


def box(center, size, mat, cands):
    M = Matrix.Translation(center) @ Matrix.Diagonal((*size, 1.0))
    res = bmesh.ops.create_cube(bm, size=1.0, matrix=M)
    edges = {e for v in res["verts"] for e in v.link_edges}
    for e in edges:
        e[CREASE] = 1.0
    finish(res["verts"], mat, cands, smooth=False)


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
TORSO = ["hips", "spine", "chest"]
BELLY_C, BELLY_R = Vector((0, -0.03, 1.20)), Vector((0.33, 0.30, 0.36))
CHEST_C, CHEST_R = Vector((0, 0.01, 1.42)), Vector((0.28, 0.22, 0.18))

ellipsoid(BELLY_C, BELLY_R, "Coat_Red", TORSO, segs=32, rings=20)
ellipsoid(CHEST_C, CHEST_R, "Coat_Red", ["spine", "chest"], segs=28, rings=16)

# coat skirt + fur hem
SKIRT = ["hips", "thigh.L", "thigh.R"]
tube([(0, -0.02, 1.03), (0, -0.02, 0.86)], [0.30, 0.32], "Coat_Red", SKIRT, segs=32)
torus((0, -0.02, 0.86), (0, 0, 1), 0.32, 0.04, "Fur_White", SKIRT)

# belt + buckle
torus((0, -0.03, 1.06), (0, 0, 1), 0.305, 0.04, "Black", ["hips", "spine"], major_b=0.28)
box((0, -0.355, 1.06), (0.12, 0.03, 0.09), "Gold", ["hips", "spine"])
box((0, -0.37, 1.06), (0.07, 0.01, 0.05), "Black", ["hips", "spine"])


def front_y(z):
    ys = []
    for c, r in ((BELLY_C, BELLY_R), (CHEST_C, CHEST_R)):
        k = (z - c.z) / r.z
        if abs(k) < 1:
            ys.append(c.y - r.y * math.sqrt(1 - k * k))
    if 0.86 <= z <= 1.03:
        ys.append(-0.02 - (0.30 + (1.03 - z) / 0.17 * 0.02))
    return min(ys)


strip = [(0, front_y(z) + 0.005, z) for z in [1.56 - i * 0.05 for i in range(14)]]
tube(strip, [0.03] * len(strip), "Fur_White", TORSO, subdiv=2, segs=12)

# collar
torus((0, 0, 1.59), (0, 0, 1), 0.13, 0.045, "Fur_White", ["chest", "neck"])

# ---------------------------------------------------------------- head
HEAD = ["head"]
ellipsoid((0, 0, 1.74), (0.13, 0.13, 0.13), "Skin", HEAD)
ellipsoid((0, 0.03, 1.72), (0.14, 0.12, 0.12), "Fur_White", HEAD)          # hair
ellipsoid((0, -0.135, 1.745), (0.032, 0.03, 0.03), "Rosy", HEAD, segs=16, rings=10)
ellipsoid((0, -0.06, 1.62), (0.15, 0.10, 0.17), "Fur_White", HEAD)         # beard
ellipsoid((0, -0.10, 1.48), (0.10, 0.07, 0.10), "Fur_White", HEAD)         # beard tip
for s in (1, -1):
    ellipsoid((0.045 * s, -0.117, 1.78), (0.016, 0.012, 0.018), "Eye", HEAD, segs=12, rings=8)
    ellipsoid((0.05 * s, -0.117, 1.815), (0.035, 0.015, 0.012), "Fur_White", HEAD,
              euler=(0, -10 * s, 0), segs=12, rings=8)                    # eyebrow
    ellipsoid((0.075 * s, -0.10, 1.725), (0.032, 0.025, 0.028), "Rosy", HEAD,
              segs=12, rings=8)                                            # cheek
    ellipsoid((0.05 * s, -0.128, 1.705), (0.065, 0.03, 0.028), "Fur_White", HEAD,
              euler=(0, 15 * s, 0), segs=16, rings=10)                     # moustache

# hat


def hat_w(p):
    w = max(0.0, min(1.0, (p.z - 1.88) / 0.10))
    return {"head": 1 - w, "hat": w} if 0 < w < 1 else ({"hat": 1.0} if w >= 1 else {"head": 1.0})


tube([(0, 0, 1.80), (0, 0.02, 1.93), (0, 0.10, 2.04), (0, 0.22, 2.02)],
     [0.14, 0.11, 0.06, 0.015], "Coat_Red", wfn=hat_w, subdiv=5, segs=20)
torus((0, 0, 1.80), (0, 0, 1), 0.135, 0.038, "Fur_White", HEAD)
ellipsoid((0, 0.24, 2.01), (0.045, 0.045, 0.045), "Fur_White", ["hat"], segs=16, rings=10)

# ---------------------------------------------------------------- limbs
for side, s in (("L", 1), ("R", -1)):
    X = lambda p: (p[0] * s, p[1], p[2])
    b = lambda n: f"{n}.{side}"
    # arm
    ellipsoid(X((0.19, 0, 1.49)), (0.10, 0.10, 0.10), "Coat_Red",
              [b("upper_arm"), "chest"])
    tube([X((0.17, 0, 1.50)), X((0.45, 0, 1.28)), X((0.60, -0.035, 1.10))],
         [0.085, 0.075, 0.07], "Coat_Red", [b("upper_arm"), b("forearm")], subdiv=5)
    fore_dir = X((0.17, -0.04, -0.20))
    torus(X((0.60, -0.035, 1.10)), fore_dir, 0.075, 0.03, "Fur_White", [b("forearm")])
    ellipsoid(X((0.655, -0.048, 1.02)), (0.055, 0.045, 0.075), "Black", [b("hand")],
              direction=X((0.05, -0.01, -0.11)), segs=16, rings=10)
    ellipsoid(X((0.625, -0.09, 1.05)), (0.022, 0.022, 0.038), "Black", [b("hand")],
              direction=X((-0.2, -0.5, -1)), segs=12, rings=8)             # thumb
    # leg
    tube([X((0.12, 0, 0.98)), X((0.13, 0, 0.52)), X((0.13, 0.02, 0.20))],
         [0.11, 0.09, 0.08], "Coat_Red", ["hips", b("thigh"), b("shin")], subdiv=5)
    tube([X((0.13, 0.02, 0.36)), X((0.13, 0.02, 0.08))], [0.09, 0.09], "Black",
         [b("shin"), b("foot")], subdiv=4)
    torus(X((0.13, 0.02, 0.36)), (0, 0, 1), 0.095, 0.03, "Fur_White", [b("shin")])
    ellipsoid(X((0.13, -0.05, 0.065)), (0.09, 0.16, 0.065), "Black",
              [b("shin"), b("foot")], segs=20, rings=12)

bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

# ---------------------------------------------------------------- objects
me = bpy.data.meshes.new("Santa_Mesh")
bm.to_mesh(me)
bm.free()
for n in MAT_NAMES:
    me.materials.append(bpy.data.materials[n])
santa = bpy.data.objects.new("Santa", me)
scene.collection.objects.link(santa)
for n in DEFORM:
    santa.vertex_groups.new(name=n)

arm_data = bpy.data.armatures.new("Santa_Rig")
rig = bpy.data.objects.new("Santa_Rig", arm_data)
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

santa.parent = rig
mod = santa.modifiers.new("Armature", 'ARMATURE')
mod.object = rig
sub = santa.modifiers.new("Subdivision", 'SUBSURF')
sub.levels, sub.render_levels = 1, 2

for pb in rig.pose.bones:
    pb.rotation_mode = 'QUATERNION'

# sanity: every vertex weighted
unweighted = sum(1 for v in me.vertices if not v.groups)
print(f"[santa] verts={len(me.vertices)} faces={len(me.polygons)} unweighted={unweighted}")


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
act.name = "Santa_Wave"
act.use_fake_user = True
scene.frame_start, scene.frame_end = 1, 60
scene.frame_set(1)

# ---------------------------------------------------------------- camera / light / world
cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
scene.collection.objects.link(cam)
cam.location = (2.2, -4.6, 1.6)
cam.rotation_euler = (Vector((0, 0, 1.05)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
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
bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
print(f"[santa] saved {BLEND_PATH}")

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
            "upper_arm.R": ((1, 0, 0), -50), "head": ((0, 0, 1), 30),
            "hat": ((1, 0, 0), 35)}
    for bone, (axis, deg) in pose.items():
        rig.pose.bones[bone].rotation_quaternion = q_world(bone, axis, deg)
    cam.location = (-3.6, -3.6, 1.5)
    cam.rotation_euler = (Vector((0, 0, 1.0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    shot("pose.png")
