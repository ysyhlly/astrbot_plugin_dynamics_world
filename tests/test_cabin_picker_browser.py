"""Use the shipped UI and real plugin handlers with an isolated narrative database."""
import pytest
from playwright.async_api import async_playwright
from avatar_browser import local_panel


@pytest.mark.asyncio
async def test_switch_reload_and_receipts_on_real_panel():
    async with local_panel() as (url,*_), async_playwright() as pw:
        browser=await pw.chromium.launch(args=['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        try:
            page=await browser.new_page(viewport={'width':1024,'height':760},reduced_motion='reduce')
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            read="document.querySelector('.cabin3d-stage')?.cabin3D"
            async def prepare():
                tab=page.locator('#tab-cabin')
                await tab.wait_for(state='attached')
                if await tab.is_visible() and await tab.get_attribute('aria-selected')!='true':
                    await tab.click()
                await page.wait_for_function(read,timeout=45000)
                controls=page.locator('#cabinSceneControlsBtn')
                if await controls.count() and await controls.get_attribute('aria-expanded')!='true':
                    await controls.click()
                await page.wait_for_function("document.getElementById('cabinStyleChoice')&&!document.getElementById('cabinStyleChoice').disabled")
            await page.goto(url, wait_until='domcontentloaded')
            await prepare()
            picker=page.locator('#cabinStyleChoice')
            assert await picker.locator('option').count()==3
            async def change(style):
                async with page.expect_response(lambda r:'/api/' in r.url and r.url.split('?')[0].endswith('/cabin_style') and r.request.method=='POST') as response:
                    await picker.select_option(style)
                result=await (await response.value).json()
                payload=result.get('data',result)
                assert payload['style']==style and payload['bound']
                if style!='cottage':
                    assert len(payload['upcoming'])==2,payload
                await page.wait_for_function(read+".diagnostics().cabinStyle==="+repr(style))
                return payload
            await change('whale_coast')
            await page.wait_for_function(read+".diagnostics().portraitStatus==='ready'")
            await page.reload(wait_until='domcontentloaded')
            await prepare()
            await page.wait_for_function(read+".diagnostics().cabinStyle==='whale_coast'")
            assert await picker.input_value()=='whale_coast'
            await page.set_viewport_size({'width':390,'height':844})
            assert await picker.is_visible()
            await change('witch_court')
            await change('cottage')
            assert not errors,errors
        finally:
            await browser.close()
