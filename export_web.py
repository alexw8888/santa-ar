"""
Export santa_rigged.blend for WebAR.

    blender.exe -b santa_rigged.blend -P export_web.py

Writes next to this script:
  docs/santa.glb   - glTF binary with skin + "Santa_Wave" animation (Android / WebXR / desktop)
  docs/santa.usdz  - USDZ for iOS AR Quick Look
(docs/ is what GitHub Pages publishes.)
"""
import bpy, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "docs")
os.makedirs(OUT, exist_ok=True)

scene = bpy.context.scene
rig = bpy.data.objects["Santa_Rig"]
santa = bpy.data.objects["Santa"]

# Make sure the wave action is assigned so it gets exported.
act = bpy.data.actions.get("Santa_Wave")
if act and rig.animation_data:
    rig.animation_data.action = act

# Only export Santa + rig (no camera / light).
for ob in scene.objects:
    ob.select_set(ob in (rig, santa))
bpy.context.view_layer.objects.active = rig

# Blender is Z-up, Santa faces -Y. glTF export converts to Y-up; Santa then faces +Z,
# which is "toward the viewer" in model-viewer. Good.
bpy.ops.export_scene.gltf(
    filepath=os.path.join(OUT, "santa.glb"),
    export_format='GLB',
    use_selection=True,
    export_apply=False,          # keep armature modifier live (skinning)
    export_skins=True,
    export_animations=True,
    export_frame_range=True,
    export_yup=True,
)
print("[export] glb done")

try:
    kwargs = dict(
        filepath=os.path.join(OUT, "santa.usdz"),
        selected_objects_only=True,
        export_animation=True,
        export_materials=True,
    )
    # Skinned export options (names vary between Blender versions)
    props = bpy.ops.wm.usd_export.get_rna_type().properties.keys()
    for k in ("export_armatures", "export_shapekeys"):
        if k in props:
            kwargs[k] = True
    if "convert_orientation" in props:
        kwargs["convert_orientation"] = True
        kwargs["export_global_up_selection"] = 'Y'
        kwargs["export_global_forward_selection"] = 'NEGATIVE_Z'
    kwargs = {k: v for k, v in kwargs.items() if k in props or k == "filepath"}
    bpy.ops.wm.usd_export(**kwargs)
    print("[export] usdz done")
except Exception as e:
    print(f"[export] usdz FAILED: {e}")
