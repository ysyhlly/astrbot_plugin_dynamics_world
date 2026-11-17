"""Real HTTP handlers + Chromium, with an isolated host context and local data."""

import asyncio
import json
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace as NS
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from playwright.async_api import async_playwright

from astrbot_plugin_dynamics_world.main import Main
from astrbot_plugin_dynamics_world.world.core import web_api as wb_api


async def run():
    from unittest.mock import AsyncMock
    from test_release_p0 import ready_context
    import hashlib
    import io
    from PIL import Image

    output = Path("/tmp/world-release-p0-browser")
    output.mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="world-onboarding-browser-"))
    routes, errors = {}, []
    context = NS(
        get_all_stars=lambda: [],
        register_web_api=lambda path, handler, methods, desc: routes.update(
            {(path.rsplit("/", 1)[-1], methods[0]): handler}
        ),
    )

    class Config(dict):
        def save_config(self):
            pass

    with patch(
        "astrbot_plugin_dynamics_world.main.StarTools.get_data_dir", return_value=root
    ):
        plugin = Main(context, Config())
    await plugin.initialize()
    ready_context(plugin)
    plugin.onboarding.browser_status = AsyncMock(
        return_value={"installed": False, "module_available": True}
    )
    stream = io.BytesIO()
    Image.new("RGB", (16, 16), "tan").save(stream, format="JPEG")
    blob = stream.getvalue()
    plugin.textures.manifest = {
        "base_url": "https://example.invalid/",
        "files": [
            {
                "name": "fixture.jpg",
                "bytes": len(blob),
                "sha256": hashlib.sha256(blob).hexdigest(),
            }
        ],
    }
    plugin.textures.fetch = AsyncMock(side_effect=ValueError("test offline"))
    scope = {"umo": "qq:GroupMessage:onboarding"}
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
                "document.querySelector('#tab-setup').getAttribute('aria-selected')==='true' && document.querySelector('#setupProvider').options.length>1"
            )
            assert await page.locator("#setupPreset").input_value() == "generic"
            assert await page.locator("#setupGrant").is_disabled()
            await page.locator("#setupNewName").evaluate(
                '(n)=>n.closest("details").open=true'
            )
            await page.locator("#setupNewName").fill("首次安装角色")
            await page.locator("#setupNewPrompt").fill(
                "喜欢读书、散步的普通角色，按实际状态自然聊天。"
            )
            await page.locator("#setupCreate").click()
            await page.wait_for_function(
                "document.getElementById('setupCard').value.length>0"
            )
            await page.locator("#setupUmo").fill(scope["umo"])
            await page.locator("#setupUmo").dispatch_event("change")
            await page.wait_for_timeout(200)
            await page.locator("#setupConfigure").click()
            await page.wait_for_function(
                "document.querySelector('#setupStarter').disabled===false"
            )
            assert plugin.config["narrative_provider_id"] == "model/test"
            await page.locator("#setupStarter").click()
            await page.wait_for_function(
                "document.getElementById('setupWorldState').textContent.includes('地图已建立')"
            )
            await page.locator("#setupRooms").click()
            await page.wait_for_function(
                "document.getElementById('setupWorldState').textContent.includes('房间与物品已建立')"
            )
            await page.locator("#setupLocate").click()
            await page.wait_for_function(
                "document.getElementById('setupLocate').disabled===true"
            )
            await page.locator("#setupRoom").evaluate(
                '(n)=>n.closest("details").open=true'
            )
            await page.locator("#setupFurnish").click()
            await page.wait_for_function(
                "document.getElementById('setupWorldState').textContent.includes('已有家具登记')"
            )
            assert (
                await page.locator("#setupStarter").is_disabled()
                and await page.locator("#setupFurnish").is_disabled()
            )
            await page.locator("#setupDownloadTextures").click()
            await page.wait_for_function(
                "document.getElementById('setupTextureState').textContent.includes('下载未完成')"
            )
            plugin.textures.fetch = AsyncMock(return_value=blob)
            await page.locator("#setupDownloadTextures").click()
            await page.wait_for_function(
                "document.getElementById('setupTextureState').textContent.includes('1/1')"
            )
            await page.locator("#setupTexture").select_option("fixture.jpg")
            await page.locator("#setupSelectTexture").click()
            await page.wait_for_function(
                "document.getElementById('setupStatus').textContent.includes('操作已完成')"
            )
            assert plugin.textures.selected() == "fixture.jpg"
            get_star = plugin.context.get_registered_star
            plugin.context.get_registered_star = lambda _: NS(
                activated=True, star_cls=NS()
            )
            await page.locator("#setupRefresh").click()
            await page.wait_for_function(
                "document.getElementById('setupChecks').textContent.includes('需要更新')"
            )
            assert await page.locator("#setupEnable").is_disabled()
            plugin.context.get_registered_star = get_star
            await page.locator("#setupRefresh").click()
            await page.wait_for_function(
                "document.getElementById('setupEnable').disabled===false"
            )
            await page.screenshot(
                path=str(output / "setup-desktop.png"), full_page=True
            )
            await page.locator("#dwTheme").click()
            await page.screenshot(path=str(output / "setup-night.png"), full_page=True)
            for width in (320, 390, 768):
                await page.set_viewport_size({"width": width, "height": 900})
                assert await page.evaluate(
                    "document.documentElement.scrollWidth<=innerWidth+1"
                )
            await page.screenshot(path=str(output / "setup-mobile.png"), full_page=True)
            await page.locator("#setupEnable").click()
            await page.wait_for_function(
                "document.getElementById('setupRuntime').textContent.includes('已开启')"
            )
            assert plugin.runtime_allowed()
            await page.locator("#setupDisable").click()
            await page.wait_for_function(
                "document.getElementById('setupRuntime').textContent.includes('编辑模式')"
            )
            assert (
                len(plugin.world.store.list_cards()) == 1
                and not plugin.config["runtime_enabled"]
            )
            await browser.close()
        assert not errors, errors
        (output / "result.json").write_text(
            json.dumps(
                {
                    "passed": True,
                    "checks": [
                        "clean_install_autostart_wizard",
                        "generic_default",
                        "create_character",
                        "sync_persona_bind_model_session",
                        "starter_map_without_chromium",
                        "rooms_and_furniture_registration",
                        "texture_download_failure_retry_and_selection",
                        "old_companion_blocks_activation",
                        "missing_media_degrades_to_text",
                        "enable_disable_preserves_world",
                        "day_night_mobile",
                    ],
                    "page_errors": errors,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        print("P0_ONBOARDING_BROWSER_PASS", output)
    finally:
        server.shutdown()
        server.server_close()
        await plugin.terminate()


if __name__ == "__main__":
    asyncio.run(run())
