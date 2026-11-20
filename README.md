# WebAR characters

Each version has its own public HTML page and model assets. GitHub Pages publishes `docs/` at https://alexw8888.github.io/santa-ar/.

| Version | Public page | Animation |
| --- | --- | --- |
| Boy | [index.html](https://alexw8888.github.io/santa-ar/) | Waving |
| Santa 01 | [santa01.html](https://alexw8888.github.io/santa-ar/santa01.html) | Pour coffee from a brass kettle, then lift the glass and sip |

Open a page in Chrome on Android or Safari on iPhone/iPad. Each page attempts to launch AR automatically after the model loads. Browsers that require a user gesture keep **View in your space** as a fallback. Desktop browsers show the interactive 3D model.

## Santa 01

A reference-inspired, rigged Santa with a shaped coat, layered beard, fur trim, wire spectacles, sculpted gloves, stitched leather boots, a brass kettle, and a ribbed coffee glass. Image-based color, normal, and roughness/metallic maps supply surface detail. The 12.5-second loop includes a timed coffee stream, a rising coffee level, pouring, sipping, and a return to the initial pose.

- `build_santa01.py` generates `santa01.blend` and packs the textures into it. Temporary texture images in `generated/` are recreated on each build.
- `export_santa.py` exports the named scene into `docs/santa01.glb` and `docs/santa01.usdz`.
- `docs/santa01.html` is this version’s viewer; `docs/santa01-poster.webp` is its loading poster.
- `previews/santa01-ready.png`, `santa01-pour.png`, and `santa01-drink.png` show the three main poses.

Use an official Blender build with glTF and USD support (tested on 4.3.2):

```sh
blender -b --factory-startup --python-exit-code 1 -P build_santa01.py -- previews
blender -b santa01.blend --python-exit-code 1 -P export_santa.py -- santa01
```

Validate the model, loop, prop attachments, and exports with:

```sh
blender -b --python-exit-code 1 -P tests/validate_santa01.py
```

Santa01 has 114,730 triangles, 17 material slots, a roughly 9.1 MiB GLB, and a 10.4 MiB USDZ. Physical phone AR performance and native viewer behavior should also be checked on the target devices.

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
