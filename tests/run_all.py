"""Dependency-free test runner:  python tests/run_all.py   (pytest also works)."""
import importlib.util
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
failed = 0
for path in sorted(HERE.glob("test_*.py")):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = mod
    spec.loader.exec_module(mod)
    for name in sorted(n for n in dir(mod) if n.startswith("test_")):
        t = time.time()
        try:
            getattr(mod, name)()
            print(f"PASS  {path.stem}::{name}  ({time.time() - t:.1f}s)")
        except Exception:
            failed += 1
            print(f"FAIL  {path.stem}::{name}")
            traceback.print_exc()
print("\n" + ("ALL TESTS PASSED" if not failed else f"{failed} FAILED"))
sys.exit(1 if failed else 0)
