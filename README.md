# WebAR characters

Each version has its own public HTML page and model assets. GitHub Pages publishes `docs/` at https://alexw8888.github.io/santa-ar/. [preview.html](https://alexw8888.github.io/santa-ar/preview.html) (`docs/preview.html`) links to all six pages, with each one's poster; add a card there for a new edition.

| Version | Public page | Animation |
| --- | --- | --- |
| Santa 01 | [santa01b.html](https://alexw8888.github.io/santa-ar/santa01b.html) | Pour chai from a brass kettle while watching the glass, then raise the glass to his lips and sip it empty |
| Santa 02 | [santa02.html](https://alexw8888.github.io/santa-ar/santa02.html) | Lift an armful of Aisle24 groceries, glance down and settle them back into both hands |
| Santa 03 | [santa03.html](https://alexw8888.github.io/santa-ar/santa03.html) | Raise a steaming Bouquet Cafe mug to enjoy the aroma while a bouquet sways in the other hand |
| Santa 04 | [santa04.html](https://alexw8888.github.io/santa-ar/santa04.html) | Lift and gently rock a little lit tree crowned with the glowing Landmark on Robson sign |
| Santa 05 | [santa05.html](https://alexw8888.github.io/santa-ar/santa05.html) | Lift a strawberry cream bun from chest height to his lips, bite a piece off the top, then lower it and chew beside the Mello sack |
| Santa 06 | [santa06.html](https://alexw8888.github.io/santa-ar/santa06.html) | Hold a steaming Yunqueen rice noodle bowl in one hand and lift a bundle of noodles with chopsticks in the other while the yellow duck sways |

Open a page in Chrome on Android or Safari on iPhone/iPad. Each page attempts to launch AR automatically. On iPhone/iPad it opens AR Quick Look straight away, which downloads only the USDZ; the page holds back the GLB for the in-page 3D view until you return to the page or tap it, so the two downloads never compete. Android and desktop load the GLB first, since Scene Viewer and WebXR need it. Browsers that require a user gesture keep **View in your space** as a fallback. Desktop browsers show the interactive 3D model.

`export_santa.py` slims every edition's GLB and USDZ for phone downloads without touching the `.blend`. It halves the triangles of the beard and fur trim (and Santa 03's bouquet), halves every texture (never below 128 px) and writes them as JPEG at quality 70 in both files. Blender's USD exporter only writes PNG, so the exporter re-encodes the USDZ textures and repackages it; images with real transparency would stay PNG. Tune `DECIMATE`, `TEXTURE_SCALE` and `JPEG_QUALITY` at the top of the exporter.

| Edition | Triangles (scene → export) | GLB | USDZ |
| --- | --- | --- | --- |
| Santa 01 | 135k → 101k | 4.4 MB | 3.6 MB |
| Santa 02 | 149k → 115k | 4.7 MB | 5.9 MB |
| Santa 03 | 232k → 161k | 7.2 MB | 8.8 MB |
| Santa 04 | 153k → 119k | 5.6 MB | 6.2 MB |
| Santa 05 | 137k → 102k | 4.4 MB | 5.5 MB |
| Santa 06 | 155k → 121k | 5.1 MB | 6.2 MB |

## How the editions are built

Every edition starts from one base Santa, so a fix to Santa himself reaches all of them:

- `build_santa_base.py` (with `santa_model.py`, the procedural character) writes `santa_base.blend`: the character with two cupped gloves (the right one mirrors the left), no props and no animation, packed with its generated textures. It is never published.
- `santa_motion.py` adds secondary-motion bones to the base (coat hem, both sleeves, hat tip) with the garment weights blended in, and provides `sway`: a gentle, loopable body sway with cloth follow-through and foot settling.
- `santa_kit.py` opens the base, renames it `SantaNN`, adds the edition's prop bones, joins its props, bakes its loop and saves `santaNN.blend` with previews and the page poster. Every bake adds the shared sway first, then solves the arms from the swaying shoulders, so held props stay locked in the gloves.
- `export_santa.py` writes each edition's `docs/santaNN.glb` and `docs/santaNN.usdz`.

Build the base first, then any edition; rebuild every edition after changing the base. Use an official Blender build with glTF and USD support (tested on 5.3), and run from the repository root:

```sh
blender -b --factory-startup --python-exit-code 1 -P build_santa_base.py
blender -b --factory-startup --python-exit-code 1 -P build_santa01.py -- previews
blender -b santa01.blend --python-exit-code 1 -P export_santa.py -- santa01
blender -b --python-exit-code 1 -P tests/validate_santa01.py
```

Replace `01` with the edition number for the others. Add shot names after the preview folder (for example `-- previews front`) to render only those previews; the `front` shot also writes the page poster. Generated texture images in `generated/` are recreated on each build; the `.blend` files pack them.

## The base Santa

Modelled on the Santa 01 reference photo (`photos/01 Chaiiwala Santa.jpg`):

- A portly build: a round belly pushed forward over the belt, broad shoulders and thick sleeves and trousers.
- A wide stance: the legs splay out from the hips and the boots turn outward, as in the photo.
- Each eye has its own bone (parented to the head), so editions aim the irises at what Santa is looking at while his head turns and nods part of the way.
- The face grins with a broad open mouth (lips, upper teeth, tongue) whose corners lift into the cheeks, smile creases, wide eyes, bushy arched eyebrows, wire spectacles, a big red nose and round rosy cheeks.
- The beard is wide and full, made of wavy, flattened locks; the moustache sweeps up into the cheeks; sideburns join the hat to the beard.
- The red garments use a generated photographic velvet swatch (`assets/textures/santa01-velvet-source.png`) with fiber normals, varying roughness and soft sheen, at a consistent physical UV scale. Core color/normal/roughness maps also support AR viewers that do not render the optional sheen extension.
- The fur trim is plush, with soft clumps and fibers; the pompom is round and fluffy.
- Brown leather gloves; worn mid-brown work boots with thick soles, heels, toe-cap seams and brass ankle buckles; a wide leather belt with a large brass buckle.
- Generated textures are converted from linear to sRGB when written; the scene keeps them at full resolution (velvet 1024 px), and the exporter halves them into JPEG for the GLB and USDZ.
- AR Quick Look fixes: the mouth cavity faces the viewer because Quick Look culls back faces even on double-sided meshes, and the exporter patches translucent materials' opacity into the USDZ (Blender writes every UsdPreviewSurface as opaque).

## Santa 01

`build_santa01.py` adds a golden brass kettle in the right glove (its own kettle grip replaces the base's cupped right glove) and a cutting-chai glass in the cupped left glove. The kettle's large beaded oval cartouche carries raised "Chaiiwala" and "of London" lettering with a small kettle-and-glass emblem, modelled as geometry (Blender's built-in font) and wrapped to the kettle's curve.

The 12.5-second loop (`Santa01_Natural_Shoulders_Drink_Cup_Tilt`) is computed in one pass per frame, in layers:

1. The pour: the kettle lifts and pours a timed stream into the glass, then lowers; the glass rises toward his face; his head and eyes follow the glass. It is evaluated at an eased time, so each gesture eases in and out.
2. The shared sway, with the kettle, stream and glass following the gloves that hold them.
3. A subtle torso counterlean while the kettle is up: the kettle-side shoulder rises and the glass-side one drops, and the arms re-solve to the same wrists.
4. The sip: the glass comes to his lips and tips about 17°, the left glove gripping it. The chai fills while it is poured (the stream always reaches its surface) and drains while he sips, so the glass is empty at both ends of the loop and playback wraps without a pop; the steam fades with the last sip.

`previews/santa01-*.png` show the front view (also the poster), the pour and the sip, the face, the kettle lettering and a fabric close-up. The test checks the rigid grips, arm joints, stream, chai level, the sip, the eyes following the glass, loop closure, and that the GLB, USDZ and `docs/santa01b.html` agree.

## Santa 02

Modelled on `photos/02 Aisle24 Santa.jpg`. Santa cradles a scored baguette, spinach, tomatoes, stacked yogurt cups, bagged fruit, flour, milk and snacks. The open canvas Aisle24 tote stands beside his right boot. Both hands follow the groceries through a five-second loop. `build_santa02.py` models the groceries itself and uses `santa_kit.py` to start from the base and bake the loop.

## Santa 03 to 06

Each is modelled on its photo in `photos/` by its own `build_santaNN.py`, using `santa_kit.py` to:

- model props from lathes, tubes, ellipsoids, two-sided petals/leaves and typeset lettering (flat, or wrapped around a mug or bowl), each bound rigidly to one bone and joined into the character mesh;
- recolour Santa's velvet and plush textures for new fabrics, keeping their pile;
- pose the arms by solving each elbow from the shoulder to a wrist placed so the cupped glove wraps the prop, turn the head part way toward a target and aim the eye bones the rest of the way;
- bake every frame, with the shared sway, into ordinary bone keys and save the scene, previews and poster.

| Edition | Photo | Props and loop |
| --- | --- | --- |
| Santa 03 | `03 Bouquet Cafe Santa.jpg` | A big white Bouquet Cafe mug (wrapped lettering and lotus mark) with curling steam, a dense hand bouquet of roses, tulips, asters, daisies and lavender, and a crimson velvet sack brimming with flowers. Six seconds: he lifts the mug, breathes in the steam, lowers it; the bouquet sways throughout. |
| Santa 04 | `04 Landmark on Robson Santa.jpg` | A little fir tree with needle sprigs, red and green baubles, holly, a spiral of glowing fairy lights and a brass finial carrying the lit Landmark on Robson sign (tower in an arch, outlined lettering). Five seconds: he lifts and rocks the tree while looking up at the sign. |
| Santa 05 | `05 Mello Santa.jpg` | A sugared brioche with a cream ridge, piped swirls, a strawberry, and a piece of crust over the top that he bites off (its own `chunk` bone shrinks into his mouth, leaving a scalloped bite showing the crumb and cream filling), and a mustard velvet Mello sack (stacked outline lettering, jute rope) holding gifts, a gingerbread figure and a teddy. Eight seconds: he lifts the whole bun from his chest; it rolls bite-side up and rises to wherever his lower lip is as his head leans in, he bites the top, then lowers the bitten bun and chews, and holds it for three more seconds (`REST` in the build script). The piece reappears on the last frame so the loop restarts with a whole bun. |
| Santa 06 | `06 Yunqueen Santa.jpg` | A porcelain Yunqueen Rice Noodles bowl with broth, wavy rice noodles, pork mince, cilantro, scallions and chilli oil, steam, bamboo chopsticks held the usual way in a right glove of its own (replacing the base's cupped one): the lower stick rests in the web of the thumb and on the ring fingertip and never moves, while the upper stick, held like a pencil between thumb, index and middle fingers, pivots on its own `stick` bone to open and pinch; and the yellow plush duck with its deadpan eyes. Six seconds: his left glove holds the bowl; his right dips the chopsticks into the broth, pinches a bundle of wavy noodles and lifts it above the bowl to admire (not to eat), then lowers it back and lets go while the duck sways. The bundle is six strands on a chain of 16 `noodle.NN` bones: it lies curled in the broth until pinched, then hangs from the tips and trails back into the bowl. |

Steam materials are translucent; the exporter patches their opacity into the USDZ as for Santa 01. The tests check that the arm chains stay connected and ride the swaying chest, both gloves stay locked to their props, props are skinned rigidly, the loop closes, and the GLB, USDZ and page agree.

Physical phone AR performance and native viewer behavior should also be checked on the target devices. Create later editions as separate numbered pages and asset sets (`santa07.html`, `santa07.glb`, `santa07.usdz`) with a matching scene/rig name and their own animation; the versioned exporter requires an explicit name so it never overwrites another edition's assets.

Commit the generated models, page, poster, and previews to `main` to publish. No backend or custom build service is required.
