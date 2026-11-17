"""Optional content profiles; generic operation has no franchise-specific rules."""

import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=2)
def preset(key):
    if key not in {"generic", "manosaba"}:
        raise ValueError("未知世界预设")
    return json.loads(
        (Path(__file__).parent / "presets" / (key + ".json")).read_text("utf-8")
    )


def catalog(starters=False):
    fields = (
        ("id", "name", "description", "character")
        if starters
        else ("id", "name", "description")
    )
    return [{k: preset(key)[k] for k in fields} for key in ("generic", "manosaba")]


def selected(profile, config):
    value = profile.get("style_preset", config.get("visual_style_default", "generic"))
    return value if value in {"generic", "manosaba"} else "generic"
