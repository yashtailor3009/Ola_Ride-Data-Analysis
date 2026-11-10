"""Shared fixtures (pytest) - also importable by the plain runner."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
