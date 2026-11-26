"""Shared building blocks for the Santa editions made from the base character.

A build_santaNN.py script calls `start` (opens santa_base.blend, renames Santa to SantaNN and adds
the edition's prop bones), models its props with the geometry helpers below, joins them with
`attach`, bakes its loop with `bake` (which adds the shared secondary sway from santa_motion.py)
and finally calls `finish` to save the .blend, previews and poster.

Props are modelled in world space at their rest placement. Each vertex is bound rigidly to the
bone that is active in `bound(...)`, so posing a prop bone with `rigid` moves the prop as one piece.
"""
import math
import random
import sys
from contextlib import contextmanager
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import santa_motion  # noqa: E402

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
EYES = Vector((0, -.13, 1.79))
EYE_LIMIT = math.radians(19)
MAX_DOWNWARD_NOD = math.radians(13)
# The cupped left glove wraps a vertical cylinder (about 5 cm radius) whose axis sits at this offset
# from the wrist; the right glove is its mirror image. Rotating a hand turns the offset with it.
GRIP = {'L': Vector((-.16, -.04, 0)), 'R': Vector((.16, -.04, 0))}
TAU = math.tau

scene = rig = santa = None
NAME = ''


# ----------------------------------------------------------------------------- character
def start(number, scene_name, photo, prop_bones):
    """Open the base character, rename it SantaNN and add (name, head, tail, parent) bones.

    The base has two cupped gloves (the right one mirrors the left), so both hands can wrap a prop
    from opposite sides, and the secondary-motion bones that `bake` animates."""
    global scene, rig, santa, NAME
    NAME = f'Santa{number:02d}'
    bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'santa_base.blend'))
    scene = bpy.context.scene
    scene.name = scene_name
    scene['Reference'] = photo
    rig = bpy.data.objects['Santa_Rig']
    santa = bpy.data.objects['Santa']
    rig.name = rig.data.name = NAME + '_Rig'
    santa.name, santa.data.name = NAME, NAME + '_Mesh'
    for bone in rig.pose.bones:
        bone.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    for name, head, tail, parent in prop_bones:
        bone = rig.data.edit_bones.new(name)
        bone.head, bone.tail = head, tail
        bone.parent = rig.data.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    for bone in rig.pose.bones:
        bone.rotation_mode = 'QUATERNION'
    return scene, rig, santa


