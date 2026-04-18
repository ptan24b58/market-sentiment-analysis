"""Top-level pytest configuration.

Adds the repository root to ``sys.path`` so that ``import src.*`` works from
any test file without an editable install. Also enables structured logging at
DEBUG level for test runs.
"""

import logging
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
