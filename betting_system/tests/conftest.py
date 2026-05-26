import sys
from pathlib import Path

# Ensure repo root is on sys.path for imports under pytest importlib modes.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