# ----------------------------------------------------------------------------- materials
def linear(hex_color):
    rgb = [int(hex_color[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in rgb]


def to_srgb(values):
    values = np.clip(values, 0, 1)
    return np.where(values <= .0031308, values * 12.92, 1.055 * values ** (1 / 2.4) - .055)


def from_srgb(values):
    return np.where(values <= .04045, values / 12.92, ((values + .055) / 1.055) ** 2.4)


TILE = {}  # material -> texture repeat in metres (box-projected UVs)


def material(name, hex_color, rough=.5, metal=0, emit=0, alpha=1, sheen=0, coat=0):
    color = linear(hex_color)
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, alpha)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Metallic'].default_value = metal
    if emit:
        bsdf.inputs['Emission Color'].default_value = (*color, 1)
        bsdf.inputs['Emission Strength'].default_value = emit
    if alpha < 1:
        # export_santa.py finds translucent materials by their USD prim name, which can't hold spaces.
        assert name.replace('_', '').isalnum(), 'name translucent materials with letters and underscores'
        bsdf.inputs['Alpha'].default_value = alpha
        mat.surface_render_method = 'DITHERED'
        mat.use_transparency_overlap = False
    if sheen:
        bsdf.inputs['Sheen Weight'].default_value = sheen
        bsdf.inputs['Sheen Roughness'].default_value = .7
    if coat:
        bsdf.inputs['Coat Weight'].default_value = coat
        bsdf.inputs['Coat Roughness'].default_value = .08
    return mat


def image(name, rgb):
    """Pack an sRGB float array (h, w, 3) as an image."""
    h, w = rgb.shape[:2]
    pixels = np.ones((h, w, 4), dtype=np.float32)
    pixels[:, :, :3] = rgb
    im = bpy.data.images.new(name, width=w, height=h, alpha=False)
    im.pixels.foreach_set(pixels.ravel())
    im.pack()
    return im


def textured(mat, rgb, tile):
    """Drive a material's base colour from a generated, tileable sRGB swatch."""
    node = mat.node_tree.nodes.new('ShaderNodeTexImage')
    node.image = image(mat.name + ' swatch', rgb)
    mat.node_tree.links.new(node.outputs['Color'], mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'])
    TILE[mat] = tile
    return mat


def recolor(source, name, hex_color, tile):
    """Copy one of Santa's textured materials (velvet, plush fur) in a new colour, keeping its pile."""
    mat = bpy.data.materials[source].copy()
    mat.name = name
    target = np.array(linear(hex_color))
    bsdf = mat.node_tree.nodes['Principled BSDF']
    node = bsdf.inputs['Base Color'].links[0].from_node
    old = node.image
    w, h = old.size
    px = np.empty(w * h * 4, dtype=np.float32)
    old.pixels.foreach_get(px)
    rgb = from_srgb(px.reshape(h, w, 4)[:, :, :3])
    base = rgb.reshape(-1, 3).mean(axis=0)
    shade = (rgb @ base) / (base @ base)
    node.image = image(name + ' color', to_srgb(target[None, None, :] * shade[:, :, None]))
    mat.diffuse_color = (*target, 1)
    bsdf.inputs['Sheen Tint'].default_value = (*(target / max(target)), 1)
    TILE[mat] = tile
    return mat


# ----------------------------------------------------------------------------- prop geometry
verts, faces, slots, smooth, solid, materials, bones, uvs = [], [], [], [], [], [], [], []
pose = Matrix.Identity(4)
binding = 'root'


@contextmanager
def place(x=0, y=0, z=0, tilt=0, yaw=0, scale=1, roll=0):
    """Nest a local frame: translate, then yaw (Z), roll (X) and tilt (Y) in degrees, then scale."""
    global pose
    previous = pose
    pose = (pose @ Matrix.Translation((x, y, z)) @ Matrix.Rotation(math.radians(yaw), 4, 'Z')
            @ Matrix.Rotation(math.radians(roll), 4, 'X') @ Matrix.Rotation(math.radians(tilt), 4, 'Y')
            @ (Matrix.Diagonal((*scale, 1)) if isinstance(scale, tuple) else Matrix.Scale(scale, 4)))
    try:
        yield
    finally:
        pose = previous


@contextmanager
def frame(matrix):
    global pose
    previous = pose
    pose = pose @ matrix
    try:
        yield
    finally:
        pose = previous


@contextmanager
def bound(bone):
    global binding
    previous = binding
    binding = bone
    try:
        yield
    finally:
        binding = previous


def surface(points, polygons, mat, rounded=False, closed=False, two_sided=False, uv=None):
    """uv: optional (u, v) per point; otherwise textured materials get box-projected UVs."""
    for back in ((False, True) if two_sided else (False,)):
        offset = len(verts)
        verts.extend(pose @ Vector(p) for p in points)
        bones.extend([binding] * len(points))
        uvs.extend(uv or [None] * len(points))
        if mat not in materials:
            materials.append(mat)
        slots.extend([materials.index(mat)] * len(polygons))
        smooth.extend([rounded] * len(polygons))
        solid.extend([closed] * len(polygons))
        faces.extend(tuple(offset + i for i in (reversed(poly) if back else poly)) for poly in polygons)


def rings(rows, mat, rounded=True, close=True, two_sided=False):
    n = len(rows[0])
    polys = [(j * n + i, j * n + (i + 1) % n, (j + 1) * n + (i + 1) % n, (j + 1) * n + i)
             for j in range(len(rows) - 1) for i in range(n)]
    if close:
        polys.extend([tuple(reversed(range(n))), tuple(range((len(rows) - 1) * n, len(rows) * n))])
    surface([p for row in rows for p in row], polys, mat, rounded, close, two_sided and not close)


def profile(levels, mat, power=1, n=32, rounded=True, close=True, wobble=None, two_sided=False):
    """Lathe (z, half-width, half-depth) levels; `wobble(angle, z)` scales the radius."""
    rows = []
    for z, w, d in levels:
        row = []
        for i in range(n):
            a = TAU * i / n
            c, s = math.cos(a), math.sin(a)
            k = wobble(a, z) if wobble else 1
            row.append((k * w * math.copysign(abs(c) ** power, c), k * d * math.copysign(abs(s) ** power, s), z))
        rows.append(row)
    rings(rows, mat, rounded, close, two_sided)


def ellipsoid(x, y, z, rx, ry, rz, mat, n=16, m=8, wobble=None):
    with place(x, y, z):
        profile([(rz * math.sin(a), rx * max(.01, math.cos(a)), ry * max(.01, math.cos(a)))
                 for a in [math.pi * (j / m - .5) for j in range(m + 1)]], mat, n=n, wobble=wobble)


def ball(x, y, z, r, mat, n=12, m=6):
    ellipsoid(x, y, z, r, r, r, mat, n, m)


def cord(points, radius, mat, scales=None, sides=8):
    path = [Vector(p) for p in points]
    rows = []
    u = None
    for i, p in enumerate(path):
        axis = (path[min(i + 1, len(path) - 1)] - path[max(0, i - 1)]).normalized()
        if u is None:
            u = axis.cross(Vector((0, 1, 0)) if abs(axis.y) < .95 else Vector((1, 0, 0))).normalized()
        else:
            # Parallel transport: carry the ring's orientation along the path so it never twists.
            u = (u - axis * u.dot(axis)).normalized()
        v = axis.cross(u)
        r = radius * (scales[i] if scales else 1)
        rows.append([p + r * (u * math.cos(j * TAU / sides) + v * math.sin(j * TAU / sides)) for j in range(sides)])
    rings(rows, mat)


def sheet(rows, mat, rounded=True):
    """A two-sided open grid (petals, leaves, ribbons) from rows of points."""
    n = len(rows[0])
    polys = [(j * n + i, j * n + i + 1, (j + 1) * n + i + 1, (j + 1) * n + i)
             for j in range(len(rows) - 1) for i in range(n - 1)]
    surface([p for row in rows for p in row], polys, mat, rounded, two_sided=True)


def leaf(length, width, mat, fold=.25, curl=.15, segments=8):
    """A lanceolate leaf along +Z, folded along its midrib and curling toward -Y."""
    rows = []
    for j in range(segments + 1):
        t = j / segments
        w = width * math.sin(math.pi * min(1, t * 1.08)) ** .7
        z = length * t
        back = -curl * length * t * t
        rows.append([(s * w, back + fold * w * abs(s), z) for s in (-1, -.5, 0, .5, 1)])
    sheet(rows, mat)


def text_mesh(text, bold=0.0):
    font = bpy.data.curves.new('Lettering', 'FONT')
    font.resolution_u = 5
    font.body, font.align_x, font.align_y = text, 'CENTER', 'CENTER'
    font.offset = bold
    ob = bpy.data.objects.new('Typeset', font)
    scene.collection.objects.link(ob)
    bpy.context.view_layer.update()
    evaluated = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    data = evaluated.to_mesh()
    points = [v.co.copy() for v in data.vertices]
    polys = [tuple(p.vertices) for p in data.polygons]
    evaluated.to_mesh_clear()
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.curves.remove(font)
    return points, polys


def flat(x, y, z):
    """Lettering on the plane y = const, facing -Y; `depth` sets it back toward +Y."""
    return lambda u, v, depth=0: (x + u, y + depth, z + v)


def around(radius, z, lift=.0015, x=0, y=0, spin=0):
    """Lettering wrapped around a vertical lathe of radius `radius(z)` (or a number).

    It faces -Y, turned `spin` radians toward +X."""
    def mapper(u, v, depth=0):
        r = (radius(z + v) if callable(radius) else radius) + lift - depth
        a = u / r + spin
        return (x + r * math.sin(a), y - r * math.cos(a), z + v)
    return mapper


def label(text, mat, mapper, width, bold=0.0, outline=None, step=.0012):
    """Typeset `text` `width` wide, centred on the mapper's origin.

    outline=(material, extra boldness) adds a fatter copy just behind the fill; a list of
    (material, extra boldness, dx, dy) tuples stacks several, each further back, offset by dx, dy.
    """
    points, polys = text_mesh(text, bold)
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    k = width / (max(xs) - min(xs))
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    layers = [(points, polys, mat, 0, 0, 0)]
    if isinstance(outline, tuple):
        outline = [(*outline, 0, 0)]
    for i, (m, extra, dx, dy) in enumerate(outline or []):
        layers.insert(0, (*text_mesh(text, bold + extra), m, step * (i + 1), dx, dy))
    for pts, ps, m, depth, dx, dy in layers:
        surface([mapper((p.x - cx) * k + dx, (p.y - cy) * k + dy, depth) for p in pts], ps, m)


def decal(mapper, width, height, mat, columns=24, rows=6):
    """A printed image (the material's texture, UV 0..1) `width` x `height`, centred on the mapper's origin."""
    points, uv = [], []
    for j in range(rows + 1):
        for i in range(columns + 1):
            u, v = i / columns, j / rows
            points.append(mapper((u - .5) * width, (v - .5) * height))
            uv.append((u, v))
    polys = [(j * (columns + 1) + i, j * (columns + 1) + i + 1, (j + 1) * (columns + 1) + i + 1,
              (j + 1) * (columns + 1) + i) for j in range(rows) for i in range(columns)]
    surface(points, polys, mat, rounded=True, uv=uv)


def printed(base, name, path, ink, crop=None, width=1024):
    """Copy material `base` with an image printed on it: the image's pale background becomes the
    material's own colour and its darkest marks become `ink` (hex), so the patch edge never shows."""
    source = bpy.data.images.load(str(ROOT / path))
    w, h = source.size
    px = np.empty(w * h * 4, dtype=np.float32)
    source.pixels.foreach_get(px)
    rgb = px.reshape(h, w, 4)[:, :, :3]
    if crop:  # (left, bottom, right, top) in pixels, image rows counted from the bottom
        rgb = rgb[crop[1]:crop[3], crop[0]:crop[2]]
    luma = rgb @ np.array([.2126, .7152, .0722])
    paper, dark = np.percentile(luma, 90), np.percentile(luma, .5)
    amount = np.clip((paper - luma) / (paper - dark), 0, 1)[:, :, None]
    bsdf = base.node_tree.nodes['Principled BSDF']
    glaze = to_srgb(np.array(bsdf.inputs['Base Color'].default_value[:3]))
    out = glaze * (1 - amount) + to_srgb(np.array(linear(ink))) * amount
    height = round(width * out.shape[0] / out.shape[1])
    ys = np.linspace(0, out.shape[0] - 1, height).round().astype(int)
    xs = np.linspace(0, out.shape[1] - 1, width).round().astype(int)
    bpy.data.images.remove(source)
    mat = base.copy()
    mat.name = name
    node = mat.node_tree.nodes.new('ShaderNodeTexImage')
    node.image = image(name + ' print', out[ys][:, xs])
    mat.node_tree.links.new(node.outputs['Color'], mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'])
    return mat


def steam(x, y, z, count, height, radius, mat, seed):
    """Soft, curling wisps rising from (x, y, z)."""
    rnd = random.Random(seed)
    for i in range(count):
        a = TAU * i / count + rnd.uniform(-.4, .4)
        r0 = radius * rnd.uniform(.2, .6)
        phase = rnd.uniform(0, TAU)
        h = height * rnd.uniform(.75, 1.1)
        curl = radius * rnd.uniform(1.6, 2.4)
        path = [(x + r0 * math.cos(a) + curl * math.sin(phase + 5 * t) * t,
                 y + r0 * math.sin(a) + curl * .7 * math.cos(phase + 4 * t) * t,
                 z + h * t) for t in [k / 9 for k in range(10)]]
        cord(path, radius * rnd.uniform(.30, .42), mat, [.3, .7, .95, 1, 1, .95, .85, .65, .4, .12], sides=8)


def attach(name):
    """Join the modelled props to the character mesh, bound rigidly to their bones."""
    data = bpy.data.meshes.new(name)
    data.from_pydata(verts, [], faces)
    data.update()
    ob = bpy.data.objects.new(name, data)
    scene.collection.objects.link(ob)
    for mat in materials:
        data.materials.append(mat)
    for poly, slot, rounded in zip(data.polygons, slots, smooth):
        poly.material_index, poly.use_smooth = slot, rounded
    # Closed shells must face outward: AR Quick Look culls back faces even on double-sided meshes.
    mesh = bmesh.new()
    mesh.from_mesh(data)
    mesh.faces.ensure_lookup_table()
    bmesh.ops.recalc_face_normals(mesh, faces=[mesh.faces[i] for i, closed in enumerate(solid) if closed])
    mesh.to_mesh(data)
    mesh.free()
    uv = data.uv_layers.new(name=santa.data.uv_layers.active.name, do_init=False)
    uv.uv.foreach_set('vector', np.zeros(len(data.loops) * 2, dtype=np.float32))
    for poly in data.polygons:
        tile = TILE.get(materials[poly.material_index])
        if uvs[data.loops[poly.loop_start].vertex_index] is not None:
            for loop in poly.loop_indices:
                uv.data[loop].uv = uvs[data.loops[loop].vertex_index]
        elif tile:
            a, b = sorted(sorted(range(3), key=lambda k: abs(poly.normal[k]))[:2])
            for loop in poly.loop_indices:
                co = data.vertices[data.loops[loop].vertex_index].co
                uv.data[loop].uv = (co[a] / tile, co[b] / tile)
    for bone in sorted(set(bones)):
        ob.vertex_groups.new(name=bone).add([i for i, b in enumerate(bones) if b == bone], 1, 'REPLACE')
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    santa.select_set(True)
    bpy.context.view_layer.objects.active = santa
    bpy.ops.object.join()
    print(f'[model] {name}: {len(verts):,} prop vertices; {NAME} now has {len(santa.data.vertices):,}', flush=True)


# ----------------------------------------------------------------------------- posing
def smoothstep(t):
    t = max(0, min(1, t))
    return t * t * (3 - 2 * t)


def ramp(t, a, b):
    return smoothstep((t - a) / (b - a))


def rigid(name, point, rotation=None):
    """Move bone `name` so its rest geometry is rotated about the bone head and placed at `point`."""
    bone = rig.data.bones[name]
    rotation = rotation or Matrix.Identity(3)
    rig.pose.bones[name].matrix = (Matrix.Translation(point) @ rotation.to_4x4()
                                   @ Matrix.Translation(-bone.head_local) @ bone.matrix_local)
    bpy.context.view_layer.update()


def attached(name):
    """Where bone `name`'s head sits on its posed parent (e.g. a shoulder riding the swaying chest)."""
    bone = rig.data.bones[name]
    parent = rig.pose.bones[bone.parent.name]
    return parent.matrix @ bone.parent.matrix_local.inverted() @ bone.head_local


def reach(side, wrist):
    """Two-bone arm from the shoulder (where the posed chest carries it) to `wrist`, elbow out and down."""
    upper, fore = [rig.data.bones[n + '.' + side] for n in ('upper_arm', 'forearm')]
    shoulder = attached(upper.name)
    direction = (wrist - shoulder).normalized()
    full = upper.length + fore.length
    assert (wrist - shoulder).length < full - .005, (side, 'cannot reach', wrist)
    dist = (wrist - shoulder).length
    along = (upper.length ** 2 - fore.length ** 2 + dist ** 2) / (2 * dist)
    guide = Vector((1 if side == 'L' else -1, .08, -.5))
    elbow = (shoulder + along * direction + (guide - direction * guide.dot(direction)).normalized()
             * math.sqrt(max(0, upper.length ** 2 - along ** 2)))
    for bone, a, b in ((upper, shoulder, elbow), (fore, elbow, wrist)):
        rigid(bone.name, a, (bone.tail_local - bone.head_local).rotation_difference(b - a).to_matrix())


def hold(side, grip, rotation=None):
    """Wrap the cupped glove of `side` around the vertical axis through `grip`."""
    rotation = rotation or Matrix.Identity(3)
    wrist = grip - rotation @ GRIP[side]
    reach(side, wrist)
    rigid('hand.' + side, wrist, rotation)
    return wrist


def turn(degrees, axis='Z'):
    return Matrix.Rotation(math.radians(degrees), 3, axis)


def look(target, extra_nod=0, turn_share=.6, nod_share=.35):
    """Turn and nod the head part of the way toward `target`; the eyes do the rest."""
    d = Vector(target) - EYES
    yaw = turn_share * math.atan2(d.x, -d.y)
    # A deep bow puts the portrait's lower face behind the coat collar.
    pitch = min(MAX_DOWNWARD_NOD, nod_share * math.atan2(-d.z, math.hypot(d.x, d.y)) + extra_nod)
    rig.pose.bones['head'].rotation_quaternion = Quaternion((0, 1, 0), yaw) @ Quaternion((1, 0, 0), pitch)
    bpy.context.view_layer.update()


def aim_eyes(target):
    head = rig.pose.bones['head']
    head_deform = head.matrix @ rig.data.bones['head'].matrix_local.inverted()
    local_target = head_deform.inverted() @ Vector(target)
    for side in ('L', 'R'):
        pivot = rig.data.bones['eye.' + side].head_local
        twist = Vector((0, -1, 0)).rotation_difference((local_target - pivot).normalized())
        if twist.angle > EYE_LIMIT:
            twist = Quaternion(twist.axis, EYE_LIMIT)
        deform = Matrix.Translation(pivot) @ twist.to_matrix().to_4x4() @ Matrix.Translation(-pivot)
        rig.pose.bones['eye.' + side].matrix = head_deform @ deform @ rig.data.bones['eye.' + side].matrix_local
    bpy.context.view_layer.update()


def action_fcurves(obj):
    action = obj.animation_data.action
    if hasattr(action, 'fcurves'):
        return action.fcurves
    from bpy_extras.anim_utils import action_get_channelbag_for_slot
    return action_get_channelbag_for_slot(action, obj.animation_data.action_slot).fcurves


def bake(action_name, frames, pose_at, animated, sway=True, activity=None):
    """Key `animated` bones on every frame; `pose_at(t)` receives the loop phase t in [0, 1].

    With `sway`, each frame first gets the shared secondary motion (body sway, coat, sleeves, hat
    tip, feet) at the same phase, scaled up a little by `activity(t)` (0..1) during big gestures;
    `pose_at` then solves the arms from the swaying shoulders, so held props stay put in the gloves.
    """
    scene.frame_start, scene.frame_end = 1, frames
    scene.render.fps = 24
    armature = santa.modifiers.get('Armature')
    armature.show_viewport = False
    if sway:
        animated = list(dict.fromkeys(list(animated) + list(santa_motion.ANIMATED_BONES)))
    for f in range(1, frames + 1):
        scene.frame_set(f)
        for bone in rig.pose.bones:
            bone.matrix_basis = Matrix.Identity(4)
        t = (f - 1) / (frames - 1)
        if sway:
            santa_motion.sway(rig, t, activity(t) if activity else 0)
            bpy.context.view_layer.update()
        pose_at(t)
        for name in animated:
            bone = rig.pose.bones[name]
            for path in ('location', 'rotation_quaternion', 'scale'):
                bone.keyframe_insert(path, frame=f, group=name)
    armature.show_viewport = True
    rig.animation_data.action.name = action_name
    rig.animation_data.action.use_fake_user = True
    for fc in action_fcurves(rig):
        for k in fc.keyframe_points:
            k.interpolation = 'LINEAR'
    scene.frame_set(1)


# ----------------------------------------------------------------------------- output
def camera(location, target, lens, size):
    cam = scene.camera
    cam.location = location
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens
    scene.render.resolution_x, scene.render.resolution_y = size


def finish(version, front, shots):
    """Save versionNN.blend; with a preview folder argument render `shots` and the poster.

    front: camera arguments for the editable scene and the poster.
    shots: (name, frame, camera arguments) tuples; the 'front' shot also writes the poster.
    """
    camera(*front)
    scene.render.resolution_percentage = 100
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 20
    scene.cycles.use_denoising = True
    scene.frame_set(1)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / (version + '.blend')), compress=True)
    print('[model] Saved', version + '.blend', flush=True)
    if not ARGS:
        return
    previews = Path(ARGS[0]).resolve()
    previews.mkdir(exist_ok=True, parents=True)
    only = set(ARGS[1:])
    for name, f, view in shots:
        if only and name not in only:
            continue
        camera(*view)
        scene.frame_set(f)
        scene.render.filepath = str(previews / f'{version}-{name}.png')
        bpy.ops.render.render(write_still=True)
        print('[render]', name, flush=True)
        if name == 'front':
            scene.render.image_settings.file_format = 'WEBP'
            scene.render.image_settings.quality = 88
            bpy.data.images['Render Result'].save_render(str(ROOT / 'docs' / f'{version}-poster.webp'), scene=scene)
            scene.render.image_settings.file_format = 'PNG'
