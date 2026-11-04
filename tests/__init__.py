"""Project test suite."""
import sys
from pathlib import Path


SITE_ROOT = Path(__file__).resolve().parents[1] / "site"
if str(SITE_ROOT) not in sys.path:
    sys.path.insert(0, str(SITE_ROOT))
