"""Batch 4 regression tests: packaging hygiene, CI unpinning, timezone & alias cleanup."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import zipfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def _load_build_release():
    spec = importlib.util.spec_from_file_location("dw_build_release_b4", ROOT / "build_release.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_build_release_single_top_level_dir_and_hygiene(tmp_path):
    br = _load_build_release()
    out_zip = tmp_path / "install.zip"
    res = br.build(ROOT, out_zip)

    assert res["top_level_dir"] == "astrbot_plugin_dynamics_world"
    assert res["bytes"] < 3_500_000, f"Expected trimmed archive under 3.5 MB, got {res['bytes']} bytes"
    assert out_zip.is_file()

    prefix = "astrbot_plugin_dynamics_world/"
    banned_dirs = {".git", ".github", "src", "tests", "node_modules", "__pycache__", ".pytest_cache"}
    banned_files = {
        "build_release.py",
        "package.json",
        "package-lock.json",
        ".gitignore",
        ".gitattributes",
        "requirements-dev.txt",
        ".env",
    }

    with zipfile.ZipFile(out_zip) as zf:
        names = zf.namelist()

    assert names, "Release archive must not be empty"
    for name in names:
        assert name.startswith(prefix), f"Archive entry missing top-level dir: {name}"
        rel = name[len(prefix) :]
        parts = rel.split("/")
        assert not (set(parts) & banned_dirs), f"Banned directory leaked into zip: {name}"
        assert parts[-1] not in banned_files, f"Banned dev file leaked into zip: {name}"
        assert not rel.endswith((".sqlite3", ".db", ".pyc", ".bak", ".zip")), f"Artifact leaked: {name}"

    name_set = set(names)
    # Core runtime assets must be present.
    for required in (
        prefix + "main.py",
        prefix + "metadata.yaml",
        prefix + "_conf_schema.json",
        prefix + "life/core/narrative_ddl.py",
        prefix + "pages/world/index.html",
        prefix + "pages/world/cabin3d.min.js",
        prefix + ".astrbot-plugin/i18n/zh-CN.json",
        prefix + "vendor/azgaar/index.html",
        prefix + "vendor/azgaar/index-CH0Rm5id.js",
        prefix + "vendor/azgaar/app-BvZbQ29j.js",
        prefix + "vendor/azgaar/en-BpPoOois.js",
        prefix + "vendor/azgaar/zh-r7nepuD_.js",
        prefix + "vendor/azgaar/images/pattern1.png",
    ):
        assert required in name_set, f"Missing required runtime asset: {required}"

    # Unused Azgaar UI/PWA/style-preset assets must be excluded.
    for forbidden_prefix in (
        prefix + "vendor/azgaar/images/icons/",
        prefix + "vendor/azgaar/images/style-presets/",
        prefix + "vendor/azgaar/styles/",
        prefix + "vendor/azgaar/heightmaps/",
    ):
        assert not any(n.startswith(forbidden_prefix) for n in names), (
            f"Unused Azgaar directory leaked: {forbidden_prefix}"
        )
    for forbidden_exact in (
        prefix + "vendor/azgaar/images/waves.png",
        prefix + "vendor/azgaar/images/preview.png",
        prefix + "vendor/azgaar/images/tour-button-icon.png",
        prefix + "vendor/azgaar/images/Discord.png",
        prefix + "vendor/azgaar/sw.js",
    ):
        assert forbidden_exact not in name_set, f"Unused Azgaar asset leaked: {forbidden_exact}"
    assert not any(
        n.startswith(prefix + "vendor/azgaar/icons-goods-") for n in names
    ), "Unused Azgaar icons-goods chunk leaked"


def test_ci_workflow_unpinned_and_has_hygiene_and_node_gates():
    ci_text = (ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8")
    assert "2a39bcf5525fa7e03908e9249f3aaeab1e87acd4" not in ci_text
    assert "ysyhlly/astrbot_plugin_chat_dynamics" in ci_text
    assert "node --test tests/test_avatar_state.mjs" in ci_text
    assert "build_release.py" in ci_text
    assert "astrbot_plugin_dynamics_world/" in ci_text


def test_timezone_prompts_and_frontend_format_ts():
    prompt_text = (ROOT / "life" / "core" / "narrative_prompt.py").read_text("utf-8")
    assert "北京时间" not in prompt_text
    assert "timezone" in prompt_text

    injector_text = (ROOT / "life" / "core" / "injector.py").read_text("utf-8")
    assert "北京时间" not in injector_text

    picker_text = (ROOT / "pages" / "world" / "cabin-style-picker.js").read_text("utf-8")
    assert "Asia/Shanghai" not in picker_text
    assert "getSeriesTimezone" in picker_text

    # Runtime JS verification of pages/world/api.js timezone handling.
    api_url = (ROOT / "pages" / "world" / "api.js").as_uri()
    script = f"""
