"""Run with blender -b --python-exit-code 1 -P tests/validate_santa02.py."""
import json
import struct
from pathlib import Path

import bpy
from mathutils import Vector
from pxr import Usd, UsdGeom, UsdShade, UsdSkel

root = Path(__file__).resolve().parents[1]
bpy.ops.wm.open_mainfile(filepath=str(root / 'santa02.blend'))
scene = bpy.context.scene
rig = bpy.data.objects['Santa02_Rig']
santa = bpy.data.objects['Santa02']
action = 'Santa02_Grocery_Lift'
assert rig.animation_data.action.name == action
assert all(name not in rig.data.bones for name in ('cup', 'kettle', 'liquid', 'aroma', 'stream'))
assert all(im.packed_file for im in bpy.data.images if im.source == 'FILE')
assert all(v.groups and abs(sum(g.weight for g in v.groups) - 1) < .0001 for v in santa.data.vertices)

# Sample actual skin deformation at each end and the peak as well as the
# skeleton throughout, so an unbound grocery mesh or moving tote fails here.
samples = {}
for group in ('groceries', 'root'):
    index = santa.vertex_groups[group].index
    samples[group] = next(v.index for v in santa.data.vertices if any(
        g.group == index and g.weight > .999 for g in v.groups))
rest_points = {}
initial_pose = {}
assert (scene.frame_start, scene.frame_end, scene.render.fps) == (1, 121, 24)
for frame in range(1, 122):
    scene.frame_set(frame)
    load = rig.pose.bones['groceries']
    lift = load.head - rig.data.bones['groceries'].head_local
    for side, sign in [('L', 1), ('R', -1)]:
        upper, fore, hand = [rig.pose.bones[n + '.' + side] for n in ('upper_arm', 'forearm', 'hand')]
        assert (upper.tail - fore.head).length < .0001
        assert (fore.tail - hand.head).length < .0001
        assert (hand.head - Vector((sign * .322, -.415, 1.125)) - lift).length < .0001
    if frame == 1:
        initial_pose = {bone.name: bone.matrix.copy() for bone in rig.pose.bones}
    if frame == 61:
        assert lift.z > .08
    if frame == 121:
        for bone in rig.pose.bones:
            difference = bone.matrix - initial_pose[bone.name]
            assert max(abs(value) for row in difference for value in row) < .0001
    if frame in (1, 61, 121):
        mesh = santa.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
        for group, i in samples.items():
            point = mesh.vertices[i].co
            if frame == 1:
                rest_points[group] = point.copy()
            expected = rest_points[group] + lift if group == 'groceries' else rest_points[group]
            assert (point - expected).length < .0001

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
page = (docs / 'santa02.html').read_text(encoding='utf-8')
assert action in page
for asset in ('santa02.glb', 'santa02.usdz', 'santa02-poster.webp'):
    assert asset in page and (docs / asset).stat().st_size > 0
print('PASS: Santa02 grip, lift, stationary tote, loop closure, skinning, textures, exports and page assets')
