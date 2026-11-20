"""Export a numbered Santa without changing any other version.

blender -b santa01.blend --python-exit-code 1 -P export_santa.py -- santa01
blender -b santa01b.blend --python-exit-code 1 -P export_santa.py -- santa01b

Editions after santa01 embed JPEG textures in the GLB to stay within the download budget.
"""
import bpy, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
if len(args) != 1 or not re.fullmatch(r'santa[0-9]{2,}[a-z]?', args[0]):
    raise ValueError('Pass a numbered version after --, for example santa01 or santa01b')
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
    **({} if version == 'santa01' else dict(export_image_format='JPEG', export_image_quality=88)),
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

# Blender's USD exporter always writes UsdPreviewSurface opacity = 1, so glass and steam come out
# solid in AR Quick Look. Patch the material's alpha into the shader and repackage the USDZ.
alphas = {}
for mat in bpy.data.materials:
    bsdf = mat.node_tree.nodes.get('Principled BSDF') if mat.node_tree else None
    if bsdf and not bsdf.inputs['Alpha'].is_linked and bsdf.inputs['Alpha'].default_value < 1:
        alphas[mat.name] = bsdf.inputs['Alpha'].default_value
if alphas:
    import shutil, tempfile, zipfile
    from pxr import Sdf, Usd, UsdShade, UsdUtils
    usdz = os.path.join(out, version + '.usdz')
    work = tempfile.mkdtemp()
    try:
        with zipfile.ZipFile(usdz) as archive:
            archive.extractall(work)
            root = archive.namelist()[0]
        stage = Usd.Stage.Open(os.path.join(work, root))
        patched = set()
        for prim in stage.Traverse():
            shader = UsdShade.Shader(prim)
            name = prim.GetParent().GetName()
            if shader and shader.GetIdAttr().Get() == 'UsdPreviewSurface' and name in alphas:
                shader.CreateInput('opacity', Sdf.ValueTypeNames.Float).Set(alphas[name])
                patched.add(name)
        assert patched == set(alphas), ('Transparent materials not found in USD', set(alphas) - patched)
        stage.GetRootLayer().Save()
        del stage
        os.remove(usdz)
        assert UsdUtils.CreateNewARKitUsdzPackage(Sdf.AssetPath(os.path.join(work, root)), usdz)
        print('[export] USDZ opacity set for', ', '.join(sorted(patched)), flush=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)

for ext in ('glb','usdz'):
    path = os.path.join(out, version + '.' + ext)
    assert os.path.getsize(path) > 0
    print('[export]', version, ext, os.path.getsize(path), 'bytes', flush=True)
