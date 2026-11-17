"""Explicit, read-only legacy export and atomic destination generation import.

Only this migration boundary reads legacy storage. Runtime services own their
new generation exclusively. Preview never instantiates a legacy store/engine.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import time
import uuid
from contextlib import closing
from pathlib import Path

WORLD = "astrbot_plugin_worldbook"
LIFE = "astrbot_plugin_dynamic_life_state"
MAX_BYTES = 128 * 1024 * 1024


def active_directory(root: Path) -> Path:
    pointer = root / "active.json"
    if not pointer.exists():
        return root / "initial"
    generation = json.loads(pointer.read_text("utf-8"))["generation"]
    if not re.fullmatch(r"import-[0-9a-f]{32}", generation):
        raise ValueError("Invalid active generation")
    target = root / generation
    if not target.is_dir():
        raise ValueError("Active generation is missing")
    return target


def _read_json(path: Path):
    if not path.exists():
        return None
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Source is too large")
    result = json.loads(path.read_text("utf-8-sig"))
    if not isinstance(result, dict):
        raise ValueError("Expected a JSON object")
    return result


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")


def _capture_json(path):
    if not path.exists():
        return None, None
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Source is too large")
    value = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value, raw


def _database_snapshot(path: Path):
    if not path.exists():
        return None, {}
    deadline = time.monotonic() + 10
    def progress(_status, _remaining, _total):
        if time.monotonic() > deadline:
            raise TimeoutError("Legacy database is busy; retry preview")
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)) as source:
        size = source.execute("PRAGMA page_count").fetchone()[0] * source.execute("PRAGMA page_size").fetchone()[0]
        if size > MAX_BYTES:
            raise ValueError("Legacy database is too large for panel import; use an offline backup")
        with closing(sqlite3.connect(":memory:")) as snapshot:
            source.backup(snapshot, pages=128, progress=progress, sleep=0.05)
            if snapshot.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Legacy database failed integrity check")
            version = snapshot.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
            if not version or version[0] != "1":
                raise ValueError("Unsupported narrative schema")
            counts = {}
            for table in ("lives", "scopes", "events", "diary", "commitments", "intents"):
                counts[table] = snapshot.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            return snapshot.serialize(), counts


def _validate_world(world):
    for key in ("books", "cards", "sessions"):
        if not isinstance(world.get(key, {}), dict):
            raise ValueError("Invalid world collection: " + key)
        if any(not isinstance(v, dict) for v in world.get(key, {}).values()):
            raise ValueError("Invalid world record: " + key)
    books, cards = world.get("books", {}), world.get("cards", {})
    if world.get("default_card_id") and world["default_card_id"] not in cards:
        raise ValueError("Default card refers to a missing character")
    for cid, card in cards.items():
        if card.get("id", cid) != cid:
            raise ValueError("Character key/id mismatch")
        if card.get("linked_book_id") and card["linked_book_id"] not in books:
            raise ValueError("Character refers to a missing book")
    for bid, book in books.items():
        if book.get("id", bid) != bid or not isinstance(book.get("entries", []), list):
            raise ValueError("Invalid worldbook identity/entries")
    for session in world.get("sessions", {}).values():
        if session.get("card_id") not in (None, "", "__none__") and session["card_id"] not in cards:
            raise ValueError("Session refers to a missing character")
        if not isinstance(session.get("book_ids", []), list) or any(b not in books for b in session.get("book_ids", [])):
            raise ValueError("Session refers to a missing book")
    if not isinstance(world.get("active_book_ids", []), list) or any(b not in books for b in world.get("active_book_ids", [])):
        raise ValueError("Active list refers to a missing book")


def capture(source_root: Path, config_root: Path | None = None):
    """Return owned bytes, never live SQLite/WAL files or executable inputs."""
    payloads, counts, settings = {}, {}, {}
    world, raw_world = _capture_json(source_root / WORLD / "worldbook_store.json")
    if world is not None:
        _validate_world(world)
        payloads["worldbook_store.json"] = raw_world
        counts.update({k: len(world.get(k, {})) for k in ("cards", "books", "sessions")})
        counts["entries"] = sum(len(b.get("entries", [])) for b in world.get("books", {}).values())
    legacy, raw_legacy = _capture_json(source_root / LIFE / "life_state.json")
    if legacy is not None:
        payloads["life_state.json"] = raw_legacy
    history = source_root / LIFE / "history"
    history_count = 0
    for path in sorted(history.glob("life_state_*.json")):
        if not re.fullmatch(r"life_state_\d{4}\.\d{2}\.\d{2}\.json", path.name):
            raise ValueError("Invalid legacy history filename")
        _, raw = _capture_json(path)
        payloads["history/" + path.name] = raw
        history_count += 1
    counts["legacy_history"] = history_count
    database, db_counts = _database_snapshot(source_root / LIFE / "narrative.sqlite3")
    if database is not None:
        payloads["narrative.sqlite3"] = database
        counts.update(db_counts)
    if config_root is not None:
        # Source configs are filtered against our schema; unknown credentials cannot migrate.
        supported = set(json.loads(Path(__file__).with_name("_conf_schema.json").read_text("utf-8")))
        for plugin in (WORLD, LIFE):
            cfg = _read_json(config_root / (plugin + "_config.json")) or {}
            settings.update({k: v for k, v in cfg.items() if k in supported})
    settings["runtime_enabled"] = False
    payloads["migration-settings.json"] = _json_bytes(settings)
    digest = hashlib.sha256()
    for name, data in sorted(payloads.items()):
        digest.update(name.encode()); digest.update(hashlib.sha256(data).digest())
    summary = {"schema_version": 1, "fingerprint": digest.hexdigest(), "counts": counts,
               "files": sorted(payloads), "has_data": len(payloads) > 1,
               "settings_keys": sorted(settings), "source_unchanged": True}
    return payloads, summary


def destination_has_data(root: Path):
    target = active_directory(root)
    database = target / "narrative.sqlite3"
    if database.exists():
        with closing(sqlite3.connect(database.resolve().as_uri()+"?mode=ro",uri=True)) as db:
            for table in ("world_maps", "world_environment", "world_weather_credentials", "world_scene_state"):
                if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone():
                    if db.execute("SELECT 1 FROM "+table+" LIMIT 1").fetchone():
                        return True
    world = _read_json(target / "worldbook_store.json") or {}
    if any(world.get(k) for k in ("cards", "books", "sessions")):
        return True
    if (target / "life_state.json").exists():
        legacy = _read_json(target / "life_state.json")
        if legacy:
            return True
    _, counts = _database_snapshot(target / "narrative.sqlite3")
    return any(counts.get(k) for k in ("events", "diary", "commitments", "intents"))


def preview(source_root: Path, destination: Path, config_root: Path | None = None):
    _, result = capture(source_root, config_root)
    result["conflicts"] = ["目标已有数据；首版迁移仅支持空目标，不自动覆盖或合并。"] if destination_has_data(destination) else []
    manifest = _read_json(active_directory(destination) / "import-manifest.json") or {}
    result["already_imported"] = manifest.get("fingerprint") == result["fingerprint"]
    return result


def prepare_import(source_root: Path, destination: Path, fingerprint: str, config_root: Path | None = None):
    payloads, result = capture(source_root, config_root)
    if fingerprint != result["fingerprint"]:
        raise ValueError("源数据在预览后发生变化，请重新预览")
    if not result["has_data"]:
        raise ValueError("没有可迁移的数据")
    manifest = _read_json(active_directory(destination) / "import-manifest.json") or {}
    if manifest.get("fingerprint") == fingerprint:
        return active_directory(destination), {**result, "already_imported": True}
    if destination_has_data(destination):
        raise ValueError("目标已有数据，拒绝覆盖；请导出后使用空目标")
    target = destination / ("import-" + uuid.uuid4().hex)
    target.mkdir(parents=True)
    for name, data in payloads.items():
        (target / name).parent.mkdir(parents=True, exist_ok=True)
        (target / name).write_bytes(data)
    (target / "import-manifest.json").write_bytes(_json_bytes(result))
    return target, result


def activate_generation(destination: Path, target: Path):
    if target.parent.resolve() != destination.resolve() or not re.fullmatch(r"import-[0-9a-f]{32}", target.name):
        raise ValueError("Invalid import destination")
    previous = active_directory(destination)
    pointer = destination / "active.json"
    temporary = destination / ("active-" + uuid.uuid4().hex + ".tmp")
    temporary.write_bytes(_json_bytes({"generation": target.name, "previous": previous.name}))
    os.replace(temporary, pointer)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="群间世界离线迁移；默认只读预览，写入前必须停止目标插件")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--config-root", type=Path)
    parser.add_argument("--apply-fingerprint", default="")
    args = parser.parse_args()
    if args.apply_fingerprint:
        target, result = prepare_import(args.source_root, args.destination, args.apply_fingerprint, args.config_root)
        activate_generation(args.destination, target)
    else:
        result = preview(args.source_root, args.destination, args.config_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
