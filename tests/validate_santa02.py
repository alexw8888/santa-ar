"""Run with blender -b --python-exit-code 1 -P tests/validate_santa02.py."""
import json
import struct
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from pxr import Usd, UsdGeom, UsdShade, UsdSkel

sys.path.insert(0, str(Path(__file__).resolve().parent))
from edition_checks import check_beard_clearance  # noqa: E402

root = Path(__file__).resolve().parents[1]
bpy.ops.wm.open_mainfile(filepath=str(root / 'santa02.blend'))
scene = bpy.context.scene
rig = bpy.data.objects['Santa02_Rig']
santa = bpy.data.objects['Santa02']
action = 'Santa02_Grocery_Lift'
frames, lift_frame = 241, 89
assert rig.animation_data.action.name == action
assert all(name not in rig.data.bones for name in ('cup', 'kettle', 'liquid', 'aroma', 'stream'))
assert all(im.packed_file for im in bpy.data.images if im.source == 'FILE')
assert all(v.groups and abs(sum(g.weight for g in v.groups) - 1) < .0001 for v in santa.data.vertices)

# Sample actual skin deformation at each end and the peak as well as the
# skeleton throughout, so an unbound grocery mesh or moving tote fails here.
samples = {}
for group in ('groceries', 'bread_idle', 'greens_idle'):
    index = santa.vertex_groups[group].index
    samples[group] = next(v.index for v in santa.data.vertices if any(
        g.group == index and g.weight > .999 for g in v.groups))
tote_material = santa.data.materials.find('Aisle24 printed canvas')
assert tote_material >= 0, 'The tote must have its printed canvas'
tote_face = next(face for face in santa.data.polygons if face.material_index == tote_material)
samples['root'] = tote_face.vertices[0]
initial_pose = {}
load_relative = {}
swayed = set()
assert (scene.frame_start, scene.frame_end, scene.render.fps) == (1, frames, 24)
shopping = ('groceries', 'bread_idle', 'greens_idle')
check_beard_clearance(scene, santa, cover=shopping)

# The shopping is held in front of the beard, as in the photo: no draped beard vertex may sit in
# front of any of it, on any frame.
mesh = santa.data
shopping_groups = {santa.vertex_groups[name].index for name in shopping}
shopping_vertices = {v.index for v in mesh.vertices
                     if sum(g.weight for g in v.groups if g.group in shopping_groups) > .5}
shopping_faces = [f.vertices for f in mesh.polygons if all(i in shopping_vertices for i in f.vertices)]
shopping_used = sorted({i for face in shopping_faces for i in face})
shopping_index = {i: k for k, i in enumerate(shopping_used)}
shopping_faces = [[shopping_index[i] for i in face] for face in shopping_faces]
drape = santa.vertex_groups['beard_drape'].index
beard_slot = mesh.materials.find('Silver_beard')
draped = sorted({i for face in mesh.polygons if face.material_index == beard_slot for i in face.vertices
                 if any(g.group == drape and g.weight > 0 for g in mesh.vertices[i].groups)})
assert draped, 'Expected a draped lower beard'
for frame in range(1, frames + 1):
    scene.frame_set(frame)
    posed = santa.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.vertices
    held = BVHTree.FromPolygons([posed[i].co for i in shopping_used], shopping_faces)
    for i in draped:
        x, y, z = posed[i].co
        hit = held.ray_cast((x, -2, z), (0, 1, 0))[0]
        assert hit is None or hit.y < y, (frame, i, 'beard shows in front of the shopping')
print('PASS: Santa02 beard stays behind the shopping throughout the loop', flush=True)

for frame in range(1, frames + 1):
    scene.frame_set(frame)
    load = rig.pose.bones['groceries']
    load_deform = load.matrix @ load.bone.matrix_local.inverted()
    for side, sign in [('L', 1), ('R', -1)]:
        upper, fore, hand = [rig.pose.bones[n + '.' + side] for n in ('upper_arm', 'forearm', 'hand')]
        assert (upper.tail - fore.head).length < .0001
        assert (fore.tail - hand.head).length < .0001
        assert (hand.head - load_deform @ Vector((sign * .322, -.415, 1.125))).length < .0001
        hand_deform = hand.matrix @ hand.bone.matrix_local.inverted()
        rotation_difference = hand_deform.to_3x3() - load_deform.to_3x3()
        assert max(abs(value) for row in rotation_difference for value in row) < .0001, (
            frame, side, 'glove must roll with the groceries')
    if frame == 1:
        initial_pose = {bone.name: bone.matrix.copy() for bone in rig.pose.bones}
    for name in ('bread_idle', 'greens_idle'):
        relative = load.matrix.inverted() @ rig.pose.bones[name].matrix
        if frame == 1:
            load_relative[name] = relative
        if max(abs(value) for row in relative - load_relative[name] for value in row) > .001:
            swayed.add(name)
    if frame == lift_frame:
        assert load.head.z - initial_pose['groceries'].translation.z > .04
    if frame == frames:
        for bone in rig.pose.bones:
            difference = bone.matrix - initial_pose[bone.name]
            assert max(abs(value) for row in difference for value in row) < .0001
    if frame in (1, lift_frame, frames):
        mesh = santa.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
        for group, i in samples.items():
            rest = santa.data.vertices[i].co
            bone = rig.pose.bones[group]
            expected = rest if group == 'root' else bone.matrix @ bone.bone.matrix_local.inverted() @ rest
            assert (mesh.vertices[i].co - expected).length < .0001, (frame, group)
assert swayed == {'bread_idle', 'greens_idle'}, 'Bread and greens must sway independently of the bundle'

docs = root / 'docs'
raw = (docs / 'santa02.glb').read_bytes()
assert struct.unpack_from('<4sII', raw) == (b'glTF', 2, len(raw))
length, kind = struct.unpack_from('<I4s', raw, 12)
assert kind == b'JSON'
gltf = json.loads(raw[20:20+length])
assert [a['name'] for a in gltf['animations']] == [action]
assert gltf['skins'] and gltf['images'] and all('bufferView' in image for image in gltf['images'])
assert all('WEIGHTS_0' in p['attributes'] and 'JOINTS_0' in p['attributes']
           for m in gltf['meshes'] for p in m['primitives'])
stage = Usd.Stage.Open(str(docs / 'santa02.usdz'))
assert any(p.IsA(UsdGeom.Mesh) for p in stage.Traverse())
assert any(p.IsA(UsdSkel.Skeleton) for p in stage.Traverse())
assert any(p.IsA(UsdSkel.Animation) and
           UsdSkel.Animation(p).GetTranslationsAttr().GetNumTimeSamples() > 1 for p in stage.Traverse())
assert any(s.GetIdAttr().Get() == 'UsdPreviewSurface' and s.GetInput('opacity') and
           0 < s.GetInput('opacity').Get() < .2
           for p in stage.Traverse() if p.IsA(UsdShade.Shader) for s in [UsdShade.Shader(p)])
page = (docs / 'Santa_Aisle24.html').read_text(encoding='utf-8')
assert action in page
for asset in ('santa02.glb', 'santa02-android.glb', 'santa02.usdz', 'santa02-poster.webp'):
    assert asset in page and (docs / asset).stat().st_size > 0
assert b'extensions' not in (docs / 'santa02-android.glb').read_bytes()[:200000],     'Android GLB still uses glTF extensions'
print('PASS: Santa02 grip, lift, stationary tote, loop closure, skinning, textures, exports and page assets')
