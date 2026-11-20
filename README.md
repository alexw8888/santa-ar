# WebAR characters

Each version has its own public HTML page and model assets. GitHub Pages publishes `docs/` at https://alexw8888.github.io/santa-ar/.

| Version | Public page | Animation |
| --- | --- | --- |
| Boy | [index.html](https://alexw8888.github.io/santa-ar/) | Waving |
| Santa 01 | [santa01.html](https://alexw8888.github.io/santa-ar/santa01.html) | Pour chai from a brass kettle while watching the glass, then lift the upright glass to enjoy the aroma |
| Santa 02 | [santa02.html](https://alexw8888.github.io/santa-ar/santa02.html) | Lift an armful of Aisle24 groceries, glance down and settle them back into both hands |

Open a page in Chrome on Android or Safari on iPhone/iPad. Each page attempts to launch AR automatically after the model loads. Browsers that require a user gesture keep **View in your space** as a fallback. Desktop browsers show the interactive 3D model.

## Santa 01

A rigged Santa modelled on the reference photo (`photos/`), with a 12.5-second loop: he pours chai from a brass kettle into a cutting-chai glass (timed stream, rising chai level), then lifts the upright glass to enjoy the aroma and returns to the initial pose.

- A portly build: a round belly pushed forward over the belt, broad shoulders and thick sleeves and trousers.
- A wide stance: the legs splay out from the hips and the boots turn outward, as in the photo.
- He watches the glass, as in the photo: each eye has its own bone (parented to the head) that aims the iris at the glass every frame, and his head turns and nods to follow it through the pour and the aroma gesture.
- The face grins with a broad open mouth (lips, upper teeth, tongue) whose corners lift into the cheeks, smile creases, wide eyes, bushy arched eyebrows, wire spectacles, a big red nose and round rosy cheeks.
- The beard is wide and full, made of wavy, flattened locks; the moustache sweeps up into the cheeks; sideburns join the hat to the beard.
- The red garments use a generated photographic velvet swatch with fiber normals, varying roughness and soft sheen, at a consistent physical UV scale. Core color/normal/roughness maps also support AR viewers that do not render the optional sheen extension.
- The fur trim is plush, with soft clumps and fibers; the pompom is round and fluffy.
- Brown leather gloves; worn mid-brown work boots with thick soles, heels, toe-cap seams and brass ankle buckles; a wide leather belt with a large brass buckle.
- The golden brass kettle's large beaded oval cartouche carries raised "Chaiiwala" and "of London" lettering with a small kettle-and-glass emblem, modelled as geometry (Blender's built-in font) and wrapped to the kettle's curve.
- Generated textures are converted from linear to sRGB when written; GLB textures are exported as JPEG to keep the GLB around 7 MB.
- AR Quick Look fixes: the exporter patches the glass and steam opacity into the USDZ (Blender writes every UsdPreviewSurface as opaque), and the mouth cavity faces the viewer because Quick Look culls back faces even on double-sided meshes.

Files:

- `build_santa01.py` generates `santa01.blend` and packs the textures into it. Temporary texture images in `generated/` are recreated on each build.
- `assets/textures/santa01-velvet-source.png` is the original generated fabric swatch; the build creates optimized runtime maps from it.
- `export_santa.py` exports the named scene into `docs/santa01.glb` and `docs/santa01.usdz`.
- `docs/santa01.html` is the viewer; `docs/santa01-poster.webp` is its loading poster.
- `previews/santa01-*.png` show the front view, face, kettle lettering, fabric close-up and the ready, pour and aroma poses.

Use an official Blender build with glTF and USD support (tested on 5.3):

```sh
blender -b --factory-startup --python-exit-code 1 -P build_santa01.py -- previews
blender -b santa01.blend --python-exit-code 1 -P export_santa.py -- santa01
```

Validate the model, loop, prop attachments, eye tracking and exports with:

```sh
blender -b --python-exit-code 1 -P tests/validate_santa01.py
```

The build also runs with Blender as a Python module (`pip install bpy`): `python3 build_santa01.py -- previews`. Add `quick` after the preview folder to skip the animation bake and render only the face, front and kettle previews.

Physical phone AR performance and native viewer behavior should also be checked on the target devices.

Create later editions as separate numbered pages and asset sets: `santa02.html`, `santa02.glb`, `santa02.usdz`, and so on. Give each edition a matching Blender scene/rig name and its own animation. Never overwrite an earlier edition’s assets when adding a new action. The versioned exporter requires an explicit name to avoid accidentally replacing another edition.

## Santa 02

Modelled on `photos/02 Aisle24 Santa.jpg`. Santa cradles a scored baguette, spinach, tomatoes, stacked yogurt cups, bagged fruit, flour, milk and snacks. The open canvas Aisle24 tote stands beside his right boot. Both hands follow the groceries through a five-second loop.

`build_santa02.py` uses the packed `santa01.blend` made by `build_santa01.py` as its character source. The grocery geometry, materials, pose and animation are built specifically for this edition. Run from the repository root:

```sh
blender -b --factory-startup --python-exit-code 1 -P build_santa02.py -- previews
blender -b santa02.blend --python-exit-code 1 -P export_santa.py -- santa02
blender -b --python-exit-code 1 -P tests/validate_santa02.py
```

The build writes the editable scene, three preview PNGs and the viewer poster. The exporter writes the GLB and USDZ used by `docs/santa02.html`.

## Original boy

- `build_boy.py` builds `boy_rigged.blend`.
- `export_web.py` exports `docs/boy.glb` and `docs/boy.usdz`.
- `rest.png`, `wave.png`, and `pose.png` preview the boy.

```sh
blender -b --factory-startup --python-exit-code 1 -P build_boy.py -- .
blender -b boy_rigged.blend --python-exit-code 1 -P export_web.py
```

Commit the generated models, page, poster, and previews to `main` to publish. No backend or custom build service is required.
