"""Real HTTP handlers + Chromium, with an isolated host context and local data."""

import asyncio
import json
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace as NS
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from playwright.async_api import async_playwright

from astrbot_plugin_dynamics_world.main import Main
from astrbot_plugin_dynamics_world.world.core.character import CharacterCard
from astrbot_plugin_dynamics_world.world.core.models import WorldBook, WorldEntry
from astrbot_plugin_dynamics_world.world.core import web_api as wb_api


async def run():
    output = Path("/tmp/world-visual-editor-browser")
    output.mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="world-browser-"))
    routes, errors = {}, []
    context = NS(
        get_all_stars=lambda: [],
        register_web_api=lambda path, handler, methods, desc: routes.update(
            {(path.rsplit("/", 1)[-1], methods[0]): handler}
        ),
    )
    scope = {
        "platform": "qq",
        "umo": "qq:GroupMessage:demo",
        "persona_id": "demo",
        "instance_id": "demo",
    }
    with patch(
        "astrbot_plugin_dynamics_world.main.StarTools.get_data_dir", return_value=root
    ):
        plugin = Main(
            context, {"persona_id": "demo", "narrative_sessions": [scope["umo"]]}
        )
    await plugin.initialize()
    met_fails = [True]

    async def weather_fetch(kind, params):
        if kind == "search":
            return {
                "results": [
                    {
                        "name": "Berlin",
                        "admin1": "Berlin",
                        "country": "Deutschland",
                        "latitude": 52.52,
                        "longitude": 13.405,
                        "timezone": "Europe/Berlin",
                    }
                ]
            }
        stamp = plugin.life.narrative.clock()
        if kind == "met":
            from datetime import datetime, timezone
            from astrbot_plugin_dynamics_world.weather import response_error

            if met_fails[0]:
                raise response_error(429, {}, "3600")

            def iso(value):
                return datetime.fromtimestamp(value, timezone.utc).isoformat()

            return {
                "properties": {
                    "meta": {"updated_at": iso(stamp)},
                    "timeseries": [
                        {
                            "time": iso(stamp // 3600 * 3600 + i * 3600),
                            "data": {
                                "instant": {
                                    "details": {
                                        "air_temperature": 16 + i / 10,
                                        "wind_speed": 3,
                                    }
                                },
                                "next_1_hours": {
                                    "summary": {"symbol_code": "partlycloudy_day"},
                                    "details": {"precipitation_amount": 0},
                                },
                            },
                        }
                        for i in range(49)
                    ],
                }
            }
        return {
            "timezone": "Europe/Berlin",
            "current": {
                "time": stamp,
                "temperature_2m": 9,
                "apparent_temperature": 7,
                "precipitation": 0.3,
                "wind_speed_10m": 8,
                "weather_code": 61,
                "is_day": 0,
            },
            "hourly": {
                "time": [stamp + 3600 * i for i in range(1, 25)],
                "temperature_2m": [8] * 24,
                "weather_code": [61] * 24,
                "precipitation_probability": [75] * 24,
                "is_day": [0] * 24,
            },
            "daily": {
                "time": [stamp],
                "sunrise": [stamp - 3600],
                "sunset": [stamp + 3600],
            },
        }

    plugin.life.narrative.environment.fetch = weather_fetch
    card = CharacterCard(
        id="demo",
        name="小夏",
        persona_id="demo",
        system_prompt="在海边小镇生活，喜欢读书和写作。",
    )
    book = WorldBook(id="town", name="海边小镇", description="咖啡馆、书店与沿海步道")
    book.entries = [
        WorldEntry(
            uid="cafe",
            name="街角咖啡馆",
            content="窗边可以看见海。",
            keys=["咖啡"],
            scenarios=["咖啡馆"],
        )
    ]
    plugin.world.store.upsert_book(book)
    plugin.world.store.upsert_card(card)
    plugin.world.store.set_default_card(card.id)
    plugin.world.store.update_session(scope["umo"], card_id=card.id, scenario="咖啡馆")
    now = time.time()

    async def model(request):
        return {
            "state": {
                "activity_code": "reading",
                "availability": "available",
                "valid_until": request["now"] + 3600,
            },
            "diary": [
                {
                    "text": "午后在窗边读了一会儿书，雨停后出去散步。",
                    "fact_kind": "fiction",
                    "source_ids": [request["events"][0]["event_id"]],
                }
            ],
        }

    plugin.life.narrative.model = model
    global_scope = dict(scope, umo="", platform="")
    await plugin.life.narrative.advance(
        [
            {
                "event_id": "tick",
                "type": "life.tick",
                "scope": global_scope,
                "occurred_at": now,
                "received_at": now,
                "fact_kind": "fiction",
                "text": "日常推进",
            }
        ]
    )
    await plugin.life.correct_state(
        scope,
        {
            "activity": "在街角咖啡馆读书",
            "availability": "available",
            "summary": "雨刚停，准备读完这一章再去散步。",
        },
    )
    from test_spatial import document
    from astrbot_plugin_dynamics_world.visual_assets import VisualAssetLibrary
    from PIL import Image, ImageDraw
    import base64
    import io

    def picture(color):
        stream = io.BytesIO()
        im = Image.new("RGB", (960, 540), color)
        draw = ImageDraw.Draw(im)
        draw.rectangle((60, 200, 360, 450), fill="white")
        draw.rectangle((560, 300, 880, 470), fill="gray")
        im.save(stream, format="PNG")
        return stream.getvalue()

    engine = plugin.life.narrative
    doc = document()
    doc["image"] = (
        "data:image/png;base64," + base64.b64encode(picture("#cad9cd")).decode()
    )
    engine.spatial.install(scope, doc)
    engine.spatial.admin_action(
        scope,
        {"kind": "locate", "target_id": "a", "map_revision": 1, "position_revision": 1},
    )
    engine.scenes.bootstrap(scope, {"expected_revision": 0, "place_id": "a"})
    with engine._db() as db:
        scene = engine.scenes.snapshot(db, scope, engine.clock())
    room = next(r["id"] for r in scene["rooms"] if r["name"] == "房间")
    book = next(i["id"] for i in scene["items"] if i["kind"] == "book")
    engine.scenes.administer(
        scope,
        {
            "action": "start",
            "expected_revision": scene["revision"],
            "steps": [{"kind": "enter", "target_id": room}],
        },
    )
    with engine._db() as db:
        engine.scenes.settle(db, scope, engine.clock() + 60)
    profiles = engine.visuals.profiles
    library = VisualAssetLibrary(profiles)
    style = library.upload(
        {
            "role": "style",
            "label": "旧画风参考",
            "image_base64": base64.b64encode(picture("#a59ac4")).decode(),
        }
    )
    layout = library.upload(
        {
            "role": "layout",
            "label": "旧房间底图",
            "image_base64": base64.b64encode(picture("#c9b39c")).decode(),
        }
    )
    profiles.configure(
        scope,
        {"action": "style", "expected_revision": 0, "asset_ids": [style["asset_id"]]},
    )
    profiles.configure(
        scope,
        {
            "action": "room",
            "expected_revision": 1,
            "target_id": room,
            "asset_id": layout["asset_id"],
            "layout": "床在左，书桌在右",
        },
    )
    profiles.configure(
        scope,
        {
            "action": "item",
            "expected_revision": 2,
            "target_id": book,
            "appearance": "紫色硬封书",
            "home_room_id": room,
            "placement": "书桌左侧",
        },
    )

    def saved():
        with engine._db() as db:
            return profiles.admin(db, scope)

    with engine._db() as db:
        original_items = json.loads(
            db.execute("SELECT state FROM world_scene_state").fetchone()[0]
        )["items"]
    # Serialize response transport only; all endpoint implementations stay real.
    wb_api.json_response = lambda data=None, **kwargs: data
    lock = asyncio.Lock()
    loop = asyncio.get_running_loop()

    async def invoke(endpoint, method, query, body):
        async with lock:
            wb_api.request = NS(query=query, json=lambda **kwargs: body, headers={})
            return await routes[(endpoint, method)]()

    pages = Path(__file__).parents[1] / "pages/world"
    bridge = """<script>window.AstrBotPluginPage={ready:async()=>{},apiGet:async(e,q={})=>fetch('/api/'+e+'?'+new URLSearchParams(q)).then(r=>r.json()),apiPost:async(e,b)=>fetch('/api/'+e,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(b)}).then(r=>r.json())};</script>"""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.serve("GET")

        def do_POST(self):
            self.serve("POST")

        def serve(self, method):
            parsed = urlparse(self.path)
            if parsed.path.startswith("/api/"):
                body = json.loads(
                    self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}"
                )
                result = asyncio.run_coroutine_threadsafe(
                    invoke(
                        parsed.path.split("/")[-1],
                        method,
                        {k: v[0] for k, v in parse_qs(parsed.query).items()},
                        body,
                    ),
                    loop,
                ).result(15)
                data = (
                    result.body
                    if hasattr(result, "body")
                    else json.dumps(result, ensure_ascii=False).encode()
                )
                mime = "application/json"
            else:
                filename = parsed.path.lstrip("/") or "index.html"
                if (
                    not (pages / filename).resolve().is_relative_to(pages.resolve())
                    or not (pages / filename).is_file()
                ):
                    self.send_error(404)
                    return
                data = (pages / filename).read_bytes()
                mime = {
                    ".js": "text/javascript",
                    ".css": "text/css",
                    ".html": "text/html",
                }.get(Path(filename).suffix, "text/plain")
                if filename == "index.html":
                    data = data.replace(b"</head>", (bridge + "</head>").encode())
            self.send_response(200)
            self.send_header("Content-Type", mime + "; charset=utf-8")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = await browser.new_page(viewport={"width": 1440, "height": 1000})
            page.on("pageerror", lambda e: errors.append(str(e)))
            await page.goto(f"http://127.0.0.1:{server.server_port}/")
            await page.wait_for_function(
                "document.getElementById('dwOverviewLife').textContent.includes('小夏')"
            )
            await page.locator("#tab-map").click()
            await page.wait_for_function(
                "document.querySelector('#visLayout').value==='床在左，书桌在右'"
            )
            await page.locator("#sceneVisual").evaluate(
                '(n)=>n.closest("details").open=true'
            )
            await page.wait_for_function(
                "document.querySelector('#visRoomPreview img')?.naturalWidth>0 && document.querySelector('#visStylePreview1 img')?.naturalWidth>0"
            )
            await page.locator("#visRoomPreview button").click()
            assert await page.locator("#visImageDialog").is_visible()
            await page.keyboard.press("Escape")
            assert not await page.locator("#visImageDialog").is_visible()
            await page.locator("#visLayout").fill("床在左，书桌在右，窗边留出通道")
            await page.locator("#visAppearance").fill("紫色硬封书，金色边框")
            await page.evaluate(
                "document.dispatchEvent(new CustomEvent('world-view',{detail:'map'}))"
            )
            await page.wait_for_timeout(700)
            assert (
                await page.locator("#visLayout").input_value()
                == "床在左，书桌在右，窗边留出通道"
            )
            assert await page.locator("#visRoom").is_disabled()
            await page.locator("#visSaveRoom").click()
            await page.wait_for_function(
                "document.getElementById('visStatus').textContent.includes('其余草稿')"
            )
            assert (
                await page.locator("#visAppearance").input_value()
                == "紫色硬封书，金色边框"
            )
            await page.locator("#visSaveItem").click()
            await page.wait_for_function(
                "document.getElementById('visStatus').textContent.includes('新设定')"
            )
            assert (
                saved()["profile"]["items"][book]["appearance"]
                == "紫色硬封书，金色边框"
            )
            await page.locator("#visLayout").fill("不能丢失的草稿")
            profiles.configure(
                scope,
                {
                    "action": "style",
                    "expected_revision": saved()["revision"],
                    "asset_ids": [],
                },
            )
            await page.evaluate(
                "document.dispatchEvent(new CustomEvent('world-view',{detail:'map'}))"
            )
            await page.wait_for_function(
                "document.getElementById('visStatus').textContent.includes('其他页面')"
            )
            await page.locator("#visSaveRoom").click()
            await page.wait_for_function(
                "document.getElementById('visStatus').textContent.includes('未覆盖')"
            )
            assert await page.locator("#visLayout").input_value() == "不能丢失的草稿"
            assert saved()["profile"]["rooms"][room]["layout"] != "不能丢失的草稿"
            await page.locator("#visReload").click()
            await page.wait_for_function(
                "document.getElementById('visStatus').textContent.includes('已重新载入')"
            )
            await page.locator("#visUploadRole").select_option("layout")
            await page.locator("#visUploadLabel").fill("新房间底图")
            await page.locator("#visFile").set_input_files(
                {
                    "name": "new-layout.png",
                    "mimeType": "image/png",
                    "buffer": picture("#7da59c"),
                }
            )
            await page.locator("#visUpload").click()
            await page.wait_for_function(
                "document.getElementById('visStatus').textContent.includes('已上传')"
            )
            new_layout = await page.locator("#visRoomAsset").input_value()
            assert saved()["profile"]["rooms"][room]["asset_id"] == layout["asset_id"]
            assert await page.locator("#visRoomAsset option").count() == 3
            await page.locator("#visSaveRoom").click()
            await page.wait_for_function(
                "document.getElementById('visStatus').textContent.includes('新设定')"
            )
            assert saved()["profile"]["rooms"][room]["asset_id"] == new_layout
            await page.locator("#visUploadRole").select_option("style")
            await page.locator("#visUploadLabel").fill("新画风参考")
            await page.locator("#visFile").set_input_files(
                {
                    "name": "new-style.webp",
                    "mimeType": "image/png",
                    "buffer": picture("#84a8c4"),
                }
            )
            await page.locator("#visUpload").click()
            await page.wait_for_function(
                "document.getElementById('visStatus').textContent.includes('已上传')"
            )
            await page.locator("#visSaveStyle").click()
            await page.wait_for_function(
                "document.getElementById('visStatus').textContent.includes('新设定')"
            )
            assert len(profiles.assets()) == 4
            with engine._db() as db:
                snap = engine._snapshot(db, scope, engine.clock())
                assert (
                    json.loads(
                        db.execute("SELECT state FROM world_scene_state").fetchone()[0]
                    )["items"]
                    == original_items
                )
            refs = snap["visual_sharing"]["references_default"]
            assert len(refs) == 2 and new_layout in refs[0]
            from astrbot_plugin_visual_media.tl.llm_tools import (
                _resolve_tool_references,
            )

            resolved, error = await _resolve_tool_references(
                NS(
                    cfg=NS(
                        llm_tool_reference_path_mode="whitelist",
                        llm_tool_reference_allowed_dirs=[str(profiles.asset_root)],
                        reference_cross_session=False,
                    ),
                    generation_tracker=None,
                    image_generator=NS(max_reference_images=6),
                ),
                NS(unified_msg_origin=scope["umo"]),
                refs,
            )
            assert error is None and len(resolved.images) == 2
            from astrbot_plugin_visual_media.tl.file_uri import file_uri_to_path

            for uri in resolved.images:
                raw = file_uri_to_path(uri).read_bytes()
                with Image.open(io.BytesIO(raw)) as decoded:
                    assert decoded.size == (960, 540)
            before = saved()
            await page.locator("#visFile").set_input_files(
                {
                    "name": "bad.png",
                    "mimeType": "image/png",
                    "buffer": b"<svg>bad</svg>",
                }
            )
            await page.locator("#visUpload").click()
            await page.wait_for_function(
                "document.getElementById('visStatus').classList.contains('error')"
            )
            assert saved() == before
            await page.reload()
            await page.wait_for_function(
                "document.getElementById('visLayout').value.includes('窗边')"
            )
            await page.locator("#sceneVisual").evaluate(
                '(n)=>n.closest("details").open=true'
            )
            assert await page.locator("#visRoomAsset").input_value() == new_layout
            await page.wait_for_function(
                "document.querySelector('#visRoomPreview img')?.naturalWidth>0"
            )
            await page.locator("#sceneVisual").screenshot(
                path=str(output / "editor-desktop.png")
            )
            for width in (320, 390, 768):
                await page.set_viewport_size({"width": width, "height": 900})
                assert await page.evaluate(
                    "document.documentElement.scrollWidth<=innerWidth+1"
                )
                await page.locator("#sceneVisual").screenshot(
                    path=str(output / f"editor-{width}.png")
                )
            plugin.world.web.settings.raw["web_panel"]["allow_write"] = False
            await page.evaluate(
                "document.dispatchEvent(new CustomEvent('world-view',{detail:'map'}))"
            )
            await page.wait_for_function(
                "!document.getElementById('visReadonly').hidden"
            )
            assert (
                await page.locator("#visUpload").is_disabled()
                and await page.locator("#visLayout").is_disabled()
            )
            assert not await page.locator("#visRoom").is_disabled()
            await page.locator("#visRoomPreview button").click()
            assert await page.locator("#visImageDialog").is_visible()
            await browser.close()
        assert not errors, errors
        report = {
            "passed": True,
            "checks": [
                "actual_http_handlers",
                "existing_settings_preloaded",
                "image_preview_and_dialog",
                "draft_survives_poll",
                "independent_section_save_preserves_other_drafts",
                "concurrent_edit_conflict",
                "upload_layout_and_style",
                "upload_does_not_bind_until_saved",
                "old_assets_retained",
                "invalid_image_rejected",
                "reload_persists_design",
                "item_state_unchanged",
                "actual_visual_media_resolver_reads_both_files",
                "readonly_preview",
                "narrow_320_390_768",
            ],
            "page_errors": errors,
            "image_provider_called": False,
        }
        (output / "result.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2)
        )
        print("VISUAL_EDITOR_BROWSER_PASS", output)
    finally:
        server.shutdown()
        server.server_close()
        await plugin.terminate()


if __name__ == "__main__":
    asyncio.run(run())
