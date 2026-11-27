"""Run with blender -b --python-exit-code 1 -P tests/validate_santa04.py."""
import json
import struct
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from pxr import Usd, UsdSkel

sys.path.insert(0, str(Path(__file__).resolve().parent))
from edition_checks import ROOT, check  # noqa: E402

check('santa04', 'Santa04_Gift_Presentation', 193,
      holds=[('hand.L', 'gift'), ('hand.R', 'gift')],
      props=['gift'], translucent=False,
      grip_offsets={'hand.L': Vector((-.16, -.04, 0)), 'hand.R': Vector((.16, -.04, 0))})

santa = bpy.data.objects['Santa04']
mesh = santa.data
scene = bpy.context.scene
bones = bpy.data.objects['Santa04_Rig'].pose.bones
light_names = {bone.name for bone in bones if bone.name.startswith('tree_light_')}
assert light_names, 'The tree must have animated bulbs'


def material_vertices(materials):
    slots = {mesh.materials.find(name) for name in materials}
    assert -1 not in slots, ('Missing prop material', materials)
    indices = {i for face in mesh.polygons if face.material_index in slots for i in face.vertices}
    vertices = [mesh.vertices[i] for i in indices]
    assert vertices, ('Missing prop geometry', materials)
    return vertices


def prop_vertices(materials, bone):
    group = santa.vertex_groups[bone].index
    vertices = material_vertices(materials)
    assert all(any(g.group == group and g.weight > .999 for g in v.groups) for v in vertices), (
        'Prop geometry must follow its bone rigidly', bone)
    return [v.co for v in vertices]


gift = prop_vertices(('Gift box sides', 'Gift box lid', 'Gift ribbon', 'Landmark on Robson logo'), 'gift')
tree = prop_vertices(('Fir needles', 'Fairy light casings'), 'root')
assert min(v.y for v in tree) > max(v.y for v in gift), 'The tree must stand behind the held gift'

logo = mesh.materials['Landmark on Robson logo']
base_color = logo.node_tree.nodes['Principled BSDF'].inputs['Base Color']
assert base_color.is_linked, 'The gift logo must use the supplied artwork texture'
texture = base_color.links[0].from_node
assert texture.type == 'TEX_IMAGE' and texture.image and texture.image.packed_file, 'The gift logo must be packed'

dip_frame, lift_frame, offer_frame, glance_frame = 21, 70, 116, 42
poses = []
for frame in (1, dip_frame, lift_frame, offer_frame):
    scene.frame_set(frame)
    poses.append(bones['gift'].head.copy())
start, dip, lifted, offered = poses
assert start.z - dip.z > .015, 'Santa must dip the gift before lifting it'
assert lifted.z - start.z > .18, 'Santa must raise the gift from the starting hold'
assert lifted.y - offered.y > .025, 'Santa must extend the raised gift toward the viewer'

for frame in (glance_frame, offer_frame):
    scene.frame_set(frame)
    gift_pose = bones['gift']
    gift_rotation = (gift_pose.matrix @ gift_pose.bone.matrix_local.inverted()).to_3x3()
    bow = gift_pose.head + gift_rotation @ Vector((0, .06, .20))
    target = bow if frame == glance_frame else scene.camera.location
    for name in ('head', 'eye.L', 'eye.R'):
        bone = bones[name]
        rotation = bone.matrix @ bone.bone.matrix_local.inverted()
        forward = rotation.to_3x3() @ Vector((0, -1, 0))
        eye_origin = bone.head if name != 'head' else (bones['eye.L'].head + bones['eye.R'].head) * .5
        assert forward.normalized().dot((target - eye_origin).normalized()) > .93, (
            frame, name, 'Santa must look at the gift before looking at the viewer')

light_vertices = material_vertices(('Warm fairy lights',))
light_groups = {santa.vertex_groups[name].index for name in light_names}
assert all(len(v.groups) == 1 and v.groups[0].weight > .999 for v in light_vertices), (
    'Each glowing bulb vertex must follow a single light bone')
assert {v.groups[0].group for v in light_vertices} == light_groups, (
    'Each light bone must carry glowing bulb geometry')

light_bones = [bones[name] for name in sorted(light_names)]
scene.frame_set(1)
centers = [bone.head.copy() for bone in light_bones]
scales = []
for frame in range(1, scene.frame_end + 1, 4):
    scene.frame_set(frame)
    assert all((bone.head - center).length < .0001 for bone, center in zip(light_bones, centers)), (
        frame, 'The bulbs must flash in place')
    scales.append([bone.scale.x for bone in light_bones])
assert all(min(samples) < .35 and max(samples) > .85 for samples in zip(*scales)), (
    'Every bulb must have a lit and a dim phase')
assert any(min(sample) < .35 and max(sample) > .85 for sample in scales), (
    'Different sets of bulbs must flash at different phases')

docs = ROOT / 'docs'
for filename in ('santa04.glb', 'santa04-android.glb'):
    raw = (docs / filename).read_bytes()
    json_length = struct.unpack_from('<I', raw, 12)[0]
    gltf = json.loads(raw[20:20 + json_length])
    animated_scales = {gltf['nodes'][channel['target']['node']]['name']
                       for channel in gltf['animations'][0]['channels'] if channel['target']['path'] == 'scale'}
    assert light_names <= animated_scales, (filename, 'Light scale channels missing')
    assert any(channel['target']['path'] == 'rotation' and
               gltf['nodes'][channel['target']['node']]['name'] == 'beard_drape'
               for channel in gltf['animations'][0]['channels']), (filename, 'Beard animation missing')

stage = Usd.Stage.Open(str(docs / 'santa04.usdz'))
animation = next(UsdSkel.Animation(prim) for prim in stage.Traverse() if prim.IsA(UsdSkel.Animation))
joints = {path.rsplit('/', 1)[-1]: i for i, path in enumerate(animation.GetJointsAttr().Get())}
assert light_names <= joints.keys(), 'USDZ light animation joints missing'
assert 'beard_drape' in joints, 'USDZ beard animation joint missing'
usd_scales = animation.GetScalesAttr()
scale_samples = [usd_scales.Get(t) for t in usd_scales.GetTimeSamples()]
for name in light_names:
    samples = [scales_at_time[joints[name]][0] for scales_at_time in scale_samples]
    assert min(samples) < .35 and max(samples) > .85, (name, 'USDZ light scale animation missing')

print('PASS: Santa04 gift lift and reach, beard clearance, packed logo, planted tree and staggered lights in both AR formats')
