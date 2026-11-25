import base64
import copy
import io
import json
from types import SimpleNamespace as NS

import pytest
from PIL import Image

from test_spatial import SCOPE
from test_visual_profiles import prepared, design
from astrbot_plugin_dynamics_world.visual_assets import VisualAssetLibrary, MAX_BYTES


def picture(color="red"):
    output = io.BytesIO()
    Image.new("RGB", (80, 48), color).save(output, format="PNG")
    return output.getvalue()


def upload(library, role="style", color="red", **extra):
    return library.upload(
        dict(
            role=role,
            label="参考 <script>只作为文字</script>",
            image_base64=base64.b64encode(picture(color)).decode(),
            **extra,
        )
    )


def test_upload_preserves_existing_assets_and_binding_until_explicit_save(rig):
    engine, now, profiles, room, book = prepared(rig)
    library = VisualAssetLibrary(profiles)
    before = copy.deepcopy(design(engine))
    index = json.loads((profiles.asset_root / "index.json").read_text())
    asset = upload(library, role="layout")
    second = upload(library, role="layout", color="blue")
    assert asset["asset_id"] != second["asset_id"]
    saved = json.loads((profiles.asset_root / "index.json").read_text())
    assert all(saved[k] == v for k, v in index.items()) and design(engine) == before
    preview = library.preview(asset["asset_id"])
    assert (
        preview["data_url"].startswith("data:image/jpeg;base64,")
        and preview["width"] == 80
    )
    profiles.configure(
        SCOPE,
        {
            "action": "room",
            "target_id": room,
            "asset_id": asset["asset_id"],
            "layout": "床在左，书桌在右",
            "expected_revision": 3,
        },
    )
    assert design(engine)["references"][0]["asset_id"] == asset["asset_id"]
    assert (profiles.asset_root / index["room"]["file"]).exists()
    with pytest.raises(ValueError):
        profiles.configure(
            SCOPE,
            {
                "action": "style",
                "asset_ids": [second["asset_id"]],
                "expected_revision": 4,
            },
        )


@pytest.mark.parametrize(
    "raw",
    [
        b'<svg xmlns="http://www.w3.org/2000/svg"></svg>',
        b"not an image",
        picture()[:20],
    ],
)
def test_invalid_image_does_not_change_catalogue(rig, raw):
    _, _, profiles, _, _ = prepared(rig)
    library = VisualAssetLibrary(profiles)
    before = (profiles.asset_root / "index.json").read_bytes()
    with pytest.raises(ValueError):
        library.upload(
            {
                "role": "style",
                "label": "x",
                "image_base64": base64.b64encode(raw).decode(),
            }
        )
    assert (profiles.asset_root / "index.json").read_bytes() == before


def test_limits_paths_urls_and_corrupt_catalogue_fail_without_data_loss(rig):
    _, _, profiles, _, _ = prepared(rig)
    library = VisualAssetLibrary(profiles)
    with pytest.raises(ValueError):
        library.preview("../../cmd_config.json")
    with pytest.raises(ValueError):
        upload(library, source_url="javascript:alert(1)")
    with pytest.raises(ValueError):
        library.upload(
            {"role": "style", "label": "x", "image_base64": "a" * (MAX_BYTES * 2)}
        )
    with pytest.raises(ValueError):
        library.upload({"role": "style", "label": "x", "image_base64": "***"})
    path = profiles.asset_root / "index.json"
    path.write_text("broken")
    with pytest.raises(ValueError):
        upload(library)
    assert path.read_text() == "broken"


def test_dimension_limit_before_decode(rig):
    _, _, profiles, _, _ = prepared(rig)
    library = VisualAssetLibrary(profiles)
    import struct
    import zlib

    raw = picture()
    ihdr = struct.pack(">IIBBBBB", 9000, 9000, 8, 2, 0, 0, 0)
    raw = raw[:16] + ihdr + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr)) + raw[33:]
    with pytest.raises(ValueError):
        library.upload(
            {
                "role": "style",
                "label": "x",
                "image_base64": base64.b64encode(raw).decode(),
            }
        )


@pytest.mark.asyncio
async def test_upload_and_preview_handlers_obey_readonly_and_scope(
    tmp_path, monkeypatch
):
    from test_world_integration import make_plugin, seed, UMO
    from astrbot_plugin_dynamics_world.world.core import web_api as transport

    plugin, _, routes = await make_plugin(tmp_path, monkeypatch)
    seed(plugin)
    monkeypatch.setattr(transport, "json_response", lambda data=None, **kwargs: data)
    monkeypatch.setattr(
        transport,
        "error_response",
        lambda message, **kwargs: {"error": message, "code": kwargs.get("status_code")},
    )
    payload = {
        "umo": UMO,
        "role": "style",
        "label": "test",
        "image_base64": base64.b64encode(picture()).decode(),
    }
    admin_headers = {
        "Host": "dashboard.local",
        "Origin": "https://dashboard.local",
        "Sec-Fetch-Site": "same-origin",
    }

    def _admin_req(method, *, query=None, body=None):
        raw = NS(
            state=NS(dashboard_g=NS(username="admin")),
            method=method,
            headers=admin_headers,
            cookies={},
        )
        return NS(
            query=query or {},
            json=lambda **kwargs: body,
            headers=admin_headers,
            cookies={},
            method=method,
            username="admin",
            _request=raw,
        )

    monkeypatch.setattr(
        transport, "request", _admin_req("POST", body=payload)
    )
    plugin.world.web.settings.raw.setdefault("web_panel", {})["allow_write"] = False
    result = await plugin.web.visual_asset_post()
    assert result["code"] == 403
    assert not plugin.life.narrative.visuals.profiles.asset_root.exists()
    plugin.world.web.settings.raw["web_panel"]["allow_write"] = True
    result = await plugin.web.visual_asset_post()
    assert result["ok"]
    asset = result["data"]["asset_id"]
    plugin.world.web.settings.raw["web_panel"]["allow_write"] = False
    monkeypatch.setattr(
        transport, "request", _admin_req("GET", query={"umo": UMO, "asset_id": asset})
    )
    assert (await plugin.web.visual_asset_get())["data"]["width"] == 80
    assert (await plugin.web.visual_get())["data"]["can_write"] is False
    await plugin.terminate()
