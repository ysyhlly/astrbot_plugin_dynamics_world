import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from io import BytesIO
import json
import stat
from threading import Barrier
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from PIL import Image
import pytest

from astrbot_plugin_dynamics_world import avatar_models
from astrbot_plugin_dynamics_world.avatar_models import AvatarLibrary


GEOMETRY = {
    "minecraft:geometry": [{
        "description": {"identifier": "geometry.test", "texture_width": 8, "texture_height": 8},
        "bones": [
            {"name": "body", "pivot": [0, 0, 0], "cubes": [{"origin": [-1, 0, -1], "size": [2, 4, 2], "uv": [0, 0]}]},
            {"name": "head", "parent": "body", "pivot": [0, 4, 0], "cubes": [
                {"origin": [-1, 4, -1], "size": [2, 2, 2], "uv": {"north": {"uv": [2, 2], "uv_size": [-2, 2]}}},
            ]},
        ],
    }],
}
ANIMATIONS = {
    "idle": {"loop": True, "bones": {"head": {"rotation": ["query.anim_time", 0, 0], "scale": [1]}}},
    "walk": {"loop": True, "animation_length": 1, "bones": {
        "body": {"position": {"0": [0, 0, 0], "0.5": {"pre": [0, 1, 0], "post": [0, 2, 0], "lerp_mode": "catmullrom"}}},
    }},
}


def png(color="red", size=(8, 8)):
    buffer = BytesIO()
    Image.new("RGBA", size, color).save(buffer, "PNG")
    return buffer.getvalue()


def texture(name, data):
    return {"name": name, "data_url": "data:image/png;base64," + base64.b64encode(data).decode("ascii")}


def json_package(*, geometry=GEOMETRY, textures=(), animations=ANIMATIONS):
    return json.dumps({"geometry": geometry, "textures": list(textures), "animations": animations}).encode()


def zip_package(entries):
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for path, data in entries:
            archive.writestr(path, data)
    return buffer.getvalue()


def encrypted_zip_package(entries):
    raw = bytearray(zip_package(entries))
    pos = 0
    while True:
        idx = raw.find(b"PK\x03\x04", pos)
        if idx == -1:
            break
        raw[idx + 6] |= 1
        pos = idx + 4
    pos = 0
    while True:
        idx = raw.find(b"PK\x01\x02", pos)
        if idx == -1:
            break
        raw[idx + 8] |= 1
        pos = idx + 4
    return bytes(raw)


def test_model_and_selection_round_trip_preserves_world_files(tmp_path):
    world_state = tmp_path / "world.sqlite"
    world_state.write_bytes(b"original world state")
    library = AvatarLibrary(tmp_path / "avatars")
    assert library.catalog("persona") == {
        "models": [{"id": "builtin", "name": "默认角色", "texture_names": [], "warnings": []}],
        "selection": {"model_id": "builtin", "texture_index": 0, "home_room_id": "", "garden_room_id": "", "revision": 0},
    }
    variants = [texture("晴空", png()), texture("夜色", png("blue"))]
    package = json_package(textures=variants)
    model = library.import_package("avatar.json", package, "双贴图角色")
    assert model["textures"] == variants
    assert model["geometry"] == GEOMETRY["minecraft:geometry"][0]
    assert model["format"] == "ysm-bedrock"
    assert model["animations"]["idle"]["bones"] == {"head": {"scale": 1}}
    assert model["animations"]["walk"]["bones"]["body"]["position"]["0.5"]["pre"] == [0, 1, 0]
    assert model["warnings"] and "Molang" in model["warnings"][0]
    assert library.import_package("renamed.json", package, "不同显示名称") == model
    assert list(library.models_dir.glob("*.json")) == [library.models_dir / f"{model['id']}.json"]
    assert library.catalog("persona")["selection"]["model_id"] == "builtin"

    body = {
        "model_id": model["id"], "texture_index": 1, "home_room_id": "room-a", "garden_room_id": "room-b",
        "expected_revision": 0,
    }
    selection = library.select("persona", body)
    reopened = AvatarLibrary(tmp_path / "avatars")
    assert reopened.model(model["id"]) == model
    assert reopened.catalog("persona")["selection"] == selection
    assert reopened.catalog("persona")["models"][1]["texture_names"] == ["晴空", "夜色"]
    assert reopened.catalog("other persona")["selection"]["revision"] == 0
    with pytest.raises(ValueError, match="刷新"):
        reopened.select("persona", body)
    with pytest.raises(ValueError, match="贴图编号"):
        reopened.select("persona", {"expected_revision": 1, "texture_index": 2})
    assert reopened.catalog("persona")["selection"] == selection
    reset = reopened.select("persona", {"expected_revision": 1, "model_id": "builtin"})
    assert reset["texture_index"] == 0
    assert reset["home_room_id"] == "room-a"
    assert world_state.read_bytes() == b"original world state"


