"""Run with blender -b --python-exit-code 1 -P tests/validate_santa03.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from edition_checks import check  # noqa: E402

check('santa03', 'Santa03_Coffee_and_Flowers', 145,
      holds=[('hand.L', 'mug'), ('hand.R', 'bouquet')],
      props=['mug', 'steam', 'bouquet'], translucent=True)
