import asyncio
import copy
import hashlib
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from astrbot_plugin_dynamics_world.main import Main
from astrbot_plugin_dynamics_world import migration
from astrbot_plugin_dynamics_world.world.core.character import CharacterCard
from astrbot_plugin_dynamics_world.world.core.models import WorldBook, WorldEntry
from astrbot_plugin_dynamics_world.life.core.narrative import NarrativeEngine

UMO = "qq:GroupMessage:one"
SCOPE = {"platform": "qq", "umo": UMO, "persona_id": "p", "instance_id": "p"}


class Config(dict):
    def save_config(self):
        self.saved = copy.deepcopy(dict(self))


async def make_plugin(tmp_path, monkeypatch, **overrides):
    monkeypatch.setattr("astrbot_plugin_dynamics_world.main.StarTools.get_data_dir", lambda: tmp_path)
    entries, routes = [], {}
    context = NS(get_all_stars=lambda: entries, register_web_api=lambda path, handler, methods, desc: routes.update({(path, tuple(methods)): handler}))
    cfg = Config(persona_id="p", narrative_sessions=[UMO], **overrides)
    plugin = Main(context, cfg)
    await plugin.initialize()
    return plugin, entries, routes


def seed(plugin):
    plugin.world.store.upsert_card(CharacterCard(id="card", name="角色", persona_id="p", system_prompt="Keep the character consistent."))
    plugin.world.store.set_default_card("card")
    book = WorldBook(id="world", name="海边小镇")
    book.entries = [WorldEntry(uid="cafe", keys=["咖啡"], content="咖啡馆位于海边。")]
    plugin.world.store.upsert_book(book)


@pytest.mark.asyncio
async def test_native_plugin_is_self_contained_and_cancels_loop(tmp_path, monkeypatch):
    plugin, entries, routes = await make_plugin(tmp_path, monkeypatch)
    assert plugin.world.store.list_cards() == []  # No forced bundled persona.
    assert plugin.life._worldbook() is plugin.world
    assert plugin.get_dynamics_capabilities()["enabled"] is False
    assert len(routes) == 36
    assert ('/astrbot_plugin_dynamics_world/visual', ('POST',)) in routes
    seed(plugin)
    with pytest.raises(RuntimeError):
        await plugin.get_character_context(SCOPE)
    plugin.config["runtime_enabled"] = True
    assert plugin.get_dynamics_capabilities()["ready"]
    character = await plugin.get_character_context(SCOPE, "咖啡")
    assert character["name"] == "角色" and "海边" in character["world_prompt"]
    assert (await plugin.get_snapshot(SCOPE))["managed"]
    entries.append(NS(name="astrbot_plugin_worldbook", activated=True, star_cls=object()))
    assert not plugin.runtime_allowed()
    with pytest.raises(RuntimeError):
        await plugin.get_snapshot(SCOPE)
    entries[0].activated = False
    assert plugin.runtime_allowed()
    await plugin.terminate()
    assert plugin.life._narrative_task.done()
    assert not plugin.get_dynamics_capabilities()["ready"]


@pytest.mark.asyncio
async def test_owned_request_does_not_double_inject(tmp_path, monkeypatch):
    plugin, _, _ = await make_plugin(tmp_path, monkeypatch, runtime_enabled=True)
    seed(plugin)
    event = NS(unified_msg_origin=UMO, get_extra=lambda key, default=None: True if key=="_narrative_managed_v1" else default)
    req = NS(system_prompt="original", extra_user_content_parts=[], contexts=[])
    await plugin.on_llm_request(event, req)
    assert req.system_prompt == "original" and req.extra_user_content_parts == []
    await plugin.terminate()


@pytest.mark.asyncio
async def test_explicit_unbind_and_scope_mismatch(tmp_path, monkeypatch):
    plugin, _, _ = await make_plugin(tmp_path, monkeypatch, runtime_enabled=True)
    seed(plugin)
    plugin.world.store.update_session(UMO, card_id="__none__")
    result = await plugin.get_character_context(SCOPE)
    assert result["disabled"]
    result = await plugin.get_character_context(SCOPE, NS(unified_msg_origin="qq:GroupMessage:other", message_str="hello"))
    assert not result["available"]
    await plugin.terminate()


def legacy_source(tmp_path):
    source = tmp_path / "legacy"
    source.mkdir()
    world = source / migration.WORLD
    world.mkdir()
    content = {"cards":{"c":{"id":"c","name":"角色","persona_id":"p","system_prompt":"设定"}},
               "books":{}, "sessions":{UMO:{"card_id":"c"}}, "default_card_id":"c"}
    (world / "worldbook_store.json").write_text(json.dumps(content),encoding="utf-8")
    return source


