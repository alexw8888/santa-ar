"""Run with blender -b --python-exit-code 1 -P tests/validate_santa06.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from edition_checks import check  # noqa: E402

check('santa06', 'Santa06_Noodle_Aroma', 121,
      holds=[('hand.L', 'bowl'), ('hand.R', 'bowl')],
      props=['bowl', 'steam', 'duck'], translucent=True)
