"""Exercise the cabin with real WorldAPI handlers and an isolated world database."""

import argparse
import asyncio
from contextlib import asynccontextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import tempfile
from threading import Thread
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright, expect
from pytest import MonkeyPatch

from astrbot_plugin_dynamics_world.world.core import web_api as transport
from astrbot_plugin_dynamics_world.world.core.character import CharacterCard
from test_avatar_api import OTHER_UMO, seed_scene
from test_spatial import document
from test_world_integration import UMO, make_plugin, seed


BRIDGE = """<script>
window.AstrBotPluginPage = {
  ready: async () => {},
  apiGet: (endpoint, query={}) => fetch('/api/'+endpoint+'?'+new URLSearchParams(query)).then(r=>r.json()),
  apiPost: (endpoint, body) => fetch('/api/'+endpoint, {
    method: 'POST', headers: {'content-type':'application/json'}, body: JSON.stringify(body)
  }).then(r=>r.json())
};
</script>"""

READ_DIAGNOSTICS = "() => document.querySelector('.cabin3d-stage')?.cabin3D?.actorDiagnostics()"


@asynccontextmanager
async def local_panel():
    with tempfile.TemporaryDirectory(prefix='avatar-browser-') as data, MonkeyPatch.context() as patch:
        plugin, _, routes = await make_plugin(Path(data), patch)
        try:
            seed(plugin)
            plugin.world.store.upsert_card(CharacterCard(id='second', name='另一角色', persona_id='second'))
            plugin.world.store.update_session(OTHER_UMO, card_id='second')
            engine = plugin.life.narrative
            now = [1_794_366_000.0]
            patch.setattr(engine, 'clock', lambda: now[0])
            scope, _ = await plugin.web.scope(UMO)
            seed_scene(engine, scope)
            other, _ = await plugin.web.scope(OTHER_UMO)
            engine.spatial.install(other, document())
            engine.scenes.bootstrap(other, {'expected_revision': 0, 'place_id': 'a'})

            patch.setattr(transport, 'json_response', lambda data=None, status_code=200, **kwargs: (status_code, data))
            patch.setattr(transport, 'error_response', lambda message, status_code=400, **kwargs:
                (status_code, {'ok': False, 'error': message, 'message': message}))
            lock = asyncio.Lock()
            loop = asyncio.get_running_loop()
            pages = Path(__file__).resolve().parents[1] / 'pages' / 'world'
            server_errors = []

            async def invoke(path, method, query, body):
                route = ('/astrbot_plugin_dynamics_world/' + path, (method,))
                if route not in routes:
                    return 404, {'ok': False, 'error': 'route not registered'}
                async with lock:
                    patch.setattr(transport, 'request', SimpleNamespace(query=query, json=lambda **kwargs: body, headers={}))
                    return await routes[route]()

            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *args):
                    pass

                def do_GET(self):
                    self.serve('GET')

                def do_POST(self):
                    self.serve('POST')

                def serve(self, method):
                    parsed = urlparse(self.path)
                    if parsed.path.startswith('/api/'):
                        body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or '{}')
                        query = {key: values[0] for key, values in parse_qs(parsed.query).items()}
                        pending = asyncio.run_coroutine_threadsafe(invoke(parsed.path[5:], method, query, body), loop)
                        try:
                            result = pending.result(30)
                            if hasattr(result, 'body'):
                                status, payload = result.status_code, result.body
                            else:
                                status, data = result
                                payload = json.dumps(data, ensure_ascii=False).encode()
                        except Exception as exc:
                            server_errors.append(f'{method} {parsed.path}: {exc!r}')
                            status, payload = 500, json.dumps({'ok': False, 'error': str(exc)}).encode()
                        mime = 'application/json'
                    else:
                        filename = (pages / (parsed.path.lstrip('/') or 'index.html')).resolve()
                        if not filename.is_relative_to(pages) or not filename.is_file():
                            self.send_error(404)
                            return
                        status, payload = 200, filename.read_bytes()
                        mime = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
                        if filename.name == 'index.html':
                            payload = payload.replace(b'</head>', (BRIDGE + '</head>').encode())
                    self.send_response(status)
                    self.send_header('Content-Type', mime)
                    self.send_header('Content-Length', str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)

            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                yield f'http://127.0.0.1:{server.server_port}/', engine, now, scope
                assert not server_errors, server_errors
            finally:
                await asyncio.to_thread(server.shutdown)
                server.server_close()
                thread.join()
        finally:
            await plugin.terminate()


