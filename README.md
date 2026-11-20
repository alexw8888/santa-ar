# WebAR characters

Each version has its own public HTML page and model assets. GitHub Pages publishes `docs/` at https://alexw8888.github.io/santa-ar/.

| Version | Public page | Animation |
| --- | --- | --- |
| Boy | [index.html](https://alexw8888.github.io/santa-ar/) | Waving |
| Santa 01 | [santa01.html](https://alexw8888.github.io/santa-ar/santa01.html) | Pour coffee from a brass kettle, then lift the upright glass to enjoy the aroma |
| Santa 01b | [santa01b.html](https://alexw8888.github.io/santa-ar/santa01b.html) | Same pour-and-aroma loop with chai, remodelled to match the reference photo more closely |

Open a page in Chrome on Android or Safari on iPhone/iPad. Each page attempts to launch AR automatically after the model loads. Browsers that require a user gesture keep **View in your space** as a fallback. Desktop browsers show the interactive 3D model.

## Santa 01

A reference-inspired, rigged Santa with a warm closed-mouth smile, soft cheek blush, relaxed eyes, a shaped coat, layered beard, fur trim, wire spectacles, sculpted gloves, stitched leather boots, a brass kettle, and a ribbed coffee glass. The red garments use a generated photographic velvet swatch with fiber normals, varying roughness, and soft sheen. Fabric UVs use a consistent physical scale; shallow waist and elbow folds add cloth shaping. Core color/normal/roughness maps also support AR viewers that do not render the optional sheen extension. The 12.5-second loop includes a timed coffee stream, a rising coffee level, pouring, a closed-mouth smile, a gentle lean toward the upright glass to smell the coffee, and a return to the initial pose.

- `assets/textures/santa01-velvet-source.png` is the original generated fabric swatch. The build creates optimized runtime maps from it.
- `previews/santa01-fabric.png` shows the garment material close up.
- `build_santa01.py` generates `santa01.blend` and packs the textures into it. Temporary texture images in `generated/` are recreated on each build.
- `export_santa.py` exports the named scene into `docs/santa01.glb` and `docs/santa01.usdz`.
- `docs/santa01.html` is this version’s viewer; `docs/santa01-poster.webp` is its loading poster.
- `previews/santa01-ready.png`, `santa01-pour.png`, and `santa01-aroma.png` show the three main poses; `previews/santa01-face.png` shows the softened smiling expression.

Use an official Blender build with glTF and USD support (tested on 4.3.2):

```sh
blender -b --factory-startup --python-exit-code 1 -P build_santa01.py -- previews
blender -b santa01.blend --python-exit-code 1 -P export_santa.py -- santa01
```

Validate the model, loop, prop attachments, and exports with:

```sh
blender -b --python-exit-code 1 -P tests/validate_santa01.py
```

Physical phone AR performance and native viewer behavior should also be checked on the target devices.

## Santa 01b

A closer match to the reference photo, built by `build_santa01b.py` with the same rig, prop anchors and 12.5-second loop as Santa 01. Changes from Santa 01:

- Generated textures are converted from linear to sRGB when written, so the gloves and boots are brown leather and the kettle is golden brass instead of near-black and copper.
- The fur trim is plush, with soft clumps and fibers instead of spiky dots; the pompom is round and fluffy.
- A portlier build: a rounder belly pushed forward over the belt, broader shoulders and thicker sleeves and trousers.
- A wide stance: the legs splay out from the hips and the boots turn outward, as in the photo.
- The face grins with a broad open mouth (lips, upper teeth, tongue) whose corners lift into the cheeks, smile creases, wide eyes, bushy arched eyebrows, a bigger red nose and round rosy cheeks.
- The beard is wider and fuller, made of wavy, flattened locks; the moustache sweeps up into the cheeks; sideburns join the hat to the beard.
- Worn mid-brown work boots with thick soles, heels, toe-cap seams and brass ankle buckles; a wide leather belt with a large brass buckle.
- The kettle's beaded oval cartouche carries raised "Chaiiwala" and "of London" lettering with a small kettle-and-glass emblem, modelled as geometry (Blender's built-in font) and wrapped to the kettle's curve; the drink is milky chai.
- GLB textures are exported as JPEG, so the GLB is about 6.8 MB instead of 14 MB.

```sh
blender -b --factory-startup --python-exit-code 1 -P build_santa01b.py -- previews
blender -b santa01b.blend --python-exit-code 1 -P export_santa.py -- santa01b
blender -b --python-exit-code 1 -P tests/validate_santa01b.py
```

The build also runs with Blender as a Python module (`pip install bpy`): `python3 build_santa01b.py -- previews`. Add `quick` after the preview folder to skip the animation bake and render only the face, front and kettle previews. Previews are in `previews/santa01b-*.png`.

Create later editions as separate numbered pages and asset sets: `santa02.html`, `santa02.glb`, `santa02.usdz`, and so on. Give each edition a matching Blender scene/rig name and its own animation. Never overwrite an earlier edition’s assets when adding a new action. The versioned exporter requires an explicit name to avoid accidentally replacing another edition.

## Original boy

- `build_boy.py` builds `boy_rigged.blend`.
- `export_web.py` exports `docs/boy.glb` and `docs/boy.usdz`.
- `rest.png`, `wave.png`, and `pose.png` preview the boy.

```sh
blender -b --factory-startup --python-exit-code 1 -P build_boy.py -- .
blender -b boy_rigged.blend --python-exit-code 1 -P export_web.py
```

Commit the generated models, page, poster, and previews to `main` to publish. No backend or custom build service is required.