def test_zip_manifest_selects_model_animation_and_texture_variants(tmp_path):
    library = AvatarLibrary(tmp_path)
    manifest = {"files": {"player": {
        "model": {"main": "models/character.json", "arm": "models/arm.json"},
        "animation": {"main": "animations/motion.json"},
        "texture": ["textures/blue.png", "textures/default.png"],
    }}}
    raw = zip_package([
        ("pack/ysm.json", json.dumps(manifest)),
        ("pack/models/arm.json", json.dumps({"minecraft:geometry": []})),
        ("pack/models/character.json", json.dumps(GEOMETRY)),
        ("pack/animations/motion.json", json.dumps({"animations": ANIMATIONS})),
        ("pack/animations/arm.animation.json", json.dumps({"animations": {"idle": {}}})),
        ("pack/textures/default.png", png()),
        ("pack/textures/blue.png", png("blue")),
        ("pack/textures/arrow.png", png("green")),
        ("pack/avatar/author.png", png("green")),
        ("__MACOSX/pack/._ysm.json", b"AppleDouble metadata"),
    ])
    model = library.import_package("pack.zip", raw)
    assert model["geometry"]["bones"][1]["name"] == "head"
    assert model["animations"]["walk"]["animation_length"] == 1
    assert [item["name"] for item in model["textures"]] == ["blue", "default"]


def test_manifestless_zip_prefers_main_geometry_and_animation(tmp_path):
    raw = zip_package([
        ("arm.json", json.dumps({"minecraft:geometry": []})),
        ("projectile.json", json.dumps({"minecraft:geometry": []})),
        ("model.json", json.dumps({"properties": {"command": "not an asset"}})),
        ("models/main.json", json.dumps(GEOMETRY)),
        ("extra.animation.json", json.dumps({"animations": {"idle": {"bones": {"head": {"scale": 2}}}}})),
        ("main.animation.json", json.dumps({"animations": ANIMATIONS})),
        ("blue.png", png("blue")),
        ("default.png", png()),
    ])
    model = AvatarLibrary(tmp_path).import_package("pack.zip", raw)
    assert model["geometry"] == GEOMETRY["minecraft:geometry"][0]
    assert [entry["name"] for entry in model["textures"]] == ["default", "blue"]
    assert model["animations"]["idle"]["bones"]["head"]["scale"] == 1


@pytest.mark.parametrize("path", ["../escape.json", "/escape.json", "pack/../../escape.json", "C:\\escape.json", "pack\\..\\escape.json"])
def test_zip_rejects_path_traversal_and_absolute_paths(tmp_path, path):
    archive = zip_package([("main.json", json.dumps(GEOMETRY)), (path, "{}")])
    library = AvatarLibrary(tmp_path / "avatars")
    with pytest.raises(ValueError, match="路径"):
        library.import_package("escape.zip", archive)
    assert not library.root.exists()


def test_zip_rejects_links_and_manifest_path_traversal(tmp_path):
    link = ZipInfo("images/default.png")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    library = AvatarLibrary(tmp_path)
    with pytest.raises(ValueError, match="链接"):
        library.import_package("link.zip", zip_package([(link, "../../image.png")]))
    manifest = {"files": {"player": {"model": {"main": "../main.json"}}}}
    raw = zip_package([("main.json", json.dumps(GEOMETRY)), ("pack/ysm.json", json.dumps(manifest))])
    with pytest.raises(ValueError, match="路径"):
        library.import_package("bad-manifest.zip", raw)


