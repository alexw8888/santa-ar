"""Run with blender -b --python-exit-code 1 -P tests/validate_santa05.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from edition_checks import check  # noqa: E402

check('santa05', 'Santa05_Cream_Bun_Bite', 193,
      holds=[('hand.L', 'bun'), ('hand.R', 'bun')],
      props=['bun', 'chunk'], translucent=False)
