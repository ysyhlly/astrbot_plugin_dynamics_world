"""Offline Azgaar renderer. Run as a cancellable child process, one map at a time."""
import asyncio
import base64
import functools
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import signal
import threading
from urllib.parse import urlencode, urlparse


async def render(seed, output,texture=''):
    from playwright.async_api import async_playwright
    assets = Path(__file__).with_name("vendor") / "azgaar"
    if not (assets / "index.html").exists():
        raise RuntimeError("离线 Azgaar 资源未安装")
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            if urlparse(self.path).path=='/world-texture' and texture:
                data=Path(texture).read_bytes();self.send_response(200);self.send_header('Content-Type','image/png' if texture.endswith('.png') else 'image/jpeg');self.end_headers();self.wfile.write(data);return
            super().do_GET()
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(assets)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        task = asyncio.current_task()
        asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, task.cancel)
    except (NotImplementedError, RuntimeError):
        pass
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            try:
                context = await browser.new_context(viewport={"width":1200,"height":800}, service_workers="block")
                async def local_only(route):
                    host = urlparse(route.request.url).hostname
                    if host == "127.0.0.1" and urlparse(route.request.url).port == server.server_port:
                        await route.continue_()
                    else:
                        await route.abort()
                await context.route("**/*", local_only)
                page = await context.new_page()
                query = urlencode({"seed":seed,"options":"default","width":1200,"height":800,
                                   "layers":"ocean,landmass,heightmap,lakes,rivers,coastline,relief"})
                await page.goto(f"http://127.0.0.1:{server.server_port}/index.html?{query}", wait_until="domcontentloaded")
                await page.wait_for_function("window.FMG && FMG.mapHistory.length > 0 && FMG.pack.cells.h.length > 0", timeout=120000)
                await page.evaluate("""() => { FMG.Dialog.closeAll(); FMG.hideOptions(); FMG.resetZoom(); }""")
                data = await page.evaluate("""() => ({
                  width: FMG.options.map.graph.width, height: FMG.options.map.graph.height,
                  points: FMG.pack.cells.p, edges: FMG.pack.cells.c, heights: Array.from(FMG.pack.cells.h),
                  burgs: FMG.pack.burgs.filter(b=>b.i && !b.removed).map(b=>({name:b.name,cell:b.cell,x:b.x,y:b.y}))
                })""")
                # Hide chrome and all potentially remote textures; screenshot
                # only the generated map, with no upstream editor UI.
                await page.add_style_tag(content="body > :not(svg#map) { display:none !important; } #texture {display:none !important;}")
                if texture:
                    await page.evaluate("""async () => {
                        const url='/world-texture';const loaded=new Image();loaded.src=url;await loaded.decode();
                        const node=document.createElementNS('http://www.w3.org/2000/svg','image');
                        node.setAttribute('href',url);node.setAttribute('width',FMG.options.map.graph.width);node.setAttribute('height',FMG.options.map.graph.height);
                        node.setAttribute('preserveAspectRatio','none');node.setAttribute('opacity','0.16');node.style.mixBlendMode='multiply';node.style.pointerEvents='none';document.querySelector('svg#map').append(node);
                    }""")
                png = await page.locator("svg#map").screenshot(timeout=20000)
                data["image"] = "data:image/png;base64," + base64.b64encode(png).decode()
                Path(output).write_text(json.dumps(data, ensure_ascii=False), "utf-8")
            finally:
                await browser.close()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    asyncio.run(render(sys.argv[1], sys.argv[2],sys.argv[3] if len(sys.argv)>3 else ''))
