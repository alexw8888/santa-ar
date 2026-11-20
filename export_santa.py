"""Export a numbered Santa without changing any other version.

blender -b santa01.blend --python-exit-code 1 -P export_santa.py -- santa01
"""
import bpy, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
if len(args) != 1 or not re.fullmatch(r'santa[0-9]{2,}', args[0]):
    raise ValueError('Pass a numbered version after --, for example santa01')
version = args[0]
name = version.capitalize()
rig = bpy.data.objects[name + '_Rig']
mesh = bpy.data.objects[name]
scene = bpy.context.scene
scene.frame_set(1)
for ob in scene.objects:
    ob.select_set(ob in (rig, mesh))
bpy.context.view_layer.objects.active = rig
out = os.path.join(HERE, 'docs')
os.makedirs(out, exist_ok=True)
# Fail before writing either file if this Blender build lacks USD support.
props = bpy.ops.wm.usd_export.get_rna_type().properties.keys()
bpy.ops.export_scene.gltf(
    filepath=os.path.join(out, version + '.glb'),
    export_format='GLB', use_selection=True, export_apply=False,
    export_skins=True, export_animations=True, export_frame_range=True,
    export_yup=True, export_cameras=False, export_lights=False,
)
kwargs = dict(
    filepath=os.path.join(out, version + '.usdz'),
    selected_objects_only=True, export_animation=True, export_materials=True,
    convert_world_material=False, export_lights=False, export_cameras=False,
    export_subdivision='TESSELLATE', export_armatures=True, export_shapekeys=True,
)
if 'convert_orientation' in props:
    kwargs.update(convert_orientation=True, export_global_up_selection='Y',
                  export_global_forward_selection='NEGATIVE_Z')
bpy.ops.wm.usd_export(**{k: v for k, v in kwargs.items() if k in props})
for ext in ('glb','usdz'):
    path = os.path.join(out, version + '.' + ext)
    assert os.path.getsize(path) > 0
    print('[export]', version, ext, os.path.getsize(path), 'bytes', flush=True)
