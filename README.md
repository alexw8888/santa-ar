# WebAR characters

Each version has its own public HTML page and model assets. GitHub Pages publishes `docs/` at https://alexw8888.github.io/santa-ar/.

| Version | Public page | Animation |
| --- | --- | --- |
| Santa 01 | [santa01.html](https://alexw8888.github.io/santa-ar/santa01.html) | Pour chai from a brass kettle while watching the glass, then raise the glass to his lips and sip it empty |
| Santa 02 | [santa02.html](https://alexw8888.github.io/santa-ar/santa02.html) | Lift an armful of Aisle24 groceries, glance down and settle them back into both hands |
| Santa 03 | [santa03.html](https://alexw8888.github.io/santa-ar/santa03.html) | Raise a steaming Bouquet Cafe mug to enjoy the aroma while a bouquet sways in the other hand |
| Santa 04 | [santa04.html](https://alexw8888.github.io/santa-ar/santa04.html) | Lift and gently rock a little lit tree crowned with the glowing Landmark on Robson sign |
| Santa 05 | [santa05.html](https://alexw8888.github.io/santa-ar/santa05.html) | Bring a strawberry cream bun up for a bite, then chew happily beside the Mello sack |
| Santa 06 | [santa06.html](https://alexw8888.github.io/santa-ar/santa06.html) | Lift a steaming Yunqueen rice noodle bowl to smell it while the yellow duck sways |

Open a page in Chrome on Android or Safari on iPhone/iPad. Each page attempts to launch AR automatically. On iPhone/iPad it opens AR Quick Look straight away, which downloads only the USDZ; the page holds back the GLB for the in-page 3D view until you return to the page or tap it, so the two downloads never compete. Android and desktop load the GLB first, since Scene Viewer and WebXR need it. Browsers that require a user gesture keep **View in your space** as a fallback. Desktop browsers show the interactive 3D model.

`export_santa.py` slims every edition's GLB and USDZ for phone downloads without touching the `.blend`. It halves the triangles of the beard and fur trim (and Santa 03's bouquet), halves every texture (never below 128 px) and writes them as JPEG at quality 70 in both files. Blender's USD exporter only writes PNG, so the exporter re-encodes the USDZ textures and repackages it; images with real transparency would stay PNG. Tune `DECIMATE`, `TEXTURE_SCALE` and `JPEG_QUALITY` at the top of the exporter.

| Edition | Triangles (scene → export) | GLB | USDZ |
| --- | --- | --- | --- |
| Santa 01 | 135k → 101k | 4.4 MB | 3.6 MB |
| Santa 02 | 149k → 115k | 4.7 MB | 5.6 MB |
| Santa 03 | 232k → 161k | 7.1 MB | 8.3 MB |
| Santa 04 | 153k → 119k | 5.6 MB | 5.9 MB |
| Santa 05 | 134k → 99k | 4.2 MB | 5.0 MB |
| Santa 06 | 153k → 119k | 4.9 MB | 5.8 MB |

## Santa 01

A rigged Santa modelled on the reference photo (`photos/`), with a 12.5-second loop: he pours chai from a brass kettle into a cutting-chai glass (timed stream, rising chai level), then raises the glass to his lips, tips it and drinks the chai, and returns to the initial pose.

The published animation is made in two steps. `build_santa01.py` builds the character with a pour-and-aroma animation (`Santa01_Pour_and_Smell`); `santa01_final_animation.py` then re-bakes it into `Santa01_Natural_Shoulders_Drink_Cup_Tilt`, which adds:

- Subtle secondary motion in the body, coat hem, sleeves, feet and hat tip, with the kettle following the right hand.
- Ease in and out on the original gestures, without changing the kettle's path.
- A slight torso counterlean as the kettle lifts, raising the kettle-side shoulder and dropping the glass-side one.
- The glass rising to his lips and tilting about 17°, with the left glove gripping it rigidly.
- Chai that fills as it is poured and drains as he drinks, so the glass is empty at both ends of the loop and playback wraps without a pop.

- A portly build: a round belly pushed forward over the belt, broad shoulders and thick sleeves and trousers.
- A wide stance: the legs splay out from the hips and the boots turn outward, as in the photo.
- He watches the glass, as in the photo: each eye has its own bone (parented to the head) that aims the iris at the glass every frame, and his head turns and nods to follow it through the pour and the aroma gesture.
- The face grins with a broad open mouth (lips, upper teeth, tongue) whose corners lift into the cheeks, smile creases, wide eyes, bushy arched eyebrows, wire spectacles, a big red nose and round rosy cheeks.
- The beard is wide and full, made of wavy, flattened locks; the moustache sweeps up into the cheeks; sideburns join the hat to the beard.
- The red garments use a generated photographic velvet swatch with fiber normals, varying roughness and soft sheen, at a consistent physical UV scale. Core color/normal/roughness maps also support AR viewers that do not render the optional sheen extension.
- The fur trim is plush, with soft clumps and fibers; the pompom is round and fluffy.
- Brown leather gloves; worn mid-brown work boots with thick soles, heels, toe-cap seams and brass ankle buckles; a wide leather belt with a large brass buckle.
- The golden brass kettle's large beaded oval cartouche carries raised "Chaiiwala" and "of London" lettering with a small kettle-and-glass emblem, modelled as geometry (Blender's built-in font) and wrapped to the kettle's curve.
- Generated textures are converted from linear to sRGB when written; the scene keeps them at full resolution (velvet 1024 px), and the exporter halves them into JPEG for the GLB and USDZ.
- AR Quick Look fixes: the exporter patches the glass and steam opacity into the USDZ (Blender writes every UsdPreviewSurface as opaque), and the mouth cavity faces the viewer because Quick Look culls back faces even on double-sided meshes.

Files:

- `build_santa01.py` generates `santa01.blend` and packs the textures into it. Temporary texture images in `generated/` are recreated on each build. `santa01.blend` keeps the pour-and-aroma animation because later editions are built from it.
- `santa01_final_animation.py` opens `santa01.blend` and writes the drinking animation to a new `santa01_FINAL_ANIMATED.blend` beside it (git-ignored); it never overwrites its source and refuses a file it has already animated. It also keeps each stage's earlier action as a backup.
- `assets/textures/santa01-velvet-source.png` is the original generated fabric swatch; the build creates optimized runtime maps from it.
- `export_santa.py` exports the named scene into `docs/santa01.glb` and `docs/santa01.usdz`.
- `docs/santa01.html` is the viewer; `docs/santa01-poster.webp` is its loading poster.
- `previews/santa01-*.png` show the front view, face, kettle lettering, fabric close-up and the ready, pour and aroma poses of the built (pre-drinking) animation.

Use an official Blender build with glTF and USD support (tested on 5.3). Build, animate, then export only the final action (the `--python-expr` step drops the stage backups, which would otherwise be exported as extra animations):

```sh
blender -b --factory-startup --python-exit-code 1 -P build_santa01.py -- previews
blender -b santa01.blend --python-exit-code 1 -P santa01_final_animation.py
blender -b santa01_FINAL_ANIMATED.blend --python-exit-code 1 --python-expr "import bpy; a = bpy.data.objects['Santa01_Rig'].animation_data.action; [bpy.data.actions.remove(x) for x in list(bpy.data.actions) if x != a]" -P export_santa.py -- santa01
```

Validate the model, loop, prop attachments, eye tracking and exports with the test below. It checks the built `santa01.blend`, then checks that the GLB carries only the final drinking action and that `docs/santa01.html` requests it:

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

## Santa 03 to 06

Each later edition is modelled on its photo in `photos/` and built from the packed `santa01.blend` by its own `build_santaNN.py`. They share `santa_kit.py`, which:

- opens the Santa 01 character, removes the chai props, mirrors the cupped glove onto the right hand and adds the edition's prop bones;
- models props from lathes, tubes, ellipsoids, two-sided petals/leaves and typeset lettering (flat, or wrapped around a mug or bowl), each bound rigidly to one bone and joined into the character mesh;
- recolours Santa's velvet and plush textures for new fabrics, keeping their pile;
- poses the arms by solving each elbow from the fixed shoulder to a wrist placed so the cupped glove wraps the prop, turns the head part way toward a target and aims the eye bones the rest of the way;
- bakes every frame into ordinary bone keys and saves the scene, previews and poster.

| Edition | Photo | Props and loop |
| --- | --- | --- |
| Santa 03 | `03 Bouquet Cafe Santa.jpg` | A big white Bouquet Cafe mug (wrapped lettering and lotus mark) with curling steam, a dense hand bouquet of roses, tulips, asters, daisies and lavender, and a crimson velvet sack brimming with flowers. Six seconds: he lifts the mug, breathes in the steam, lowers it; the bouquet sways throughout. |
| Santa 04 | `04 Landmark on Robson Santa.jpg` | A little fir tree with needle sprigs, red and green baubles, holly, a spiral of glowing fairy lights and a brass finial carrying the lit Landmark on Robson sign (tower in an arch, outlined lettering). Five seconds: he lifts and rocks the tree while looking up at the sign. |
| Santa 05 | `05 Mello Santa.jpg` | A sugared brioche with a cream ridge, piped swirls, a strawberry and a scalloped bite showing the filling, and a mustard velvet Mello sack (stacked outline lettering, jute rope) holding gifts, a gingerbread figure and a teddy. Five seconds: he raises the bun for a bite, lowers it and chews. |
| Santa 06 | `06 Yunqueen Santa.jpg` | A porcelain Yunqueen Rice Noodles bowl with broth, wavy rice noodles, pork mince, cilantro, scallions and chilli oil, steam, and the yellow plush duck with its deadpan eyes. Five seconds: he lifts the bowl to smell it while the duck sways. |

Steam materials are translucent; the exporter patches their opacity into the USDZ as for Santa 01. Run from the repository root, replacing `03` with the edition number:

```sh
blender -b --factory-startup --python-exit-code 1 -P build_santa03.py -- previews
blender -b santa03.blend --python-exit-code 1 -P export_santa.py -- santa03
blender -b --python-exit-code 1 -P tests/validate_santa03.py
```

Add shot names after the preview folder (for example `-- previews front`) to render only those previews. The tests check that the arm chains stay connected to fixed shoulders, both gloves stay locked to their props, props are skinned rigidly, the loop closes, and the GLB, USDZ and page agree.

Commit the generated models, page, poster, and previews to `main` to publish. No backend or custom build service is required.