def test_zip_rejects_expansion_and_per_file_limit(tmp_path):
    library = AvatarLibrary(tmp_path)
    # 9 PNG entries * 4 MiB each = 36 MiB > MAX_EXPANDED_BYTES (32 MiB), compressed small
    chunk = b"\x00" * avatar_models.MAX_PNG_BYTES
    archive = zip_package([(f"textures/t{index}.png", chunk) for index in range(9)])
    assert len(archive) < avatar_models.MAX_PACKAGE_BYTES
    with pytest.raises(ValueError, match="32 MiB"):
        library.import_package("bomb.zip", archive)
    with pytest.raises(ValueError, match="大小上限"):
        library.import_package("oversized.zip", zip_package([("large.json", b" " * (avatar_models.MAX_JSON_BYTES + 1))]))


def test_zip_rejects_too_many_entries(tmp_path):
    archive = zip_package([(f"note/{index}.txt", b"0") for index in range(avatar_models.MAX_FILES + 1)])
    with pytest.raises(ValueError, match="512"):
        AvatarLibrary(tmp_path).import_package("too-many.zip", archive)


def test_rejects_bone_cycle_missing_parent_and_nonfinite_geometry(tmp_path):
    library = AvatarLibrary(tmp_path)
    geometry = deepcopy(GEOMETRY)
    bones = geometry["minecraft:geometry"][0]["bones"]
    bones[0]["parent"] = "head"
    with pytest.raises(ValueError, match="循环"):
        library.import_package("cycle.json", json_package(geometry=geometry))
    bones[0]["parent"] = "missing"
    with pytest.raises(ValueError, match="不存在的父"):
        library.import_package("missing.json", json_package(geometry=geometry))
    bones[0].pop("parent")
    bones[0]["pivot"] = [float("inf"), 0, 0]
    with pytest.raises(ValueError, match="非法数值"):
        library.import_package("nonfinite.json", json_package(geometry=geometry))


@pytest.mark.parametrize("data", [b"pretend PNG", b"\x89PNG\r\n\x1a\n" + b"broken", png(size=(2049, 1))])
def test_rejects_invalid_png(tmp_path, data):
    library = AvatarLibrary(tmp_path)
    with pytest.raises(ValueError, match="PNG"):
        library.import_package("invalid.json", json_package(textures=[texture("broken", data)]))
    with pytest.raises(ValueError, match="PNG"):
        library.import_package("invalid.zip", zip_package([("main.json", json.dumps(GEOMETRY)), ("fake.png", data)]))


def test_encrypted_ysm_and_invalid_model_id_are_rejected(tmp_path):
    library = AvatarLibrary(tmp_path)
    with pytest.raises(ValueError, match="加密保护格式（DRM）"):
        library.import_package("export.YSM", b"YSM\x00\x01\x02encrypted-payload")
    with pytest.raises(ValueError, match="加密保护格式（DRM）"):
        library.import_package("export_v2.ysm", b"YSM\x02binary-header")
    with pytest.raises(ValueError, match="加密保护格式（DRM）"):
        library.import_package("renamed.zip", b"YSM\x00\x01\x02encrypted-payload")
    enc_zip = encrypted_zip_package([("main.json", json.dumps(GEOMETRY)), ("default.png", png())])
    with pytest.raises(ValueError, match="加密保护格式（DRM）"):
        library.import_package("protected.ysm", enc_zip)
    with pytest.raises(ValueError, match="加密保护格式（DRM）"):
        library.import_package("protected.zip", enc_zip)
    with pytest.raises(ValueError, match="未加密"):
        library.import_package("corrupt.ysm", b"not-a-zip-or-ysm")
    with pytest.raises(ValueError, match="标识"):
        library.model("../world.sqlite")


