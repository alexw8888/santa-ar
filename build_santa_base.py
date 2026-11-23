"""Build the base Santa that every edition starts from.

blender -b --factory-startup --python-exit-code 1 -P build_santa_base.py -- [preview_dir]

Writes santa_base.blend: the character from santa_model.py (portly body, velvet coat, fur trim,
laughing face, beard, cap, boots) with two cupped gloves and no props or animation, packed with
its generated textures. The rig carries the secondary-motion bones from santa_motion.py (coat hem,
sleeves, hat tip) with the garment weights already blended, so each edition only adds its props,
prop bones and loop. The optional preview folder receives a front view and a face close-up.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402

import santa_model as model  # noqa: E402
import santa_motion  # noqa: E402

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
PREVIEWS = os.path.abspath(ARGS[0]) if ARGS else None

scene = model.begin('santa_base')
scene.name = 'SantaBase'
model.character_materials()
model.new_mesh()
model.character()
santa, rig = model.objects('Santa', scene)
santa_motion.ensure_secondary_rig(rig, santa)
assert all(v.groups and abs(sum(g.weight for g in v.groups) - 1) < 1e-4 for v in santa.data.vertices)
cam = model.studio(scene)
for ob in scene.objects:
    ob.select_set(False)
rig.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(model.HERE, 'santa_base.blend'), compress=True)
print('[model] Saved santa_base.blend', flush=True)

if PREVIEWS:
    from mathutils import Vector
    os.makedirs(PREVIEWS, exist_ok=True)
    for name, location, target, lens, size in (
            ('face', (-.20, -1.60, 1.85), (0, -.04, 1.75), 78, (600, 600)),
            ('front', (-.15, -6.6, 1.25), (-.10, -.12, 1.02), 70, (800, 1000))):
        cam.location = location
        cam.rotation_euler = (Vector(target) - cam.location).to_track_quat('-Z', 'Y').to_euler()
        cam.data.lens = lens
        scene.render.resolution_x, scene.render.resolution_y = size
        scene.render.filepath = os.path.join(PREVIEWS, 'santa_base-' + name + '.png')
        bpy.ops.render.render(write_still=True)
        print('[render]', name, flush=True)
