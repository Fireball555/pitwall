"""Make the repo root importable (as `pitwall`) under pytest without an editable install."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
