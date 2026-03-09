"""
pytest configuration for pi-app UI tests.
- Runs pygame in headless/dummy mode (no physical display required).
- Stubs out hardware modules unavailable on a dev machine (serial port).
- Adds pi-app/ and shared/ to sys.path.
"""
import os
import sys
from unittest.mock import MagicMock

# Headless SDL — must be set before pygame is imported
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

# Path setup
_tests_dir = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(_tests_dir, ".."))            # pi-app/
sys.path.insert(0, os.path.join(_tests_dir, "..", "..", "shared"))  # shared/

# Stub hardware modules that are unavailable outside the Pi
_HARDWARE_STUBS = [
    "serial",
]
for _mod in _HARDWARE_STUBS:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()
