"""Real HTTP handlers + Chromium, with an isolated host context and local data."""

import asyncio
import json
import os
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
    output = Path("/tmp/dynamics-world-study-browser-evidence")
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
            page = await browser.new_page(
                viewport={"width": 1440, "height": 1050}, device_scale_factor=1
            )
            tile_responses = []
            page.on(
                "response",
                lambda r: (
                    tile_responses.append(r)
                    if r.url.startswith("https://tile.openstreetmap.org/")
                    else None
                ),
            )
            if not os.environ.get("DW_REAL_TILES"):
                await page.route(
                    "https://tile.openstreetmap.org/**",
                    lambda route: route.fulfill(
                        content_type="image/svg+xml",
                        body='<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect width="256" height="256" fill="#e6eddf"/><path d="M0 128H256M128 0V256" stroke="#fff" stroke-width="12"/><text x="10" y="30" fill="#567169">Offline tile fixture</text></svg>',
                    ),
                )
            page.on("pageerror", lambda e: errors.append(str(e)))
            await page.goto(f"http://127.0.0.1:{server.server_port}/")
            await page.wait_for_function(
                "document.getElementById('dwOverviewLife').textContent.includes('小夏')"
            )
            assert await page.locator("#dwOverviewLife").inner_text()
            await page.screenshot(path=str(output / "overview.png"), full_page=True)
            await page.locator('[data-view="map"]').click()
            await page.locator("#mapGeneration").evaluate("(node)=>node.open=true")
            await page.locator("#mapPlaceNames").fill(
                "住所\n学校\n街角咖啡馆\n海边步道\n书店"
            )
            await page.locator("#mapGenerate").click()
            await page.wait_for_function(
                "document.getElementById('mapStatus').textContent.includes('Azgaar')",
                timeout=180000,
            )
            assert await page.locator("#mapWhere").inner_text() == "待定位"
            with plugin.life.narrative._db() as db:
                assert (
                    db.execute("SELECT COUNT(*) FROM world_map_versions").fetchone()[0]
                    == 1
                )
            await page.locator(".dw-map-sidebar details").evaluate(
                "(node)=>node.open=true"
            )
            await page.locator('[data-map-action="locate"]').click()
            await page.wait_for_function(
                "document.getElementById('mapWhere').textContent==='住所'"
            )
            options = await page.locator("#mapDestination option").evaluate_all(
                "(nodes)=>nodes.map(n=>({value:n.value,text:n.textContent}))"
            )
            await page.locator("#mapDestination").select_option(options[1]["value"])
            await page.locator('[data-map-action="plan"]').click()
            await page.wait_for_function(
                "document.getElementById('mapPlan').textContent.includes('学校')"
            )
            assert await page.locator("#mapWhere").inner_text() == "住所"
            await page.locator('[data-map-action="depart"]').click()
            await page.wait_for_function(
                "document.getElementById('mapWhere').textContent.includes('前往 学校')"
            )
            snap = await plugin.life.get_snapshot(scope)
            journey = snap["spatial"]["journey"]
            clock = plugin.life.narrative.clock
            plugin.life.narrative.clock = lambda: (
                (journey["departed_at"] + journey["arrives_at"]) / 2
            )
            await page.evaluate(
                "document.dispatchEvent(new CustomEvent('world-view',{detail:'map'}))"
            )
            await page.wait_for_function(
                "parseFloat(document.getElementById('mapProgress').style.width)>40"
            )
            await page.screenshot(path=str(output / "map.png"), full_page=True)
            plugin.life.narrative.clock = lambda: journey["arrives_at"] + 1
            await page.evaluate(
                "document.dispatchEvent(new CustomEvent('world-view',{detail:'map'}))"
            )
            await page.wait_for_function(
                "document.getElementById('mapWhere').textContent==='学校'"
            )
            await page.reload()
            await page.wait_for_function(
                "document.getElementById('dwScope').value.length>0"
            )
            await page.locator('[data-view="map"]').click()
            await page.wait_for_function(
                "document.getElementById('mapWhere').textContent==='学校'"
            )
            with plugin.life.narrative._db() as db:
                assert (
                    db.execute("SELECT COUNT(*) FROM world_map_versions").fetchone()[0]
                    == 1
                )
            await page.locator("#sceneHome").select_option(options[0]["value"])
            await page.locator("#sceneInitialize").click()
            await page.wait_for_function(
                "document.getElementById('sceneContents').hidden === false"
            )
            assert await page.locator(".dw-scene-item").count() == 5
            # Return to the initialized home via an explicit admin correction.
            await page.locator(".dw-map-sidebar details").evaluate(
                "(node)=>node.open=true"
            )
            await page.locator("#mapDestination").select_option(options[0]["value"])
            await page.locator('[data-map-action="locate"]').click()
            await page.wait_for_function(
                "document.getElementById('mapWhere').textContent==='住所'"
            )
            await page.locator('[data-scene-preset="read"]').click()
            await page.wait_for_function(
                "document.getElementById('sceneAction').textContent.includes('进入房间')"
            )
            for i in range(3):
                snap = await plugin.life.get_snapshot(scope)
                next_time = snap["scene"]["action"]["step_ends_at"] + 1
                plugin.life.narrative.clock = lambda t=next_time: t
                await page.evaluate(
                    "document.dispatchEvent(new CustomEvent('world-view',{detail:'map'}))"
                )
                if i < 2:
                    await page.wait_for_function(
                        f"document.getElementById('sceneAction').textContent.includes('第 {i + 2}/3 步')"
                    )
            await page.wait_for_function(
                "document.getElementById('sceneItems').textContent.includes('10/120')"
            )
            await page.screenshot(
                path=str(output / "scene-reading.png"), full_page=True
            )
            await page.locator("#sceneWriting").evaluate("(n)=>n.open=true")
            await page.locator("#sceneDraftTitle").fill("湖边构思")
            await page.locator("#sceneDraftText").fill(
                "看到湖边的灯光，想写一个小故事。"
            )
            await page.locator('[data-scene-preset="write_note"]').click()
            await page.wait_for_function(
                "document.getElementById('sceneAction').textContent.includes('拿取')"
            )
            for i in range(2):
                snap = await plugin.life.get_snapshot(scope)
                at = snap["scene"]["action"]["step_ends_at"] + 1
                plugin.life.narrative.clock = lambda at=at: at
                await plugin.life.get_snapshot(scope)
            await page.evaluate(
                "document.dispatchEvent(new CustomEvent('world-view',{detail:'map'}))"
            )
            await page.wait_for_function(
                "document.getElementById('sceneItems').textContent.includes('已保存 1 条笔记')"
            )
            await page.locator("#sceneDraftTitle").fill("小镇的夜")
            await page.locator("#sceneDraftText").fill("第一章：夜色里的小镇。")
            await page.locator('[data-scene-preset="computer_work"]').click()
            await page.wait_for_function(
                "document.getElementById('sceneAction').textContent.includes('打开电脑')"
            )
            for i in range(2):
                snap = await plugin.life.get_snapshot(scope)
                at = snap["scene"]["action"]["step_ends_at"] + 1
                plugin.life.narrative.clock = lambda at=at: at
                await plugin.life.get_snapshot(scope)
            await page.evaluate(
                "document.dispatchEvent(new CustomEvent('world-view',{detail:'map'}))"
            )
            await page.wait_for_function(
                "document.getElementById('sceneItems').textContent.includes('草稿 1 篇')"
            )
            assert (await plugin.life.get_snapshot(scope))["scene"]["last_action"][
                "origin"
            ] == "admin"
            await page.locator("#sceneItems details").evaluate_all(
                "(nodes)=>nodes.forEach(n=>n.open=true)"
            )
            await page.screenshot(
                path=str(output / "study-objects.png"), full_page=True
            )
            await page.evaluate(
                "document.dispatchEvent(new CustomEvent('world-view',{detail:'map'}))"
            )
            await page.wait_for_timeout(300)
            assert await page.locator("#sceneItems details[open]").count() == 2
            assert (await plugin.life.get_snapshot(scope))["scene"]["last_action"][
                "status"
            ] == "completed"
            # Put the carried book down before returning to the earlier map test.
            snap = await plugin.life.get_snapshot(scope)
            book_item = next(x for x in snap["scene"]["items"] if x["kind"] == "book")
            plugin.life.narrative.scenes.administer(
                scope,
                {
                    "action": "start",
                    "expected_revision": snap["scene"]["revision"],
                    "steps": [
                        {"kind": "put", "target_id": book_item["id"]},
                        {"kind": "leave"},
                    ],
                },
            )
            for _ in range(2):
                snap = await plugin.life.get_snapshot(scope)
                t = snap["scene"]["action"]["step_ends_at"] + 1
                plugin.life.narrative.clock = lambda t=t: t
                await plugin.life.get_snapshot(scope)
            # Restore the existing map test's school position with an audited correction.
            with plugin.life.narrative._db() as db:
                actor = plugin.life.narrative.spatial.snapshot(
                    db, scope, plugin.life.narrative.clock()
                )
            plugin.life.narrative.spatial.admin_action(
                scope,
                {
                    "kind": "locate",
                    "target_id": options[1]["value"],
                    "map_revision": actor["map_revision"],
                    "position_revision": actor["revision"],
                },
            )
            plugin.life.narrative.clock = clock
            assert "世界模拟" in await page.locator("#weatherSource").inner_text()
            await page.locator("#realMapSettings").evaluate("(node)=>node.open=true")
            await page.locator("#realSearch").fill("Berlin")
            await page.locator("#realSearchButton").click()
            await page.locator("#realResults button").first.click()
            assert await page.locator("#realLatitude").input_value() == "52.52"
            await page.locator("#realConfigure").click()
            await page.wait_for_function(
                "document.getElementById('mapModeHint').textContent.includes('现实底图')"
            )
            await page.wait_for_function(
                "document.getElementById('weatherNow').textContent.includes('9°C')"
            )
            assert await page.locator("#mapWhere").inner_text() == "待定位"
            assert await page.locator("#weatherEffect").evaluate(
                '(n)=>n.classList.contains("rain")&&n.classList.contains("night")'
            )
            assert (
                await page.locator(".leaflet-tile").first.get_attribute(
                    "referrerpolicy"
                )
                == "origin"
            )
            await page.locator(".dw-map-sidebar details").evaluate(
                "(node)=>node.open=true"
            )
            await page.locator('[data-map-action="locate"]').click()
            await page.wait_for_function(
                "document.getElementById('mapWhere').textContent.includes('Berlin')"
            )
            await page.locator("#realMapSettings").evaluate("(node)=>node.open=false")
            if os.environ.get("DW_REAL_TILES"):
                await page.wait_for_function(
                    "document.querySelector('#worldMap img.leaflet-tile-loaded') !== null",
                    timeout=30000,
                )
                assert any(r.status == 200 for r in tile_responses), (
                    "No real OSM tiles loaded: "
                    + str([r.status for r in tile_responses])
                )
                for response in tile_responses:
                    headers = await response.request.all_headers()
                    assert (
                        headers.get("referer")
                        == f"http://127.0.0.1:{server.server_port}/"
                    ), "Tile Referer must be origin only"
            await page.screenshot(path=str(output / "real-weather.png"), full_page=True)
            from astrbot_plugin_dynamics_world.weather import response_error

            service = plugin.life.narrative.environment
            with plugin.life.narrative._db() as db:
                env = service.snapshot(db, scope, plugin.life.narrative.clock())
                db.execute(
                    "UPDATE world_weather_cache SET updated=?,payload=json_set(payload,'$.expires_at',?)",
                    (
                        plugin.life.narrative.clock() - 1801,
                        plugin.life.narrative.clock() - 1,
                    ),
                )
            service.record_failure(
                env["cache_key"],
                response_error(429, {"reason": "Hourly API request limit exceeded"}),
            )
            await page.evaluate(
                "document.dispatchEvent(new CustomEvent('world-view',{detail:'map'}))"
            )
            await page.wait_for_function(
                "document.getElementById('weatherStatus').textContent.includes('HTTP 429') && document.getElementById('weatherStatus').textContent.includes('下次自动重试')"
            )
            assert not service.tasks
            await page.screenshot(
                path=str(output / "weather-rate-limit.png"), full_page=True
            )
            with plugin.life.narrative._db() as db:
                db.execute("DELETE FROM world_weather_limits")
                db.execute(
                    "UPDATE world_weather_cache SET updated=?,error='',payload=json_set(payload,'$.expires_at',?)",
                    (
                        plugin.life.narrative.clock(),
                        plugin.life.narrative.clock() + 1800,
                    ),
                )
            await page.evaluate(
                "document.dispatchEvent(new CustomEvent('world-view',{detail:'map'}))"
            )
            await page.locator("#weatherSettings").evaluate("(node)=>node.open=true")
            await page.locator("#weatherProvider").select_option("met")
            await page.locator("#weatherFallback").select_option("open_meteo")
            await page.locator("#weatherSave").click()
            await page.wait_for_function(
                "document.getElementById('weatherProviderInfo').textContent.includes('正在使用备用源') && document.getElementById('weatherProviderInfo').textContent.includes('429')"
            )
            met_fails[0] = False
            with plugin.life.narrative._db() as db:
                db.execute("DELETE FROM world_weather_limits WHERE service='met'")
                db.execute(
                    "DELETE FROM world_weather_cache WHERE cache_key LIKE 'met|%'"
                )
            await page.evaluate(
                "document.dispatchEvent(new CustomEvent('world-view',{detail:'map'}))"
            )
            await page.wait_for_function(
                "document.getElementById('weatherProviderInfo').textContent.includes('实际天气源：MET Norway')"
            )
            assert "本地天文计算" in await page.locator("#weatherSun").inner_text()
            assert (
                await page.locator("#weatherAttribution").get_attribute("href")
                == "https://api.met.no/"
            )
            await page.screenshot(path=str(output / "met-weather.png"), full_page=True)
            await page.locator("#weatherProvider").select_option("qweather")
            await page.locator("#weatherFallback").select_option("met")
            await page.locator("#weatherSave").click()
            await page.wait_for_function(
                "document.getElementById('weatherProviderInfo').textContent.includes('尚未配置凭据')"
            )
            await page.locator("#weatherProvider").select_option("met")
            await page.locator("#weatherFallback").select_option("open_meteo")
            await page.locator("#weatherSave").click()
            await page.wait_for_function(
                "document.getElementById('weatherProviderInfo').textContent.includes('实际天气源：MET Norway')"
            )
            await page.locator("#weatherEffects").select_option("off")
            await page.locator("#weatherSave").click()
            await page.wait_for_function(
                "document.getElementById('weatherEffect').className === ''"
            )
            await page.locator("#mapMode").select_option("virtual")
            await page.locator("#mapSwitch").click()
            await page.wait_for_function(
                "document.getElementById('mapWhere').textContent==='学校'"
            )
            assert "世界模拟" in await page.locator("#weatherSource").inner_text()
            await page.locator("#weatherEffects").select_option("on")
            await page.locator("#weatherSave").click()
            await page.locator("#weatherSettings").evaluate("(node)=>node.open=false")
            await page.locator('[data-view="life"]').click()
            await page.locator('[data-life-action="pause"]').click()
            await page.wait_for_function(
                "document.getElementById('dwLifeSummary').textContent.includes('生活已暂停')"
            )
            await page.locator('[data-life-action="resume"]').click()
            await page.locator("#dwActivity").fill("沿海边散步")
            await page.locator("#dwCorrect").click()
            await page.wait_for_function(
                "document.getElementById('dwLifeSummary').textContent.includes('沿海边散步')"
            )
            await page.wait_for_function(
                "document.getElementById('dwDiary').textContent.includes('管理员纠正')"
            )
            await page.screenshot(path=str(output / "life.png"), full_page=True)
            await page.locator('[data-view="cards"]').click()
            await page.locator("#wbCardName").wait_for()
            await page.locator("#wbCardName").fill("小夏 <script>alert(1)</script>")
            await page.locator("#wbSaveCard").click()
            await page.wait_for_function(
                "document.getElementById('wbCardTitle').textContent.includes('<script>')"
            )
            assert (
                plugin.world.store.get_card("demo").name
                == "小夏 <script>alert(1)</script>"
            )
            await page.locator("#wbCardName").fill("小夏")
            await page.locator("#wbSaveCard").click()
            await page.wait_for_function(
                "document.getElementById('wbCardTitle').textContent === '小夏'"
            )
            await page.locator('[data-view="migration"]').click()
            await page.locator("#dwPreviewMigration").click()
            await page.wait_for_function(
                "document.getElementById('dwMigrationReport').textContent.includes('目标已有数据')"
            )
            assert await page.locator("#dwImportMigration").is_disabled()
            await page.set_viewport_size({"width": 390, "height": 844})
            for view in (
                "overview",
                "books",
                "cards",
                "sessions",
                "map",
                "life",
                "migration",
                "preview",
                "config",
            ):
                await page.locator(f'[data-view="{view}"]').click()
                await page.wait_for_timeout(80)
                overflow = await page.evaluate(
                    "document.documentElement.scrollWidth > window.innerWidth + 1"
                )
                assert not overflow, view
            await page.locator('[data-view="map"]').click()
            await page.screenshot(path=str(output / "mobile-map.png"), full_page=True)
            await browser.close()
        assert not errors, errors
        (output / "result.json").write_text(
            json.dumps(
                {
                    "passed": True,
                    "real_osm_tiles": bool(os.environ.get("DW_REAL_TILES")),
                    "checks": [
                        "real_handlers",
                        "overview",
                        "pause_resume",
                        "state_correction",
                        "diary",
                        "card_edit_xss",
                        "migration_conflict",
                        "ten_mobile_tabs",
                        "azgaar_offline_generation",
                        "map_persistence",
                        "plan_depart_arrive",
                        "city_search",
                        "real_map",
                        "weather_fixture",
                        "mode_roundtrip",
                        "weather_effects",
                        "tile_origin_referrer",
                    ],
                    "page_errors": errors,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        print("BROWSER_CHECK_PASS", output)
    finally:
        server.shutdown()
        server.server_close()
        await plugin.terminate()


if __name__ == "__main__":
    asyncio.run(run())
