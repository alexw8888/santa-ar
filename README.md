# WebAR characters

Each version has its own public HTML page and model assets. GitHub Pages publishes `docs/` at https://alexw8888.github.io/santa-ar/. [preview.html](https://alexw8888.github.io/santa-ar/preview.html) (`docs/preview.html`) links to all six pages, with each one's poster; add a card there for a new edition.

The six Santa pages and the Scene Viewer test share the bundled `@google/model-viewer` 4.0.0 release, `docs/model-viewer.min.js`, with its license in `docs/model-viewer-LICENSE`.

| Version | Public page | Animation |
| --- | --- | --- |
| Santa 01 | [Santa_Chaiiwala.html](https://alexw8888.github.io/santa-ar/Santa_Chaiiwala.html) | Pour chai from a brass kettle while watching the glass, then raise the glass to his lips and sip it empty |
| Santa 02 | [Santa_Aisle24.html](https://alexw8888.github.io/santa-ar/Santa_Aisle24.html) | Lift an armful of Aisle24 groceries, glance down and settle them back into both hands |
| Santa 03 | [Santa_Bouquet_Cafe.html](https://alexw8888.github.io/santa-ar/Santa_Bouquet_Cafe.html) | Hold a steaming Bouquet Café mug, raise a wrapped bouquet from his side and reach forward to offer it to the viewer at chest height, with the flowers tipped toward them, pausing so they can pose as if taking it |
| Santa 04 | [Santa_Landmark.html](https://alexw8888.github.io/santa-ar/Santa_Landmark.html) | Lift and reach forward to offer a Landmark on Robson gift box as the Christmas tree lights flash |
| Santa 05 | [Santa_Mello.html](https://alexw8888.github.io/santa-ar/Santa_Mello.html) | Lift a split Mello cream doughnut from chest height to his lips, bite a piece off the top, then lower it and chew beside the Mello sack |
| Santa 06 | [Santa_Yunqueen.html](https://alexw8888.github.io/santa-ar/Santa_Yunqueen.html) | Hold a steaming Yunqueen rice noodle bowl in one hand and lift a bundle of noodles with chopsticks in the other while the yellow duck flaps its wings |

Open a page in Chrome on Android or Safari on iPhone/iPad. On iPhone/iPad the page opens AR Quick Look straight away, which downloads only the USDZ; it holds back the GLB for the in-page 3D view until you return to the page or tap it, so the two downloads never compete. If Safari blocks the automatic launch, **View in your space** opens it. Android opens AR only when you tap **View in your space**, in Chrome's own AR (WebXR) first, which renders the full GLB. Phones without WebXR AR fall back to Scene Viewer and load `santaNN-android.glb` instead, since Scene Viewer downloads the page's model; on some phones Scene Viewer closes as soon as it opens, even with Google's own sample model, while WebXR works. AR opens only from a tap because Chrome treats an automatic jump to Scene Viewer as a redirect and closes the tab, so the page would be gone when AR ends. `docs/test/scene-viewer.html` launches Scene Viewer and WebXR variants one tap at a time to see which work on a phone. Desktop browsers show the interactive 3D model.

`export_santa.py` slims every edition's GLB and USDZ for phone downloads without touching the `.blend`. It halves the triangles of the beard and fur trim (and Santa 03's flowers), halves every texture (never below 128 px) and writes them as JPEG at quality 70 in both files. Blender's USD exporter only writes PNG, so the exporter re-encodes the USDZ textures and repackages it; images with real transparency would stay PNG. Tune `DECIMATE`, `TEXTURE_SCALE` and `JPEG_QUALITY` at the top of the exporter.

The exporter also writes `santaNN-android.glb` with `scene_viewer_glb.py`: the same GLB without the material extensions Scene Viewer rejects (sheen, specular, clearcoat, emissive strength). Scene Viewer treats any extension outside its short list as an error and closes as soon as it opens the model. Geometry, skin, animation and textures are unchanged; desktop browsers and phones with WebXR AR keep the full GLB. To refresh the Android copies without Blender, run `python scene_viewer_glb.py santa01 santa02 ...`.

| Edition | Triangles (scene → export) | GLB | USDZ |
| --- | --- | --- | --- |
| Santa 01 | 138k → 103k | 4.4 MB | 3.6 MB |
| Santa 02 | 155k → 122k | 5.2 MB | 6.4 MB |
| Santa 03 | 271k → 186k | 8.4 MB | 10.3 MB |
| Santa 04 | 178k → 143k | 6.7 MB | 7.8 MB |
| Santa 05 | 140k → 105k | 4.5 MB | 5.6 MB |
| Santa 06 | 166k → 131k | 5.7 MB | 4.6 MB |

## Create a release ZIP

With Node.js installed, run the following command from the repository root in Windows PowerShell or macOS Terminal.

```sh
node create-release.mjs
```

The script writes `santa-release.zip` in the repository root with the six public pages, their models and posters, and the shared model viewer and its license. The files are at the top level of the ZIP so they can be uploaded together to a web host. The script uses the ZIP tools bundled with Windows and macOS.

## How the editions are built

Every edition starts from one base Santa, so a fix to Santa himself reaches all of them:

- `build_santa_base.py` (with `santa_model.py`, the procedural character) writes `santa_base.blend`: the character with two cupped gloves (the right one mirrors the left), no props and no animation, packed with its generated textures. It is never published.
- `santa_motion.py` adds secondary-motion bones to the base (coat hem, both sleeves, hat tip) with the garment weights blended in, and provides `sway`: a gentle, loopable body sway with cloth follow-through and foot settling.
- `santa_kit.py` opens the base, renames it `SantaNN`, adds the edition's prop bones, joins its props, bakes its loop and saves `santaNN.blend` with previews and the page poster. Every bake adds the shared sway first, then solves the arms from the swaying shoulders, so held props stay locked in the gloves. After the head is posed, it bakes the lower beard separately so the locks hang in front of the coat during dips and nods.
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
- Each shoulder is a round velvet ball centred on the arm joint (`SHOULDER_BALL` in `santa_model.py`). Turning about its own centre it keeps the same round shape at any arm angle, and the top of the sleeve always stays tucked inside it, so the shoulder is never pointed and the sleeve never pokes out of the coat.
- Brown leather gloves; worn mid-brown work boots with thick soles, heels, toe-cap seams and brass ankle buckles; a wide leather belt with a large brass buckle.
- Generated textures are converted from linear to sRGB when written; the scene keeps them at full resolution (velvet 1024 px), and the exporter halves them into JPEG for the GLB and USDZ.
- AR Quick Look fixes: the mouth cavity faces the viewer because Quick Look culls back faces even on double-sided meshes, and the exporter patches translucent materials' opacity into the USDZ (Blender writes every UsdPreviewSurface as opaque).

## Santa 01

`build_santa01.py` adds a golden brass kettle in the right glove (its own kettle grip replaces the base's cupped right glove) and a cutting-chai glass in the cupped left glove. The kettle's front carries a white enamel plaque printed with the black Chaiiwala logo (`photos/chaiiwala_logo_black.png`) and wrapped to the kettle's curve. Its outline is a band with notched corners, an arched crest top and bottom and a pointed tip at each end, trimmed with a rolled gold rim, a fine inner gold line and gold beads. The ink is a near-zero-reflectance metal, so it stays a neutral black instead of picking up the brass and the red coat.

The 12.5-second loop (`Santa01_Natural_Shoulders_Drink_Cup_Tilt`) is computed in one pass per frame, in layers:

1. The pour: the kettle lifts and pours a timed stream into the glass, then lowers; the glass rises toward his face; his head and eyes follow the glass. It is evaluated at an eased time, so each gesture eases in and out.
2. The shared sway, with the kettle, stream and glass following the gloves that hold them.
3. A subtle torso counterlean while the kettle is up: the kettle-side shoulder rises and the glass-side one drops, and the arms re-solve to the same wrists.
4. The sip: the glass comes to his lips and tips about 17°, the left glove gripping it. The chai fills while it is poured (the stream always reaches its surface) and drains while he sips, so the glass is empty at both ends of the loop and playback wraps without a pop; the steam fades with the last sip.

`previews/santa01-*.png` show the front view (also the poster), the pour and the sip, the face, the kettle's logo plaque and a fabric close-up. The test checks the rigid grips, arm joints, stream, chai level, the sip, the eyes following the glass, loop closure, and that the GLB, USDZ and `docs/Santa_Chaiiwala.html` agree.

## Santa 02

Modelled on `photos/02 Aisle24 Santa.jpg`. Santa cradles a scored baguette, spinach, tomatoes, stacked yogurt cups, bagged fruit, flour, milk and snacks. The open canvas Aisle24 tote stands beside his right boot. In the ten-second loop, both hands follow the groceries as he lifts them, looks them over, nods and settles back into the carry. The baguette and spinach sway independently. `build_santa02.py` models the groceries itself and uses `santa_kit.py` to start from the base and bake the loop. As in the photo, the groceries are held in front of the beard: after baking, `tuck_beard` sweeps the loop and squashes the lower beard back against the coat wherever the shopping passes in front of it. Where the shopping sinks into the coat, the beard goes back into the coat behind it, or is removed if the shopping hides it on every frame. `tests/validate_santa02.py` checks that no beard sits in front of the shopping on any frame.

## Santa 03 to 06

Each is modelled on its photo in `photos/` by its own `build_santaNN.py`, using `santa_kit.py` to:

- model props from lathes, tubes, ellipsoids, two-sided petals/leaves and typeset lettering (flat, or wrapped around a mug or bowl) and printed images (`decal`, as for Santa 03's logo), each bound rigidly to one bone and joined into the character mesh;
- recolour Santa's velvet and plush textures for new fabrics, keeping their pile;
- pose the arms by solving each elbow from the shoulder to a wrist placed so the cupped glove wraps the prop, turn the head part way toward a target and aim the eye bones the rest of the way;
- bake every frame, with the shared sway, into ordinary bone keys and save the scene, previews and poster.

| Edition | Photo | Props and loop |
| --- | --- | --- |
| Santa 03 | `03 Bouquet Cafe suggested changes.jpg` (the café's mock-up) and `03 Bouquet Cafe bouquet *.jpg` | A big white mug (wider than his glove) in his right glove, printed with the café's logo file (`assets/bouquet-cafe-logo.jpg`, its background recoloured to the glaze), with curling steam. In his left, the café's wrapped bouquet: deep red roses with spiralling, cupped petals, ruffled peach-pink spray roses and buds, silver-dollar eucalyptus and limonium sprays, in a bright red paper cone whose two sheets sweep down to a deep V at the front (more roses and eucalyptus fill the opening), with tall burgundy sheets fanned behind, tied with a sheer white bow and a burgundy satin bow whose tails are printed "bouquet café". The crimson velvet sack of roses and eucalyptus stands behind his right side, so a guest can stand on his left. Eight seconds: a relaxed left glove supports the lower wrapping from behind, with short, gently bent fingers resting on one side of the paper below the flowers, leaving the bouquet's front and bow clear. It starts low beside him, leaning outward as in the reference; he raises it to chest height while glancing down to admire it (by 1.6 s), looks back at the camera, then leans in a little and extends his arm forward toward the viewer, tipping the flower heads toward the camera with a relaxed wrist (3.4–4.8 s). He holds the offer for about 1.6 s while looking at the camera, then draws it back and lowers it, 0.8 s each. The open flower arrangement faces the guest throughout; the mug stays steady. `previews/santa03-grip.png` shows the support from behind. |
| Santa 04 | `04 Landmark on Robson Santa.jpg` | A red gift box with the Landmark on Robson logo (`photos/landmark-on-robson-logo.png`) on the front and a large decorated Christmas tree behind Santa. In the eight-second loop, Santa dips slightly before raising the gift. He looks down during the lift and back at the viewer before offering the gift. His gloves pivot around the front corners as he reaches and settles. The tree lights flash in alternating groups. |
| Santa 05 | `05 Mello Santa.jpg`, and `mello.jpg` for the real doughnut | A Mello doughnut like the real one: a sugar-rolled brioche, deep red-brown and paler towards the cut (its crust texture is painted with granulated sugar), cut clean through into a front and a back half with whipped cream between them. The cream swells out round the rim in soft folds, thickest at the top-left, where the back half's crumb shows beside it and a piped swirl is crowned with half a strawberry. The cut runs through the top-right, so the piece he bites off (its own `chunk` bone shrinks into his mouth) leaves a scalloped bite showing crumb, cream and crumb. Beside him stands a mustard velvet Mello sack (stacked outline lettering, jute rope) holding gifts, a gingerbread figure and a teddy. Ten seconds: his eyes and head lead as he lifts the whole doughnut from his chest with both hands, straight up under his chin with its top tipped back a little, while he leans in and brings his head forward to meet it. He opens his mouth and bites the top (about 3.3 s), then lowers the bitten doughnut back to his chest while chewing with `mello_jaw` (a lower-mouth bone only this edition adds), gives a small satisfied nod and holds it there for the rest of the loop. The piece reappears on the last frame so the loop restarts with a whole doughnut. |
| Santa 06 | `06 Yunqueen Santa.jpg` | A porcelain Yunqueen Rice Noodles bowl with broth, wavy rice noodles, pork mince, cilantro, scallions, chilli oil and steam. The lower chopstick rests against the right glove while the upper chopstick pivots to pinch. In the twelve-second loop, Santa searches the broth briefly, lifts a bundle of noodles, looks up at the viewer, then lowers and releases the noodles. Six strands on a chain of 16 `noodle.NN` bones sway from the chopstick tips and trail back into the bowl. Beside him, the yellow plush duck turns its head and flaps its wings with its feet planted. |

Steam materials are translucent; the exporter patches their opacity into the USDZ as for Santa 01. The tests check that the arm chains stay connected and ride the swaying chest, both gloves stay locked to their props, props are skinned rigidly, the loop closes, and the GLB, USDZ and page agree.

Physical phone AR performance and native viewer behavior should also be checked on the target devices. Create later editions as separate numbered pages and asset sets (`santa07.html`, `santa07.glb`, `santa07.usdz`) with a matching scene/rig name and their own animation; the versioned exporter requires an explicit name so it never overwrites another edition's assets.

Commit the generated models, page, poster, and previews to `main` to publish. No backend or custom build service is required.
