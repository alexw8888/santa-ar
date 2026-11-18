# Santa AR

A procedural, rigged Santa Claus built in Blender, viewable in AR on your phone.

**Live page:** https://alexw8888.github.io/santa-ar/

Open it in Chrome on Android or Safari on iPhone/iPad, then tap **View in your space**.

## Files

- `build_santa.py` builds `santa_rigged.blend` (mesh, rig, wave animation).
- `export_web.py` exports `docs/santa.glb` and `docs/santa.usdz` from the .blend.
- `docs/index.html` is the WebAR viewer (uses `<model-viewer>`). GitHub Pages serves the `docs` folder.

## Updating the model

```
blender -b --factory-startup -P build_santa.py
blender -b santa_rigged.blend -P export_web.py
git add -A
git commit -m "Update model"
git push
```
