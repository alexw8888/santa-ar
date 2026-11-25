# Santa 03: Bouquet Café's suggested changes (2026-11-24)

Source: the café's "Santa at Bouquet Café" mock-up, their logo file and two photos of their wrapped bouquet.

## Decisions (confirmed with Alex)

- The mug is held steady at the chest with steam (no aroma lift).
- The bouquet offer pauses for about 4 seconds; the loop is 8 seconds (193 frames).

## Changes

1. **Mug logo.** Put the café's real logo image on the mug as a printed decal (a texture on a thin patch that wraps the mug), replacing the typeset "BOUQUET CAFE" and the drawn lotus. The logo's grey background is recoloured to the mug's glaze so no edge shows.
   - `santa_kit.py`: `surface` takes optional per-point UVs; `attach` writes them. Add a `decal` helper.
   - Save the logo as `assets/bouquet-cafe-logo.jpg`.
2. **Real bouquet.** Replace the mixed bouquet (tulips, daisies, asters, lavender) with the café's wrapped bouquet: red roses, pink spray roses, round eucalyptus leaves and white limonium sprays in a cone of dark burgundy outer and bright red inner paper, tied with a sheer white and burgundy satin bow.
   - Save the two bouquet photos and the mock-up in `photos/`.
3. **Offer.** Swap hands as in the mock-up: mug in Santa's right glove, bouquet in his left. Loop: rest with the bouquet out at his side (mock-up pose), raise it to chest height and tilt it toward a guest standing on his left, hold still ~4 s while he looks at the camera, lower it back.
4. **Sack.** Move the flower sack behind his right side (image left) so a guest can stand on his left. Its flowers become red and pink roses with eucalyptus to match.
5. **Name.** Write "Bouquet Café" with the accent on `docs/santa03.html`, `docs/preview.html` and the README. Bump the asset version (`?v=bouquet-4`).

## Build and check

- Blender here is 5.0 (the repo's `.blend` files were saved by 5.3), so rebuild `santa_base.blend` locally with 5.0 first, build Santa 03 from it, then restore the committed base.
- `build_santa03.py -- previews`, `export_santa.py -- santa03`, `tests/validate_santa03.py` (holds become `hand.R`/mug and `hand.L`/bouquet).
- Look at the previews against the mock-up; check GLB/USDZ sizes stay well under the limit.
- Update the README's Santa 03 rows and size table.
