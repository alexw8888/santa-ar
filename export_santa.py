"""Export a numbered Santa without changing any other version.

blender -b santa01.blend --python-exit-code 1 -P export_santa.py -- santa01

The exports are slimmed for phone downloads; the .blend is never saved, so it keeps full detail:
- the beard and fur trim, the densest geometry, are decimated (DECIMATE);
- every texture is halved (TEXTURE_SCALE, never below MIN_TEXTURE px) and written as JPEG at
  JPEG_QUALITY in both the GLB and the USDZ. Images with real transparency stay PNG.
It also writes santaNN-android.glb for Scene Viewer (see scene_viewer_glb.py).
"""
import bpy, os, re, struct, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
# material -> fraction of triangles kept. The beard and fur are on every edition; the rest are
# Santa 03's flowers, which alone nearly double that edition's geometry.
DECIMATE = {'Silver_beard': .5, 'Ivory_plush_fur': .5,
            'Crimson rose petals': .5, 'Blush rose petals': .5, 'Rose heart': .5, 'Blush rose heart': .5,
            'Rose sepals': .4, 'Silver dollar eucalyptus': .6, 'Blue eucalyptus': .6}
TEXTURE_SCALE = .5
MIN_TEXTURE = 128
JPEG_QUALITY = 70
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
if len(args) != 1 or not re.fullmatch(r'santa[0-9]{2,}[a-z]?', args[0]):
    raise ValueError('Pass a numbered version after --, for example santa01 or santa02')
version = args[0]
name = version.capitalize()
rig = bpy.data.objects[name + '_Rig']
mesh = bpy.data.objects[name]
scene = bpy.context.scene
scene.frame_set(1)
out = os.path.join(HERE, 'docs')
os.makedirs(out, exist_ok=True)
# Fail before writing either file if this Blender build lacks USD support.
props = bpy.ops.wm.usd_export.get_rna_type().properties.keys()

def triangles():
    mesh.data.calc_loop_triangles()
    return len(mesh.data.loop_triangles)

# -------- geometry: decimate the beard locks and fur trim in place (in memory only)
before = triangles()
for ob in scene.objects:
    ob.select_set(ob == mesh)
bpy.context.view_layer.objects.active = mesh
for material, ratio in DECIMATE.items():
    slot = next((i for i, m in enumerate(mesh.data.materials) if m and m.name == material), None)
    if slot is None:
        continue
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    mesh.active_material_index = slot
    bpy.ops.object.material_slot_select()
    bpy.ops.mesh.decimate(ratio=ratio)
    bpy.ops.object.mode_set(mode='OBJECT')
weights = [sum(g.weight for g in v.groups) for v in mesh.data.vertices]
assert all(abs(w - 1) < 1e-3 for w in weights), 'Decimation broke the skin weights'
print(f'[export] triangles {before} -> {triangles()}', flush=True)

# -------- textures: halve every image in memory; both exporters write the smaller pixels
targets = {}
for im in bpy.data.images:
    if im.source == 'FILE' and im.size[0] and im.size[1]:
        size = tuple(max(MIN_TEXTURE, min(s, round(s * TEXTURE_SCALE))) for s in im.size)
        if size != tuple(im.size):
            im.scale(*size)
        targets[im.name] = size

for ob in scene.objects:
    ob.select_set(ob in (rig, mesh))
