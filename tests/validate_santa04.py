"""Run with blender -b --python-exit-code 1 -P tests/validate_santa04.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from edition_checks import check  # noqa: E402

check('santa04', 'Santa04_Tree_Glow', 121,
      holds=[('hand.L', 'tree'), ('hand.R', 'tree')],
      props=['tree'], translucent=False)
