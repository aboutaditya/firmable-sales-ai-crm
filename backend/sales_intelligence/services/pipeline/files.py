from __future__ import annotations

import json
import os
from pathlib import Path


def atomic_json(path: Path, payload: dict) -> None:
    """Atomically write a JSON payload to a file (write temp, then replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)