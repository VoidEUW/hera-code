"""Puts the repository root on ``sys.path`` so ``tests/`` can import ``tools/``.

``tools/`` is not a workspace member and is never installed — it is repository scripting, and the
meta-tests in ``tests/`` are what exercise it. Without this, ``from tools.vendor_digest import
tree_digest`` works when pytest happens to be run from the root and fails when it is not.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