bpy.context.view_layer.objects.active = rig
bpy.ops.export_scene.gltf(
    filepath=os.path.join(out, version + '.glb'),
    export_format='GLB', use_selection=True, export_apply=False,
    export_skins=True, export_animations=True, export_frame_range=True,
    export_yup=True, export_cameras=False, export_lights=False,
    export_image_format='JPEG', export_image_quality=JPEG_QUALITY,
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

# -------- USDZ repackage. Blender's USD exporter writes every texture as PNG and every
# UsdPreviewSurface as opaque, so glass and steam come out solid in AR Quick Look. Re-encode the
# textures as JPEG at the target size, patch the materials' alpha in, and repackage the USDZ.
import shutil, tempfile, zipfile
from pxr import Sdf, Usd, UsdShade, UsdUtils
alphas = {}
for mat in bpy.data.materials:
    bsdf = mat.node_tree.nodes.get('Principled BSDF') if mat.node_tree else None
    if bsdf and not bsdf.inputs['Alpha'].is_linked and bsdf.inputs['Alpha'].default_value < 1:
        alphas[mat.name] = bsdf.inputs['Alpha'].default_value

def safe(text):
    return re.sub(r'[^A-Za-z0-9_.-]', '_', text)
safe_targets = {safe(k): v for k, v in targets.items()}

def to_jpeg(png):
    """Resize a USDZ texture to its target and re-encode it; return the new path (or the PNG kept)."""
    stem = os.path.splitext(os.path.basename(png))[0]
    target = targets.get(stem) or safe_targets.get(safe(stem))
    assert target, ('USDZ texture does not match a Blender image', stem)
    with open(png, 'rb') as f:
        color_type = struct.unpack('>B', f.read(26)[25:26])[0]
    im = bpy.data.images.load(png, check_existing=False)
    try:
        if tuple(im.size) != target:
            im.scale(*target)
        if color_type in (4, 6):   # PNG with an alpha channel: keep it if any pixel is see-through
            pixels = np.empty(im.size[0] * im.size[1] * 4, np.float32)
            im.pixels.foreach_get(pixels)
            if pixels[3::4].min() < .999:
                im.save(filepath=png)
                return png
        jpg = os.path.splitext(png)[0] + '.jpg'
        im.file_format = 'JPEG'
        im.save(filepath=jpg, quality=JPEG_QUALITY)
        os.remove(png)
        return jpg
    finally:
        bpy.data.images.remove(im)

usdz = os.path.join(out, version + '.usdz')
work = tempfile.mkdtemp()
try:
    with zipfile.ZipFile(usdz) as archive:
        archive.extractall(work)
        root = archive.namelist()[0]
    renamed = {}
    for folder, _, files in os.walk(work):
        for file in files:
            if file.lower().endswith('.png'):
                old = os.path.join(folder, file)
                new = to_jpeg(old)
                renamed[os.path.relpath(old, work).replace(os.sep, '/')] = os.path.relpath(new, work).replace(os.sep, '/')
    stage = Usd.Stage.Open(os.path.join(work, root))
    patched, relinked = set(), set()
    for prim in stage.Traverse():
        for attr in prim.GetAttributes():
            value = attr.Get() if attr.GetTypeName() == Sdf.ValueTypeNames.Asset else None
            if value and value.path.endswith('.png'):
                key = next((k for k in renamed if value.path.endswith(k)), None)
                assert key, ('USD references a texture that was not packaged', value.path)
                if renamed[key] != key:
                    attr.Set(Sdf.AssetPath(value.path[:-len(key)] + renamed[key]))
                relinked.add(key)
        shader = UsdShade.Shader(prim)
        material = prim.GetParent().GetName()
        if shader and shader.GetIdAttr().Get() == 'UsdPreviewSurface' and material in alphas:
            shader.CreateInput('opacity', Sdf.ValueTypeNames.Float).Set(alphas[material])
            patched.add(material)
    assert patched == set(alphas), ('Transparent materials not found in USD', set(alphas) - patched)
    assert relinked == set(renamed), ('Textures not referenced by the USD', set(renamed) - relinked)
    stage.GetRootLayer().Save()
    del stage
    os.remove(usdz)
    assert UsdUtils.CreateNewARKitUsdzPackage(Sdf.AssetPath(os.path.join(work, root)), usdz)
    kept = sorted(k for k, v in renamed.items() if k == v)
    print(f'[export] USDZ textures: {len(renamed) - len(kept)} JPEG, {len(kept)} PNG kept for transparency',
          flush=True)
    if patched:
        print('[export] USDZ opacity set for', ', '.join(sorted(patched)), flush=True)
finally:
    shutil.rmtree(work, ignore_errors=True)

# -------- Android copy of the GLB for Scene Viewer, without the material extensions it rejects
sys.path.insert(0, HERE)
from scene_viewer_glb import write_android_glb
write_android_glb(version, out)

for ext in ('glb', '-android.glb', 'usdz'):
    path = os.path.join(out, version + ('' if ext.startswith('-') else '.') + ext)
    assert os.path.getsize(path) > 0
    print('[export]', version, ext, os.path.getsize(path), 'bytes', flush=True)
