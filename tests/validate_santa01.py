"""Run with an official Blender build:
blender -b --python-exit-code 1 -P tests/validate_santa01.py
"""
import bpy, json, math, struct, zipfile
import numpy as np
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
# The garment detail must reach the exported material and repeat at fabric scale.
cloth=bpy.data.materials['Crimson_velvet']
cloth_bsdf=cloth.node_tree.nodes.get('Principled BSDF')
color_image=cloth_bsdf.inputs['Base Color'].links[0].from_node.image
assert tuple(color_image.size)==(1024,1024), 'Velvet color map is missing or too small'
assert cloth_bsdf.inputs['Normal'].is_linked
samples=np.asarray(color_image.pixels[:],dtype=np.float32).reshape(-1,4)[:,0]
assert np.percentile(samples,95)-np.percentile(samples,5)>.08, 'Fabric is effectively a flat color'
cloth_index=next(i for i,m in enumerate(mesh.data.materials) if m.name=='Crimson_velvet')
cloth_u=[mesh.data.uv_layers.active.data[i].uv.x for p in mesh.data.polygons if p.material_index==cloth_index for i in p.loop_indices]
assert max(cloth_u)-min(cloth_u)>3, 'Fabric UVs are stretched across the entire garment'

# santa01.blend holds only the final loop, built on the base character with its secondary bones.
assert rig.animation_data.action.name == 'Santa01_Natural_Shoulders_Drink_Cup_Tilt'
assert [a.name for a in bpy.data.actions] == [rig.animation_data.action.name], 'Leftover actions'
assert all(b in rig.data.bones for b in ('coat_hem', 'sleeve_sway.L', 'sleeve_sway.R', 'hat_tip'))
assert scene.frame_start == 1 and scene.frame_end == 300
# The dark mouth-interior material is reserved for the kettle spout, never the face.
head_group=mesh.vertex_groups['head'].index
mouth_index=next(i for i,m in enumerate(mesh.data.materials) if m.name=='Mouth_interior')
assert not any(p.material_index==mouth_index and any(g.group==head_group and g.weight>.99 for g in mesh.data.vertices[p.vertices[0]].groups) for p in mesh.data.polygons)

originals={name: rig.data.bones[name].matrix_local.inverted() for name in ('cup','kettle','hand.L','hand.R','stream')}

def transformed(name, point):
    return rig.pose.bones[name].matrix @ originals[name] @ Vector(point)

# Each glove holds its prop rigidly, the arms stay jointed and the shoulders ride the swaying chest.
loop=[]
levels, tilts, steam, stream_miss = {}, {}, {}, 0
for frame in range(1,301):
    scene.frame_set(frame)
    chest=rig.pose.bones['chest']
    chest_deform=chest.matrix @ chest.bone.matrix_local.inverted()
    for side,prop,bind_wrist in (('L','cup',(.31,-.44,1.12)),('R','kettle',(-.44,-.32,1.55))):
        expected=transformed(prop,bind_wrist)
        hand=rig.pose.bones['hand.'+side]
        assert (hand.head-expected).length < 1e-4, (frame, side, 'hand detached')
        upper,fore = (rig.pose.bones[n+'.'+side] for n in ('upper_arm','forearm'))
        assert (upper.tail-fore.head).length < 1e-4, (frame,side,'elbow gap')
        assert (fore.tail-hand.head).length < 1e-4, (frame,side,'wrist gap')
        assert (upper.head-chest_deform @ upper.bone.head_local).length < 1e-4, (frame,side,'shoulder off the chest')
    assert all(math.isfinite(c) for pb in rig.pose.bones for row in pb.matrix for c in row)
    levels[frame]=level=rig.pose.bones['liquid'].scale.y
    assert -1e-4 <= level <= 1.0001, 'Chai overflow'
    cup_up=rig.pose.bones['cup'].matrix.to_3x3() @ Vector((0,1,0))
    tilts[frame]=math.degrees(cup_up.angle(Vector((0,0,1))))
    steam[frame]=rig.pose.bones['aroma'].scale.y
    if rig.pose.bones['stream'].scale.x > .999:
        spout=transformed('kettle',(0,-.412,1.37))
        assert (spout-rig.pose.bones['stream'].head).length < 1e-4, (frame,'stream detached from spout')
        # The stream ends at the chai surface.
        endpoint=transformed('stream',(.15,-.48,1.168))
        surface=transformed('cup',(.15,-.48,1.045+.127*level))
        stream_miss=max(stream_miss,abs(endpoint.z-surface.z))
    if frame in (1,300): loop.append([pb.matrix.copy() for pb in rig.pose.bones])
assert max(abs(a[i][j]-b[i][j]) for a,b in zip(*loop) for i in range(4) for j in range(4)) < 1e-4, 'Loop does not close'
assert stream_miss < .001, ('Stream misses the chai surface', stream_miss)
# The glass starts and ends empty, fills while poured, and drains while he sips with it tipped to his lips.
assert levels[1] < .002 and levels[300] < .002, 'Glass should be empty at the loop boundary'
assert all(levels[f] > .999 for f in range(128, 218)), 'Glass should be full after the pour'
assert levels[248] < .002, 'Chai should be gone after the sip'
assert all(levels[f] >= levels[f+1] - 1e-6 for f in range(217, 248)), 'Chai should drain steadily'
assert 16 < max(tilts.values()) < 19, ('Glass should tip about 17 degrees (plus a little body sway)', max(tilts.values()))
assert max(tilts[f] for f in list(range(1, 210)) + list(range(260, 301))) < 2, 'Glass tips outside the sip'
assert max(steam[f] for f in range(255, 301)) < .01, 'Steam should fade with the last sip'
# The eyes track the glass: each gaze points closer to it than the face does, and it moves when the glass is raised.
gazes={}
for frame in (1,92,204):
    scene.frame_set(frame)
    glass=rig.pose.bones['cup'].head+Vector((0,0,.06))
    head=rig.pose.bones['head']
    face=(head.matrix.to_3x3() @ rig.data.bones['head'].matrix_local.to_3x3().inverted() @ Vector((0,-1,0))).normalized()
    for side in 'LR':
        eye=rig.pose.bones['eye.'+side]
        gaze=(eye.tail-eye.head).normalized()
        to_glass=(glass-eye.head).normalized()
        assert gaze.angle(to_glass) < face.angle(to_glass)-.1, (frame,side,'eye is not looking at the glass')
        gazes[frame,side]=gaze
