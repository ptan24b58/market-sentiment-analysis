"""Pytest configuration for the persona sentiment pipeline test suite."""

import sys
from pathlib import Path

# Ensure project root is on sys.path so `src.*` imports resolve correctly.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
