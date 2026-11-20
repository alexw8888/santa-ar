"""Run with an official Blender build:
blender -b --python-exit-code 1 -P tests/validate_santa01.py
"""
import bpy, json, math, struct, zipfile
from pathlib import Path
from mathutils import Vector
ROOT = Path(__file__).resolve().parents[1]
bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'santa01.blend'))
scene = bpy.context.scene
mesh = bpy.data.objects['Santa01']
rig = bpy.data.objects['Santa01_Rig']
mesh.data.calc_loop_triangles()
assert len(mesh.data.loop_triangles) < 160000, 'Mobile geometry budget exceeded'
assert all(v.groups and abs(sum(g.weight for g in v.groups)-1) < 1e-4 for v in mesh.data.vertices)
assert all(im.packed_file for im in bpy.data.images if im.source == 'FILE'), 'Texture is not packed'
assert rig.animation_data.action.name == 'Santa01_Pour_and_Drink'
assert scene.frame_start == 1 and scene.frame_end == 300
originals={name: rig.data.bones[name].matrix_local.inverted() for name in ('cup','kettle','hand.L','hand.R','stream')}

def transformed(name, point):
    return rig.pose.bones[name].matrix @ originals[name] @ Vector(point)

# Hand/prop attachment must remain rigid while both arms bend and the glass tips.
loop=[]
for frame in range(1,301):
    scene.frame_set(frame)
    for side,prop,bind_wrist in (('L','cup',(.31,-.44,1.12)),('R','kettle',(-.44,-.32,1.55))):
        expected=transformed(prop,bind_wrist)
        hand=rig.pose.bones['hand.'+side]
        assert (hand.head-expected).length < 1e-4, (frame, side, 'hand detached')
        upper,fore = (rig.pose.bones[n+'.'+side] for n in ('upper_arm','forearm'))
        assert (upper.tail-fore.head).length < 1e-4, (frame,side,'elbow gap')
        assert (fore.tail-hand.head).length < 1e-4, (frame,side,'wrist gap')
    assert all(math.isfinite(c) for pb in rig.pose.bones for row in pb.matrix for c in row)
    level=rig.pose.bones['liquid'].scale.y
    assert .4199 <= level <= 1.0001, 'Coffee overflow'
    flowing=rig.pose.bones['stream'].scale.x > .999
    if flowing:
        spout=transformed('kettle',(0,-.412,1.37))
        start=rig.pose.bones['stream'].head
        assert (spout-start).length < 1e-4, (frame,'stream detached from spout')
        endpoint=transformed('stream',(.15,-.48,1.168))
        assert abs(endpoint.z-(1.045+.127*level)) < 1e-4, (frame,'stream misses coffee surface')
    if frame in (1,300): loop.append([pb.matrix.copy() for pb in rig.pose.bones])
assert max(abs(a[i][j]-b[i][j]) for a,b in zip(*loop) for i in range(4) for j in range(4)) < 1e-4
# Skinning itself must stay finite, including a nearly collapsed liquid stream.
for frame in (1,42,62,92,128,160,190,222,258,300):
    scene.frame_set(frame)
    evaluated=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
    data=evaluated.to_mesh()
    assert all(math.isfinite(c) for v in data.vertices for c in v.co)
    evaluated.to_mesh_clear()
print('PASS: all 300 frames preserve arm joints, prop grips, stream alignment, coffee level, and loop closure',flush=True)
raw=(ROOT/'docs/santa01.glb').read_bytes()
magic,version,length=struct.unpack_from('<4sII',raw)
assert magic==b'glTF' and version==2 and length==len(raw)
n,kind=struct.unpack_from('<I4s',raw,12)
gltf=json.loads(raw[20:20+n])
assert [a['name'] for a in gltf['animations']]==['Santa01_Pour_and_Drink']
assert gltf['skins'] and gltf['images']
assert all('bufferView' in im for im in gltf['images']), 'Texture is external'
assert all('JOINTS_0' in p['attributes'] and 'WEIGHTS_0' in p['attributes'] for m in gltf['meshes'] for p in m['primitives'])
assert len(raw)<15*1024*1024, 'GLB download budget exceeded'
print('PASS: self-contained GLB has skin, animation, and embedded material textures',flush=True)
path=ROOT/'docs/santa01.usdz'
with zipfile.ZipFile(path) as archive:
    assert archive.testzip() is None
    assert archive.namelist()[0].endswith(('.usd','.usdc','.usda'))
    assert not any(p.lower().endswith('.exr') for p in archive.namelist())
    assert any(p.lower().endswith('.png') for p in archive.namelist())
    data=path.read_bytes()
    for item in archive.infolist():
        assert item.compress_type==zipfile.ZIP_STORED
        name_len,extra_len=struct.unpack_from('<HH',data,item.header_offset+26)
        assert (item.header_offset+30+name_len+extra_len)%64==0
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.usd_import(filepath=str(path))
assert any(o.type=='ARMATURE' for o in bpy.context.scene.objects)
assert any(o.type=='MESH' for o in bpy.context.scene.objects)
assert len(bpy.data.actions)>0
print('PASS: textured USDZ is aligned, uncompressed, and reimports with its rig and animation',flush=True)