globalThis.MutationObserver = class {{ observe() {{}} disconnect() {{}} }};
globalThis.window = {{
  addEventListener() {{}},
  dispatchEvent() {{}},
  localStorage: {{ getItem() {{ return null; }}, setItem() {{}} }},
}};
globalThis.localStorage = globalThis.window.localStorage;
globalThis.location = {{ search: '' }};
globalThis.document = {{
  readyState: 'complete',
  body: {{}},
  documentElement: {{ lang: 'zh-CN', dataset: {{}}, setAttribute() {{}} }},
  querySelectorAll() {{ return []; }},
  getElementById() {{ return null; }},
  addEventListener() {{}},
}};
const api = await import({json.dumps(api_url)});
const ts = 1763683200; // 2025-11-21T00:00:00Z
const defStr = api.formatTs(ts);
api.setSeriesTimezone('UTC');
const utcStr = api.formatTs(ts);
const tokyoStr = api.formatTs(ts, 'Asia/Tokyo');
const tzNow = api.getSeriesTimezone();
api.setSeriesTimezone('Invalid/Zone');
const tzAfterInvalid = api.getSeriesTimezone();
console.log(JSON.stringify({{ defStr, utcStr, tokyoStr, tzNow, tzAfterInvalid }}));
process.exit(0);
"""
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    out = json.loads(proc.stdout.strip())
    assert "08:00" in out["defStr"]
    assert "00:00" in out["utcStr"]
    assert "09:00" in out["tokyoStr"]
    assert out["tzNow"] == "UTC"
    assert out["tzAfterInvalid"] == "UTC"


def test_resident_runtime_aliases_are_card_driven_not_hardcoded():
    src = (ROOT / "resident_runtime.py").read_text("utf-8")
    for fandom_name in ("樱羽艾玛", "二阶堂希罗", "月代雪"):
        assert fandom_name not in src, f"Hardcoded fandom alias leaked: {fandom_name}"

    from astrbot_plugin_dynamics_world.resident_runtime import (
        ResidentRunner,
        _peer_name_candidates,
    )

    cands = _peer_name_candidates(
        {"id": "r2", "name": "Alice·Vance"},
        {"aliases": ["小爱", "Ali"], "short_name": "艾莉"},
    )
    assert "Alice·Vance" in cands
    assert "Alice" in cands
    assert "Vance" in cands
    assert "小爱" in cands
    assert "Ali" in cands
    assert "艾莉" in cands

    # End-to-end context() check with stubbed engine/causal/spatial/scenes.
    cards = {
        "c1": {
            "name": "林舟",
            "description": "林舟常和旧友小雨一起在港口散步，也认识远方的晴空。",
            "personality": "沉稳。",
        },
        "c2": {"name": "沈微雨", "aliases": ["小雨"]},
        "c3": {"name": "晴空"},
        "c4": {"name": "陌生旅人"},
    }
    doc = {
        "residents": {
            "r1": {"id": "r1", "card_id": "c1", "name": "林舟", "enabled": True, "place_id": "p1", "revision": 1, "knowledge": []},
            "r2": {"id": "r2", "card_id": "c2", "name": "沈微雨", "enabled": True, "place_id": "p1", "revision": 1, "knowledge": []},
            "r3": {"id": "r3", "card_id": "c3", "name": "晴空", "enabled": True, "place_id": "p1", "revision": 1, "knowledge": []},
            "r4": {"id": "r4", "card_id": "c4", "name": "陌生旅人", "enabled": True, "place_id": "p1", "revision": 1, "knowledge": []},
        },
        "invitations": {},
    }
    causal = SimpleNamespace(
        load=lambda db, scope: (1, doc),
        card_resolver=lambda cid: cards.get(cid),
        actor_state=lambda db, scope, d, aid, now: {"place_id": "p2", "asleep": False, "journey": None},
        public_resident=lambda a: {"id": a["id"], "place_id": a.get("place_id")},
    )
    spatial = SimpleNamespace(document=lambda db, ident: {"places": [{"id": "p1", "name": "港口"}]})
    scenes = SimpleNamespace(load=lambda db, scope: (0, None, {"room_known": False, "room_id": None}))
    engine = SimpleNamespace(causal=causal, spatial=spatial, scenes=scenes, config={"mode": "narrative"})
    service = SimpleNamespace(is_active=lambda: True, context=None, narrative=engine)
    rt = ResidentRunner.__new__(ResidentRunner)
    rt.service = service
    rt.engine = engine

    public, _commit_ctx = rt.context(
        db=SimpleNamespace(execute=lambda *a, **k: []),
        scope={"persona_id": "p", "umo": "u"},
        actor_id="r1",
        now=1_760_000_000.0,
    )
    by_id = {p["id"]: p["label"] for p in public["public_peers"]}
    assert by_id["r2"] == "沈微雨"
    assert by_id["r3"] == "晴空"
    assert by_id["r4"] == "尚未获知姓名的居民"