assert all(gazes[1,s].angle(gazes[204,s]) > .15 for s in 'LR'), 'Eyes do not follow the raised glass'
# Skinning itself must stay finite, including a nearly collapsed liquid stream and an empty glass.
for frame in (1,42,62,92,128,160,190,222,240,258,300):
    scene.frame_set(frame)
    evaluated=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
    data=evaluated.to_mesh()
    assert all(math.isfinite(c) for v in data.vertices for c in v.co)
    evaluated.to_mesh_clear()
print(f'PASS: all 300 frames keep arm joints, rigid grips, stream on the spout (surface within {stream_miss*1000:.1f} mm), '
      f'the chai level, the {max(tilts.values()):.1f} degree sip and loop closure',flush=True)
raw=(ROOT/'docs/santa01.glb').read_bytes()
magic,version,length=struct.unpack_from('<4sII',raw)
assert magic==b'glTF' and version==2 and length==len(raw)
n,kind=struct.unpack_from('<I4s',raw,12)
gltf=json.loads(raw[20:20+n])
assert [a['name'] for a in gltf['animations']]==['Santa01_Natural_Shoulders_Drink_Cup_Tilt']
assert 'animation-name="Santa01_Natural_Shoulders_Drink_Cup_Tilt"' in (ROOT/'docs/santa01b.html').read_text(encoding='utf-8'), 'Viewer requests a different animation'
assert gltf['skins'] and gltf['images']
cloth_gltf=next(m for m in gltf['materials'] if m['name']=='Crimson_velvet')
assert 'baseColorTexture' in cloth_gltf['pbrMetallicRoughness']
assert 'metallicRoughnessTexture' in cloth_gltf['pbrMetallicRoughness']
assert 'normalTexture' in cloth_gltf and cloth_gltf['normalTexture'].get('scale',1)>.7
assert 'KHR_materials_sheen' in cloth_gltf.get('extensions',{}), 'Velvet sheen did not export'
assert 'KHR_materials_sheen' not in gltf.get('extensionsRequired',[]), 'Core AR viewers need a PBR fallback'

assert all('bufferView' in im for im in gltf['images']), 'Texture is external'
assert all('JOINTS_0' in p['attributes'] and 'WEIGHTS_0' in p['attributes'] for m in gltf['meshes'] for p in m['primitives'])
assert len(raw)<8*1024*1024, 'GLB download budget exceeded'
# Santa 01: brown leather and golden brass must not export as near-black or copper.
for name, channel_min in (('Brown_glove_leather', .02), ('Worn_boot_leather', .05), ('Golden_brass', .4)):
    image = bpy.data.materials[name].node_tree.nodes['Principled BSDF'].inputs['Base Color'].links[0].from_node.image
    red = np.asarray(image.pixels[:], dtype=np.float32).reshape(-1, 4)[:, 0]
    assert red.mean() > channel_min, (name, 'texture color space is wrong')
assert all(im['mimeType'] == 'image/jpeg' for im in gltf['images']), 'GLB textures should be JPEG'
print('PASS: self-contained GLB has skin, animation, and embedded material textures',flush=True)
path=ROOT/'docs/santa01.usdz'
with zipfile.ZipFile(path) as archive:
    assert archive.testzip() is None
    assert archive.namelist()[0].endswith(('.usd','.usdc','.usda'))
    assert not any(p.lower().endswith('.exr') for p in archive.namelist())
    textures=[p for p in archive.namelist() if p.lower().endswith(('.png','.jpg','.jpeg'))]
    assert textures and all(p.lower().endswith('.jpg') for p in textures), 'USDZ textures should be JPEG'
    data=path.read_bytes()
    for item in archive.infolist():
        assert item.compress_type==zipfile.ZIP_STORED
        name_len,extra_len=struct.unpack_from('<HH',data,item.header_offset+26)
        assert (item.header_offset+30+name_len+extra_len)%64==0
# AR Quick Look needs real opacity on the glass, and front-facing mouth faces (it culls back faces).
from pxr import Usd, UsdShade
stage = Usd.Stage.Open(str(path))
opacity = {p.GetParent().GetName(): UsdShade.Shader(p).GetInput('opacity').Get()
           for p in stage.Traverse() if UsdShade.Shader(p) and UsdShade.Shader(p).GetInput('opacity')}
assert opacity['Clear_glass'] < .5 and opacity['Chai_aroma'] < .5, ('Glass exports as opaque', opacity)
assert opacity['Laughing_mouth'] == 1
del stage
laugh = next(i for i, m in enumerate(mesh.data.materials) if m.name == 'Laughing_mouth')
assert all(p.normal.y < 0 for p in mesh.data.polygons if p.material_index == laugh), 'Mouth cavity faces away from the viewer'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.usd_import(filepath=str(path))
assert any(o.type=='ARMATURE' for o in bpy.context.scene.objects)
assert any(o.type=='MESH' for o in bpy.context.scene.objects)
assert len(bpy.data.actions)>0
print('PASS: textured USDZ is aligned, uncompressed, and reimports with its rig and animation',flush=True)
