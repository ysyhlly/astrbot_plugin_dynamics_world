"""Materialize host schema defaults for service and test consistency."""
import json
from pathlib import Path

def defaults():
    schema = json.loads(Path(__file__).with_name("_conf_schema.json").read_text("utf-8"))
    def unpack(items):
        return {key: unpack(value["items"]) if value.get("type") == "object" else value.get("default") for key, value in items.items()}
    return unpack(schema)