def test_unencrypted_ysm_v2_manifest_with_audio_and_many_entries(tmp_path):
    library = AvatarLibrary(tmp_path)
    manifest = {
        "spec": 2,
        "properties": {"name": "星野小樱"},
        "metadata": {"name": "Fallback Meta Name"},
        "files": {
            "player": {
                "model": "models/main.geo.json",
                "animation": "animations/main.animation.json",
                "texture": [
                    {"uv": "textures/spring.png", "pbr": {"normal": "textures/spring_n.png"}},
                    {"path": "textures/summer.png"},
                    {"texture": "textures/autumn.png"},
                    {"file": "textures/winter.png"},
                ],
            }
        },
    }
    entries = [
        ("ysm.json", json.dumps(manifest)),
        ("models/main.geo.json", json.dumps(GEOMETRY)),
        ("animations/main.animation.json", json.dumps({"animations": ANIMATIONS})),
        ("textures/spring.png", png("pink")),
        ("textures/spring_n.png", png("purple")),
        ("textures/summer.png", png("blue")),
        ("textures/autumn.png", png("orange")),
        ("textures/winter.png", png("white")),
        # Large .ogg audio (> MAX_EXPANDED_BYTES uncompressed) must not trigger false rejection
        ("sounds/voice_pack.ogg", b"\x00" * (avatar_models.MAX_EXPANDED_BYTES + 4096)),
    ]
    # Add > 64 extra non-asset files (e.g. lang/audio files) to confirm raised MAX_FILES (512)
    entries.extend((f"lang/entry_{idx}.lang", f"k{idx}=v{idx}".encode()) for idx in range(80))
    raw = zip_package(entries)
    assert len(raw) < avatar_models.MAX_PACKAGE_BYTES

    model = library.import_package("hoshino_sakura.ysm", raw)
    assert model["name"] == "星野小樱"
    assert model["format"] == "ysm-bedrock"
    assert [item["name"] for item in model["textures"]] == ["spring", "summer", "autumn", "winter"]
    assert model["animations"]["walk"]["animation_length"] == 1


def test_ysm_manifest_dict_texture_and_metadata_name_fallback(tmp_path):
    library = AvatarLibrary(tmp_path)
    # Single dict texture with uv key + metadata.name fallback when properties.name is absent
    manifest_single = {
        "spec": 2,
        "metadata": {"name": "月见露"},
        "files": {
            "player": {
                "model": {"main": "models/body.json"},
                "animation": {"main": "animations/body.animation.json"},
                "texture": {"uv": "textures/moon.png", "normal": "textures/moon_n.png"},
            }
        },
    }
    raw_single = zip_package([
        ("pack/ysm.json", json.dumps(manifest_single)),
        ("pack/models/body.json", json.dumps(GEOMETRY)),
        ("pack/animations/body.animation.json", json.dumps({"animations": ANIMATIONS})),
        ("pack/textures/moon.png", png("yellow")),
        ("pack/textures/moon_n.png", png("gray")),
    ])
    m1 = library.import_package("fallback_file.ysm", raw_single)
    assert m1["name"] == "月见露"
    assert [item["name"] for item in m1["textures"]] == ["moon"]

    # Variant mapping dict texture + explicit custom name overrides manifest name
    manifest_map = {
        "metadata": {"name": "Ignored Meta Name"},
        "files": {
            "player": {
                "model": "models/body.json",
                "texture": {
                    "day": "textures/day.png",
                    "night": {"uv": "textures/night.png"},
                },
            }
        },
    }
    raw_map = zip_package([
        ("ysm.json", json.dumps(manifest_map)),
        ("models/body.json", json.dumps(GEOMETRY)),
        ("textures/day.png", png("white")),
        ("textures/night.png", png("black")),
    ])
    m2 = library.import_package("day_night.ysm", raw_map, name="自定义角色名")
    assert m2["name"] == "自定义角色名"
    assert [item["name"] for item in m2["textures"]] == ["day", "night"]


def test_parallel_cas_with_different_library_instances(tmp_path):
    barrier = Barrier(2)

    def try_select(room):
        library = AvatarLibrary(tmp_path)
        barrier.wait(timeout=5)
        try:
            return library.select("persona", {"home_room_id": room, "expected_revision": 0})
        except ValueError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as executor:
        result = list(executor.map(try_select, ("a", "b")))
    assert sum(isinstance(value, dict) for value in result) == 1
    assert sum(isinstance(value, str) and "刷新" in value for value in result) == 1
    assert AvatarLibrary(tmp_path).catalog("persona")["selection"]["revision"] == 1


def test_retries_interrupted_catalog_publish_without_overwriting_model(tmp_path, monkeypatch):
    library = AvatarLibrary(tmp_path)
    original_write = avatar_models._write

    def fail_catalog(path, value):
        if path == library.catalog_path:
            raise OSError("test interruption")
        original_write(path, value)

    with monkeypatch.context() as context:
        context.setattr(avatar_models, "_write", fail_catalog)
        with pytest.raises(OSError, match="interruption"):
            library.import_package("original.json", json_package())
    assert len(library.catalog("persona")["models"]) == 1
    model = AvatarLibrary(tmp_path).import_package("renamed.json", json_package())
    assert model["name"] == "original"
    assert len(library.catalog("persona")["models"]) == 2
