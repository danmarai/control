"""Read ~/.openclaw/MANIFEST.json for live system state."""

import json
import os
import time

MANIFEST_PATH = os.path.expanduser("~/.openclaw/MANIFEST.json")


def read_manifest():
    """Return (data_dict, staleness_minutes) or (None, None) if missing/corrupt."""
    if not os.path.exists(MANIFEST_PATH):
        return None, None
    try:
        mtime = os.path.getmtime(MANIFEST_PATH)
        age_min = (time.time() - mtime) / 60.0
        with open(MANIFEST_PATH, "r") as f:
            data = json.load(f)
        return data, round(age_min, 1)
    except (json.JSONDecodeError, OSError):
        return None, None