async def exercise(page, url, engine, now, scope, archive, output):
    await page.goto(url)
    await expect(page.locator('#dwScope')).to_have_value(UMO)
    await page.locator('#tab-cabin').click()
    await page.wait_for_function("document.querySelector('.cabin3d-stage')?.dataset.renderer === 'webgl'")

    async def api(endpoint, body=None, **query):
        result = await page.evaluate("([endpoint, body, query]) => body ? AstrBotPluginPage.apiPost(endpoint, body) : AstrBotPluginPage.apiGet(endpoint, query)",
            [endpoint, {'umo': UMO, **body} if body is not None else None, {'umo': UMO, **query}])
        assert result['ok'], (endpoint, result)
        return result['data']

    async def refresh():
        async with page.expect_response(lambda response: '/api/map?' in response.url) as requested:
            await page.evaluate("document.dispatchEvent(new CustomEvent('world-view',{detail:'cabin'}))")
        result = await (await requested.value).json()
        assert result['ok'], result
        return result['data']

    async def state(*, model_id=None, animating=None, texture_index=None, **projection):
        expected = {'projection': projection}
        expected.update({key: value for key, value in [('model_id', model_id), ('animating', animating),
            ('texture_index', texture_index)] if value is not None})
        try:
            await page.wait_for_function(f"expected => {{ const actual = ({READ_DIAGNOSTICS})();"
                "return actual && Object.entries(expected).every(([k,v]) => k === 'projection'"
                "? Object.entries(v).every(([p,x]) => actual.projection?.[p] === x) : actual[k] === v); }", arg=expected)
        except Exception as exc:
            raise AssertionError((expected, await page.evaluate(READ_DIAGNOSTICS), await page.locator('#avatarFeedback').text_content())) from exc
        return await page.evaluate(READ_DIAGNOSTICS)

    async def scene_post(action, **fields):
        current = (await api('map'))['scene']
        return await api('scene', {'action': action, 'expected_revision': current['revision'], **fields})

    async def advance():
        action = (await api('map'))['scene']['action']
        assert action, 'Expected an active step before advancing the clock'
        now[0] = action['step_ends_at'] + 0.01
        return await refresh()

    async def save():
        async with page.expect_response(lambda response: response.url.endswith('/api/avatar') and
                response.request.method == 'POST') as requested:
            await page.locator('#avatarApply').click()
        result = await (await requested.value).json()
        assert result['ok'], result
        await expect(page.locator('#avatarApply')).to_be_enabled()
        return result['data']

    initial = await api('map')
    home = next(room['id'] for room in initial['scene']['rooms'] if room['name'] == '房间')
    notebook = next(item['id'] for item in initial['scene']['items'] if item['kind'] == 'notebook')
    await state(model_id='builtin', visible=False, pose='idle', animating=False)
    await scene_post('start', steps=[{'kind': 'enter', 'target_id': home}])
    entering = (await api('map'))['scene']['action']['id']
    await scene_post('room', place_id='a', name='花园', sheltered=False, accessible=True, water=False)
    current = await refresh()
    assert current['scene']['action']['id'] == entering
    garden = next(room['id'] for room in current['scene']['rooms'] if room['name'] == '花园')
    await page.locator('.avatar-bindings summary').click()
    await page.locator('#avatarHomeRoom').select_option(home)
    await page.locator('#avatarGardenRoom').select_option(garden)
    assert (await save())['model_id'] == 'builtin'
    await state(model_id='builtin', visible=True, location='room', pose='walk', animating=True)
    await advance()
    await state(visible=True, location='room', pose='idle', animating=False)
    await page.locator('[data-cabin-view="room"]').click()

    await scene_post('preset', preset='read')
    await refresh()
    await state(visible=True, pose='idle')
    reading = await advance()
    action = reading['scene']['action']
    assert action['steps'][action['index']]['kind'] == 'read'
    await state(visible=True, pose='read', animating=True)
    await page.locator('.avatar-upload summary').click()
    await page.locator('#avatarFile').set_input_files(archive)
    async with page.expect_response(lambda response: response.url.endswith('/api/avatar_upload')) as requested:
        await page.locator('#avatarImport').click()
    imported = await (await requested.value).json()
    assert imported['ok'], imported
    model_id = imported['data']['id']
    assert len(imported['data']['textures']) >= 2
    await expect(page.locator('#avatarModel')).to_have_value(model_id)
    await state(model_id='builtin', pose='read')
    for index in (0, 1):
        await page.locator('#avatarTexture').select_option(str(index))
        selection = await save()
        assert selection['model_id'] == model_id and selection['texture_index'] == index
        rendered = await state(model_id=model_id, texture_index=index, pose='read')
        assert rendered['model']['source'] == 'ysm' and rendered['model']['status'] == 'ready', rendered
        assert rendered['model']['pose'] == 'read' and rendered['model']['bone_count'] > 0, rendered
        assert rendered['model']['texture_index'] == index and rendered['model']['clips'].get('walk') == 'walk', rendered
    await page.locator('.cabin3d-stage').screenshot(path=output / 'room-reading.png')
    await page.reload()
    await page.locator('#tab-cabin').click()
    await state(model_id=model_id, texture_index=1, visible=True, pose='read')
    await expect(page.locator('#avatarTexture')).to_have_value('1')
    await page.locator('[data-cabin-view="room"]').click()
    await advance()
    await state(visible=True, pose='idle')

    def notes():
        with engine._db() as db:
            _, _, saved = engine.scenes.load(db, scope)
            return saved['items'][notebook]['notes']

    await scene_post('preset', preset='write_note', title='取消验证', text='取消的文字不会落库。')
    await advance()
    await state(visible=True, pose='write', animating=True)
    assert notes() == []
    now[0] += 45
    await engine.set_paused(True, dict(scope, platform='', umo=''))
    frozen = await refresh()
    paused = await state(visible=True, pose='write', paused=True, animating=False)
    assert paused['projection']['progress'] == frozen['scene']['action']['progress']
    await page.wait_for_timeout(250)
    assert (await page.evaluate(READ_DIAGNOSTICS))['projection'] == paused['projection']
    await engine.set_paused(False, dict(scope, platform='', umo=''))
    await refresh()
    await state(visible=True, pose='write', paused=False, animating=True)
    await page.locator('#tab-overview').click()
    hidden = await state(animating=False)
    assert hidden['active'] is False
    await page.locator('#tab-cabin').click()
    await state(visible=True, pose='write', animating=True)
    await scene_post('cancel')
    await refresh()
    await state(visible=True, pose='idle', animating=False)
    assert notes() == []

    await scene_post('preset', preset='write_note', title='保留记录', text='动作结算后这条笔记只保存一次。')
    await refresh()
    await state(visible=True, pose='write', animating=True)
    assert notes() == []
    await page.locator('.cabin3d-stage').screenshot(path=output / 'room-writing.png')
    await advance()
    await state(visible=True, pose='idle')
    assert [note['title'] for note in notes()] == ['保留记录']

    await scene_post('start', steps=[{'kind': 'leave'}, {'kind': 'enter', 'target_id': garden}])
    await refresh()
    await state(visible=True, location='room', pose='walk', animating=True)
    await page.locator('#dwScope').fill(OTHER_UMO)
    immediate = await page.locator('#dwScope').evaluate("input => { input.dispatchEvent(new Event('change'));"
        f"return ({READ_DIAGNOSTICS})(); }}")
    assert immediate['projection']['visible'] is False and immediate['animating'] is False
    await state(model_id='builtin', visible=False, location='unknown', pose='idle', animating=False)
    await expect(page.locator('#avatarHomeRoom')).to_have_value('')
    await page.locator('#dwScope').fill(UMO)
    await page.locator('#dwScope').dispatch_event('change')
    await state(model_id=model_id, texture_index=1, visible=True, location='room', pose='walk')
    await advance()
    await state(visible=True, location='garden', pose='walk', animating=True)
    await page.locator('[data-cabin-view="garden"]').click()
    await page.locator('.cabin3d-stage').screenshot(path=output / 'garden-walking.png')
    await advance()
    await state(visible=True, location='garden', pose='idle', animating=False)

    await page.locator('.avatar-bindings summary').click()
    await page.locator('.avatar-upload summary').click()
    for width in (320, 390, 768):
        await page.set_viewport_size({'width': width, 'height': 920})
        assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), width
        if width == 390:
            await page.screenshot(path=output / 'garden-mobile-390.png', full_page=True)

    await scene_post('start', steps=[{'kind': 'leave'}, {'kind': 'travel', 'target_id': 'b'}])
    await refresh()
    await state(visible=True, location='garden', pose='walk')
    travelling = await advance()
    assert travelling['scene']['phase'] == 'travelling'
    await state(visible=False, location='away', pose='idle', positionBasis='journey', animating=False)
    now[0] = travelling['actor']['journey']['arrives_at'] + 0.01
    arrived = await refresh()
    assert arrived['actor']['place_id'] == 'b'
    await state(visible=False, location='away', pose='idle', animating=False)
    assert [note['title'] for note in notes()] == ['保留记录']
    return {'passed': True, 'model_id': model_id, 'texture_index': 1, 'widths': [320, 390, 768]}


async def run(archive, output):
    output.mkdir(parents=True, exist_ok=True)
    errors = []
    async with local_panel() as (url, engine, now, scope), async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True,
            args=['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        try:
            page = await browser.new_page(viewport={'width': 1440, 'height': 1000}, reduced_motion='no-preference')
            page.set_default_timeout(15_000)
            page.on('pageerror', lambda error: errors.append(str(error)))
            try:
                report = await exercise(page, url, engine, now, scope, archive, output)
                assert not errors, errors
            except Exception:
                await page.screenshot(path=output / 'failure.png', full_page=True, timeout=5_000)
                raise
        finally:
            await browser.close()
    (output / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('AVATAR_BROWSER_PASS', output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('official_zip', type=Path)
    parser.add_argument('--output', type=Path, default=Path(tempfile.gettempdir()) / 'world-avatar-browser')
    args = parser.parse_args()
    asyncio.run(run(args.official_zip, args.output))
