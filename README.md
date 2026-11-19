# Boy AR

A procedural, rigged boy built in Blender, with short brown hair, a blue sweatshirt, jeans, and sneakers. View him in AR on your phone.

**Live page:** https://alexw8888.github.io/santa-ar/

Open it in Chrome on Android or Safari on iPhone/iPad. The page attempts to launch AR automatically after the model loads. Browsers that require a user gesture keep **View in your space** available as a one-tap fallback. Desktop browsers show the interactive 3D model.

## Files

- `rest.png`, `wave.png`, and `pose.png` preview the model in three poses.
- `build_boy.py` builds `boy_rigged.blend` (mesh, rig, wave animation).
- `export_web.py` exports `docs/boy.glb` and `docs/boy.usdz` from the .blend.
- `docs/index.html` is the WebAR viewer (uses `<model-viewer>`). GitHub Pages serves the `docs` folder.

## Updating the model

Use an official Blender build with glTF and USD export support (tested with Blender 4.3.2).

```
blender -b --factory-startup --python-exit-code 1 -P build_boy.py -- .
blender -b boy_rigged.blend --python-exit-code 1 -P export_web.py
git add -A
git commit -m "Update model"
git push
```