def test_preview_no_writes_source_preserved_and_idempotent(tmp_path):
    source = legacy_source(tmp_path)
    destination = tmp_path / "target"
    before = (source / migration.WORLD / "worldbook_store.json").read_bytes()
    result = migration.preview(source,destination)
    assert result["counts"]["cards"] == 1 and not destination.exists()
    target, _ = migration.prepare_import(source,destination,result["fingerprint"])
    migration.activate_generation(destination,target)
    assert (target / "worldbook_store.json").exists()
    assert (source / migration.WORLD / "worldbook_store.json").read_bytes()==before
    again, result = migration.prepare_import(source,destination,result["fingerprint"])
    assert again == target and result["already_imported"]


def test_stale_preview_and_existing_target_are_rejected(tmp_path):
    source=legacy_source(tmp_path);destination=tmp_path/"target"
    result=migration.preview(source,destination)
    path=source/migration.WORLD/"worldbook_store.json"
    data=json.loads(path.read_text());data["cards"]["c"]["name"]="changed";path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="变化"):
        migration.prepare_import(source,destination,result["fingerprint"])
    result=migration.preview(source,destination)
    (destination/"initial").mkdir(parents=True)
    (destination/"initial/worldbook_store.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="拒绝覆盖"):
        migration.prepare_import(source,destination,result["fingerprint"])


@pytest.mark.asyncio
async def test_sqlite_wal_snapshot_preserves_evidence(tmp_path):
    source=legacy_source(tmp_path);life=source/migration.LIFE;life.mkdir()
    engine=NarrativeEngine(life/"narrative.sqlite3", {"mode":"narrative","persona_id":"p","narrative_sessions":[UMO]},AsyncMock())
    event={"event_id":"e1","scope":SCOPE,"type":"chat.message","occurred_at":1000.0,"received_at":1000.0,"text":"约定","fact_kind":"user_claim"}
    await engine.ingest_events([event])
    destination=tmp_path/"new"
    result=migration.preview(source,destination)
    assert result["counts"]["events"] == 1
    target,_=migration.prepare_import(source,destination,result["fingerprint"])
    with sqlite3.connect(target/"narrative.sqlite3") as db:
        assert db.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        payload=json.loads(db.execute("SELECT payload FROM events WHERE event_id='e1'").fetchone()[0])
        assert payload["fact_kind"] == "user_claim" and payload["scope"]["umo"] == UMO
    await engine.close()


def test_invalid_generation_and_broken_bindings_rejected(tmp_path):
    root=tmp_path/"root";root.mkdir();(root/"active.json").write_text('{"generation":"../other"}')
    with pytest.raises(ValueError):migration.active_directory(root)
    source=legacy_source(tmp_path);path=source/migration.WORLD/"worldbook_store.json"
    path.write_text('{"cards":{},"books":{},"default_card_id":"missing"}')
    with pytest.raises(ValueError,match="missing"):
        migration.preview(source,tmp_path/"new")


@pytest.mark.asyncio
async def test_panel_import_switches_only_owned_data_and_config(tmp_path,monkeypatch):
    source=legacy_source(tmp_path)
    destination=source/"astrbot_plugin_dynamics_world"
    plugin,_,routes=await make_plugin(destination,monkeypatch)
    before=(source/migration.WORLD/"worldbook_store.json").read_bytes()
    result=migration.preview(source,destination)
    imported=await plugin.import_legacy(result["fingerprint"])
    assert imported["counts"]["cards"] == 1
    assert plugin.world.store.get_card("c").name == "角色"
    assert (source/migration.WORLD/"worldbook_store.json").read_bytes()==before
    assert (await plugin.apply_imported_settings())["runtime_enabled"] is False
    assert plugin.host_config.saved["runtime_enabled"] is False
    assert len(routes)==36
    await plugin.terminate()


@pytest.mark.asyncio
async def test_provider_response_discarded_after_character_edit(tmp_path,monkeypatch):
    plugin,_,_=await make_plugin(tmp_path,monkeypatch,runtime_enabled=True,narrative_provider_id="chosen")
    seed(plugin)
    async def chat(**kwargs):
        card=plugin.world.store.get_card("card");card.system_prompt="new setting";plugin.world.store.upsert_card(card)
        return NS(completion_text='{"no_change":true}')
    plugin.context.get_provider_by_id=lambda _:NS(text_chat=chat,provider_config={})
    with pytest.raises(RuntimeError,match="Character changed"):
        await plugin.life._narrative_model({"scope":SCOPE,"now":1000.0,"events":[]})
    await plugin.terminate()


@pytest.mark.asyncio
async def test_failed_import_restores_previous_generation(tmp_path, monkeypatch):
    source=legacy_source(tmp_path)
    destination=source/"astrbot_plugin_dynamics_world"
    plugin,_,_=await make_plugin(destination,monkeypatch)
    original=plugin._open_services
    calls=0
    async def fail_once():
        nonlocal calls
        calls+=1
        if calls==1:
            raise OSError("simulated load failure")
        await original()
    plugin._open_services=fail_once
    with pytest.raises(OSError,match="simulated"):
        await plugin.import_legacy(migration.preview(source,destination)["fingerprint"])
    assert plugin.data_dir==destination/"initial"
    assert plugin.world.store.list_cards()==[]
    assert plugin._ready and not plugin._migrating
    assert not (destination/"active.json").exists()
    await plugin.terminate()


@pytest.mark.asyncio
async def test_failed_config_reload_restores_saved_and_effective_config(tmp_path, monkeypatch):
    plugin,_,_=await make_plugin(tmp_path,monkeypatch)
    (plugin.data_dir/"migration-settings.json").write_text('{"persona_id":"other","runtime_enabled":false}')
    before=dict(plugin.host_config);original=plugin._open_services;calls=0
    async def fail_once():
        nonlocal calls
        calls+=1
        if calls==1:raise OSError("simulated settings failure")
        await original()
    plugin._open_services=fail_once
    with pytest.raises(OSError,match="simulated"):
        await plugin.apply_imported_settings()
    assert dict(plugin.host_config)==before
    assert plugin.host_config.saved==before
    assert plugin.config["persona_id"]=="p" and plugin._ready
    await plugin.terminate()


def test_legacy_history_bytes_and_config_filter_are_preserved(tmp_path):
    source=legacy_source(tmp_path);history=source/migration.LIFE/"history";history.mkdir(parents=True)
    raw=b'{"2026-11-10": {"schedule_summary": "a plan"}}\n'
    (history/"life_state_2026.11.10.json").write_bytes(raw)
    config=tmp_path/"config";config.mkdir()
    (config/(migration.LIFE+"_config.json")).write_text('{"persona_id":"p","unknown_api_key":"must-not-copy"}')
    destination=tmp_path/"dest"
    result=migration.preview(source,destination,config)
    target,_=migration.prepare_import(source,destination,result["fingerprint"],config)
    assert (target/"history/life_state_2026.11.10.json").read_bytes()==raw
    settings=json.loads((target/"migration-settings.json").read_text())
    assert "unknown_api_key" not in settings and settings["runtime_enabled"] is False


@pytest.mark.asyncio
async def test_native_registry_routes_both_roles_to_the_same_current_instance(tmp_path, monkeypatch):
    from astrbot_plugin_chat_dynamics.core.integrations.registry import IntegrationRegistry
    plugin,entries,_=await make_plugin(tmp_path,monkeypatch,runtime_enabled=True)
    seed(plugin)
    entries.append(NS(name="astrbot_plugin_dynamics_world",star_cls=plugin,activated=True))
    registry=IntegrationRegistry(plugin.context)
    world=registry.narrative_provider("worldbook")
    life=registry.narrative_provider("dynamic_life_state")
    assert world is plugin and life is plugin
    assert (await world.get_character_context(SCOPE))["persona_id"]=="p"
    assert (await life.get_snapshot(SCOPE))["managed"]
    entries[0].activated=False
    assert registry.narrative_provider("worldbook") is None
    await registry.close();await plugin.terminate()


@pytest.mark.asyncio
async def test_import_refuses_a_source_that_is_still_running(tmp_path,monkeypatch):
    source=legacy_source(tmp_path)
    plugin,entries,_=await make_plugin(source/"astrbot_plugin_dynamics_world",monkeypatch)
    entries.append(NS(name="astrbot_plugin_worldbook",activated=True,star_cls=object()))
    report=migration.preview(source,plugin.data_root)
    assert report["has_data"]
    with pytest.raises(ValueError,match="先停用"):
        await plugin.import_legacy(report["fingerprint"])
    assert not (plugin.data_root/"active.json").exists()
    await plugin.terminate()


@pytest.mark.asyncio
async def test_standalone_tool_does_not_leak_member_material(tmp_path,monkeypatch):
    plugin,_,_=await make_plugin(tmp_path,monkeypatch,runtime_enabled=True)
    seed(plugin)
    plugin.get_snapshot=AsyncMock(return_value={"managed":True,"activity":"读书","availability":"available",
        "summary":"other-member-secret","commitments":[{"description":"private-promise"}]})
    result=await plugin.world_state_tool(NS(unified_msg_origin=UMO))
    assert "当前活动未确认" in result and "secret" not in result and "promise" not in result
    plugin.get_snapshot.assert_not_awaited()  # The tool reads confirmed public facts directly.
    await plugin.terminate()
