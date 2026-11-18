"""Persistent library for the unencrypted Bedrock assets in a YSM model pack."""

import base64
import binascii
import json
import os
import re
import stat
from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile
from zipfile import ZIP_DEFLATED, ZIP_STORED, BadZipFile, ZipFile
from zlib import error as ZlibError

from PIL import Image

MAX_PACKAGE_BYTES = 8 * 1024 * 1024
MAX_EXPANDED_BYTES = 16 * 1024 * 1024
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_PNG_BYTES = 4 * 1024 * 1024
MAX_TEXTURE_EDGE = 2048
MAX_FILES = 64
MAX_BONES = 128
MAX_CUBES = 2048
MAX_TEXTURES = 16
MAX_MODELS = 32
MAX_TRANSFORM = 32768

PNG_PREFIX = "data:image/png;base64,"
MODEL_ID = re.compile(r"[a-f0-9]{64}")
FACES = ("north", "south", "east", "west", "up", "down")
CHANNELS = ("rotation", "position", "scale")
BUILTIN_MODEL = {
    "id": "builtin",
    "name": "默认角色",
    "format": "builtin",
    "geometry": None,
    "textures": [],
    "animations": {},
    "warnings": [],
}
DEFAULT_SELECTION = {
    "model_id": "builtin",
    "texture_index": 0,
    "home_room_id": "",
    "garden_room_id": "",
    "revision": 0,
}


def _encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _read(path, default):
    try:
        with path.open(encoding="utf-8") as source:
            return json.load(source)
    except FileNotFoundError:
        return default


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as temp:
            temp_path = Path(temp.name)
            temp.write(_encoded(value))
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


@contextmanager
def _library_lock(root):
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".write.lock").open("a+b") as lock:
        if os.name == "nt":
            import msvcrt

            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        yield  # Closing the descriptor releases the lock on both platforms.


def _text(value, label, max_length=120, *, empty=False):
    if (
        not isinstance(value, str)
        or (not empty and not value)
        or len(value) > max_length
        or any(ord(ch) < 32 or 0xD800 <= ord(ch) <= 0xDFFF for ch in value)
    ):
        raise ValueError(f"{label}无效")
    return value


def _name(value, label):
    value = _text(value, label)
    if value in {"__proto__", "constructor", "prototype"}:
        raise ValueError(f"{label}无效")
    return value


def _number(value, low=-MAX_TRANSFORM, high=MAX_TRANSFORM):
    return type(value) in (int, float) and low <= value <= high


def _vector(value, length, label, *, low=-MAX_TRANSFORM):
    if not isinstance(value, list) or len(value) != length or not all(_number(v, low) for v in value):
        raise ValueError(f"{label}必须由 {length} 个有限数值组成")
    return value


def _obj(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label}必须是 JSON 对象")
    return value


def _fields(source, target, vectors=(), numbers=(), flags=()):
    for name, length in vectors:
        if name in source:
            target[name] = _vector(source[name], length, name)
    for name in numbers:
        if name in source:
            if not _number(source[name]):
                raise ValueError(f"{name}必须是有限数值")
            target[name] = source[name]
    for name in flags:
        if name in source:
            if type(source[name]) is not bool:
                raise ValueError(f"{name}必须是布尔值")
            target[name] = source[name]


def _cube(value):
    cube = _obj(value, "立方体")
    output = {
        "origin": _vector(cube.get("origin"), 3, "立方体原点"),
        "size": _vector(cube.get("size"), 3, "立方体尺寸", low=0),
    }
    _fields(cube, output, (("pivot", 3), ("rotation", 3)), ("inflate",), ("mirror",))
    uv = cube.get("uv", [0, 0])
    if isinstance(uv, dict):
        faces = {}
        for face in FACES:
            if face in uv:
                raw = _obj(uv[face], "贴图面")
                faces[face] = {"uv": _vector(raw.get("uv"), 2, "uv")}
                _fields(raw, faces[face], (("uv_size", 2),), ("uv_rotation",))
        output["uv"] = faces
    else:
        output["uv"] = _vector(uv, 2, "uv")
    return output


def _validate_tree(bones):
    complete = set()
    for start in bones:
        visiting = set()
        current = start
        while current is not None and current not in complete:
            if current in visiting:
                raise ValueError("模型骨骼父子关系存在循环")
            if current not in bones:
                raise ValueError("模型骨骼引用了不存在的父骨骼")
            visiting.add(current)
            current = bones[current].get("parent")
        complete.update(visiting)


def _geometry(raw, warnings):
    geometry = _obj(raw, "模型几何")
    if "minecraft:geometry" in geometry:
        entries = geometry["minecraft:geometry"]
        if not isinstance(entries, list) or not entries:
            raise ValueError("模型没有 Bedrock 几何")
        geometry = _obj(entries[0], "模型几何")
        if len(entries) > 1:
            warnings.add("使用主模型的第一组 Bedrock 几何")

    source_description = _obj(geometry.get("description", {}), "几何描述")
    description = {}
    for axis in ("texture_width", "texture_height"):
        value = source_description.get(axis, 64)
        if type(value) is not int or not 1 <= value <= MAX_TEXTURE_EDGE:
            raise ValueError("几何贴图尺寸必须是 1 至 2048 的整数")
        description[axis] = value
    if "identifier" in source_description:
        description["identifier"] = _text(source_description["identifier"], "几何标识")
    _fields(source_description, description, (("visible_bounds_offset", 3),),
            ("visible_bounds_width", "visible_bounds_height"))

    source_bones = geometry.get("bones")
    if not isinstance(source_bones, list) or not 1 <= len(source_bones) <= MAX_BONES:
        raise ValueError("模型须包含 1 至 128 根骨骼")
    bones = {}
    cube_count = 0
    for raw_bone in source_bones:
        bone = _obj(raw_bone, "骨骼")
        name = _name(bone.get("name"), "骨骼名称")
        if name in bones:
            raise ValueError("模型骨骼名称重复")
        clean = {"name": name}
        if "parent" in bone:
            clean["parent"] = _name(bone["parent"], "父骨骼名称")
        _fields(bone, clean, (("pivot", 3), ("rotation", 3)), ("inflate",), ("mirror",))
        cubes = bone.get("cubes", [])
        if not isinstance(cubes, list):
            raise ValueError("骨骼的立方体必须是数组")
        cube_count += len(cubes)
        if cube_count > MAX_CUBES:
            raise ValueError("模型最多支持 2048 个立方体")
        if cubes:
            clean["cubes"] = [_cube(cube) for cube in cubes]
        if {"poly_mesh", "texture_meshes"} & bone.keys():
            warnings.add("部分网格未导入，当前仅支持 Bedrock 立方体")
        bones[name] = clean
    _validate_tree(bones)
    if not cube_count:
        raise ValueError("模型至少需要一个 Bedrock 立方体")
    return {"description": description, "bones": list(bones.values())}


def _animation_value(value):
    if _number(value):
        return value
    if isinstance(value, list) and len(value) in (1, 3) and all(_number(v) for v in value):
        return value[0] if len(value) == 1 else value
    raise ValueError("unsupported animation value")


def _keyframe(value):
    if not isinstance(value, dict):
        return _animation_value(value)
    frame = {side: _animation_value(value[side]) for side in ("pre", "post") if side in value}
    if not frame:
        raise ValueError("empty keyframe")
    if value.get("lerp_mode") in ("linear", "catmullrom"):
        frame["lerp_mode"] = value["lerp_mode"]
    return frame


def _channel(value):
    if not isinstance(value, dict):
        return _animation_value(value)
    if not value:
        raise ValueError("empty animation channel")
    frames = {}
    for key, frame in value.items():
        time = float(key)
        if not _number(time, 0):
            raise ValueError("invalid animation time")
        canonical_key = str(time)
        if canonical_key in frames:
            raise ValueError("duplicate animation time")
        frames[canonical_key] = _keyframe(frame)
    return frames


MOLANG_SAFE_CHARS = re.compile(r"^[0-9a-zA-Z_.\s+\-*/%?:!<>=&|,()]+$")


def _molang_expr_or_num(value):
    if _number(value):
        return value
    if isinstance(value, str):
        expr = value.strip()
        if 1 <= len(expr) <= 240 and MOLANG_SAFE_CHARS.fullmatch(expr) and "__" not in expr:
            return expr
    raise ValueError("unsafe molang expression")


def _molang_value(value):
    if _number(value) or isinstance(value, str):
        return _molang_expr_or_num(value)
    if isinstance(value, list) and len(value) in (1, 3):
        items = [_molang_expr_or_num(v) for v in value]
        return items[0] if len(items) == 1 else items
    raise ValueError("unsupported molang value")


def _molang_keyframe(value):
    if not isinstance(value, dict):
        return _molang_value(value)
    frame = {side: _molang_value(value[side]) for side in ("pre", "post") if side in value}
    if not frame:
        raise ValueError("empty molang keyframe")
    if value.get("lerp_mode") in ("linear", "catmullrom"):
        frame["lerp_mode"] = value["lerp_mode"]
    return frame


def _molang_channel(value):
    if not isinstance(value, dict):
        return _molang_value(value)
    if not value:
        raise ValueError("empty molang channel")
    frames = {}
    for key, frame in value.items():
        time = float(key)
        if not _number(time, 0):
            raise ValueError("invalid animation time")
        canonical = str(time)
        if canonical in frames:
            raise ValueError("duplicate animation time")
        frames[canonical] = _molang_keyframe(frame)
    return frames


def _extract_molang_animations(raw, bone_names):
    """Extract safe AST-evaluable Molang channels without altering numeric assets hash."""
    result = {}
    if not isinstance(raw, dict):
        return result
    if "format_version" in raw and isinstance(raw.get("animations"), dict):
        raw = raw["animations"]
    for name, clip in raw.items():
        try:
            _name(name, "动画名称")
            source_bones = _obj(_obj(clip, "动画").get("bones", {}), "动画骨骼")
        except ValueError:
            continue
        expr_bones = {}
        for bone, channels in source_bones.items():
            if bone not in bone_names or not isinstance(channels, dict):
                continue
            expr_channels = {}
            for channel, value in channels.items():
                if channel not in CHANNELS:
                    continue
                try:
                    _channel(value)
                    continue  # Already in pure numeric animations!
                except ValueError:
                    pass
                try:
                    expr_channels[channel] = _molang_channel(value)
                except ValueError:
                    continue
            if expr_channels:
                expr_bones[bone] = expr_channels
        if not expr_bones:
            continue
        expr_clip = {"bones": expr_bones}
        loop = clip.get("loop")
        if type(loop) is bool or loop == "hold_on_last_frame":
            expr_clip["loop"] = loop
        length = clip.get("animation_length")
        if _number(length, 0):
            expr_clip["animation_length"] = length
        result[name] = expr_clip
    return result


def _animations(raw, bone_names, warnings):
    result = {}
    if not isinstance(raw, dict):
        warnings.add("部分动画格式不受支持，已跳过")
        return result
    if "format_version" in raw and "animations" in raw:
        raw = raw["animations"]
        if not isinstance(raw, dict):
            warnings.add("部分动画格式不受支持，已跳过")
            return result
    for name, clip in raw.items():
        try:
            _name(name, "动画名称")
            source_bones = _obj(_obj(clip, "动画").get("bones", {}), "动画骨骼")
        except ValueError:
            warnings.add("部分动画格式不受支持，已跳过")
            continue
        clean_bones = {}
        for bone, channels in source_bones.items():
            if bone not in bone_names or not isinstance(channels, dict):
                continue
            clean_channels = {}
            for channel, value in channels.items():
                try:
                    if channel not in CHANNELS:
                        raise ValueError("unsupported animation channel")
                    clean_channels[channel] = _channel(value)
                except ValueError:
                    warnings.add("部分动画通道含 Molang 表达式或不支持的数据，已跳过")
            if clean_channels:
                clean_bones[bone] = clean_channels
        if {"sound_effects", "particle_effects", "timeline", "anim_time_update", "blend_weight"} & clip.keys():
            warnings.add("模型动画的事件与运行时表达式已跳过")
        if not clean_bones:
            continue
        clean_clip = {"bones": clean_bones}
        loop = clip.get("loop")
        if type(loop) is bool or loop == "hold_on_last_frame":
            clean_clip["loop"] = loop
        length = clip.get("animation_length")
        if _number(length, 0):
            clean_clip["animation_length"] = length
        result[name] = clean_clip
    return result


def _texture(name, png):
    if not 0 < len(png) <= MAX_PNG_BYTES:
        raise ValueError("单张 PNG 贴图不得超过 4 MiB")
    try:
        with Image.open(BytesIO(png), formats=("PNG",)) as image:
            if max(image.size) > MAX_TEXTURE_EDGE or getattr(image, "n_frames", 1) != 1:
                raise ValueError("贴图必须是 2048×2048 以内的静态 PNG")
            image.verify()
        with Image.open(BytesIO(png), formats=("PNG",)) as image:
            image.load()
    except (OSError, SyntaxError, Image.DecompressionBombError, EOFError, ZlibError) as exc:
        raise ValueError("贴图不是有效的 PNG") from exc
    return {"name": _text(name, "贴图名称"), "data_url": PNG_PREFIX + base64.b64encode(png).decode("ascii")}


def _json_object(raw, label, max_bytes=MAX_JSON_BYTES):
    if len(raw) > max_bytes:
        raise ValueError(f"{label}超过大小上限")
    try:
        return _obj(json.loads(raw.decode("utf-8-sig")), label)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError(f"{label}不是有效的 UTF-8 JSON 对象") from exc


def _json_package(raw):
    # The wrapper may include inline images. Its geometry and animations share the JSON asset limit.
    document = _json_object(raw, "JSON 模型包", MAX_PACKAGE_BYTES)
    geometry = document.get("geometry")
    animations = document.get("animations", {})
    try:
        assets_size = len(_encoded({"geometry": geometry, "animations": animations}))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError("JSON 模型包包含非法数值或文本") from exc
    if assets_size > MAX_JSON_BYTES:
        raise ValueError("模型几何与动画 JSON 不得超过 2 MiB")
    images = document.get("textures", [])
    if not isinstance(images, list) or len(images) > MAX_TEXTURES:
        raise ValueError("模型最多支持 16 张贴图")
    textures = []
    for entry in images:
        entry = _obj(entry, "贴图")
        url = entry.get("data_url")
        if not isinstance(url, str) or not url.startswith(PNG_PREFIX):
            raise ValueError("贴图须使用 PNG data URL")
        encoded = url[len(PNG_PREFIX):]
        if len(encoded) > ((MAX_PNG_BYTES + 2) // 3) * 4:
            raise ValueError("单张 PNG 贴图不得超过 4 MiB")
        try:
            png = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("PNG 贴图的 Base64 无效") from exc
        textures.append(_texture(entry.get("name"), png))
    return geometry, textures, animations, set()


def _archive_path(path):
    if not isinstance(path, str) or not path or len(path) > 512:
        raise ValueError("ZIP 包内路径无效")
    path = path.replace("\\", "/").removesuffix("/")
    if any(
        part in ("", ".", "..")
        or ":" in part
        or part.endswith((" ", "."))
        or any(ord(ch) < 32 for ch in part)
        for part in path.split("/")
    ):
        raise ValueError("ZIP 包内路径无效")
    return path


def _zip_entries(archive):
    entries = archive.infolist()
    if len(entries) > MAX_FILES or sum(entry.file_size for entry in entries) > MAX_EXPANDED_BYTES:
        raise ValueError("ZIP 包最多 64 个条目，解压内容不得超过 16 MiB")
    files = {}
    seen = set()
    for entry in entries:
        name = _archive_path(entry.orig_filename).casefold()
        kind = stat.S_IFMT(entry.external_attr >> 16)
        if kind not in (0, stat.S_IFREG, stat.S_IFDIR) or entry.external_attr & 0x400:
            raise ValueError("ZIP 包不能包含链接或特殊文件")
        if name in seen:
            raise ValueError("ZIP 包内路径重复")
        if entry.flag_bits & 1:
            raise ValueError("请提供未加密的 ZIP 模型源文件")
        seen.add(name)
        if entry.is_dir() or "__macosx" in name.split("/") or PurePosixPath(name).name.startswith("._"):
            continue
        suffix = PurePosixPath(name).suffix
        limit = {".json": MAX_JSON_BYTES, ".png": MAX_PNG_BYTES}.get(suffix)
        if limit is None:
            continue
        if entry.file_size > limit:
            raise ValueError(f"ZIP 包内单个 {suffix} 文件超过大小上限")
        if entry.compress_type not in (ZIP_STORED, ZIP_DEFLATED):
            raise ValueError("ZIP 模型请使用常规 ZIP 压缩")
        files[name] = entry
    return files


def _archive_read(archive, entry):
    with archive.open(entry) as source:
        data = source.read(entry.file_size + 1)
    if len(data) != entry.file_size:
        raise ValueError("ZIP 包内文件大小不符")
    return data


def _geometry_priority(path):
    filename = PurePosixPath(path).name
    if filename in ("main.json", "main.geo.json", "model.json", "model.geo.json"):
        priority = 0
    elif "arm" in filename:
        priority = 2
    else:
        priority = 1
    return priority, path.count("/"), path


def _pack_reference(manifest, reference):
    path = _archive_path(reference).casefold()
    prefix, _, _ = manifest.rpartition("/")
    return f"{prefix}/{path}" if prefix else path


def _player_assets(documents):
    manifests = sorted((key for key in documents if key.split("/")[-1] == "ysm.json"), key=lambda key: (key.count("/"), key))
    if not manifests:
        return None, None, []
    path = manifests[0]
    files = documents[path].get("files")
    player = files.get("player") if isinstance(files, dict) else None
    if not isinstance(player, dict):
        return None, None, []
    model = player.get("model")
    animation = player.get("animation")
    main = model.get("main") if isinstance(model, dict) else None
    motion = animation.get("main") if isinstance(animation, dict) else None
    textures = player.get("texture")
    return (
        _pack_reference(path, main) if isinstance(main, str) and main else None,
        _pack_reference(path, motion) if isinstance(motion, str) and motion else None,
        [_pack_reference(path, image) for image in textures if isinstance(image, str)] if isinstance(textures, list) else [],
    )


def _zip_package(raw):
    warnings = set()
    try:
        with ZipFile(BytesIO(raw)) as archive:
            files = _zip_entries(archive)
            documents = {
                name: _json_object(_archive_read(archive, entry), PurePosixPath(name).name)
                for name, entry in files.items()
                if name.endswith(".json")
            }
            main, motion, skins = _player_assets(documents)
            geometries = sorted(
                (name for name, doc in documents.items() if "minecraft:geometry" in doc),
                key=_geometry_priority,
            )
            if not geometries:
                raise ValueError("ZIP 模型包内未找到 Bedrock 主模型 JSON")
            if main and main not in geometries:
                raise ValueError("YSM 配置指定的主模型 JSON 缺失")
            geometry = documents[main or geometries[0]]

            if not skins:
                skins = sorted(
                    (
                        name for name in files
                        if name.endswith(".png")
                        and not {"avatar", "gui", "__macosx"} & set(name.split("/")[:-1])
                    ),
                    key=lambda name: (PurePosixPath(name).name != "default.png", name),
                )
            skins = list(dict.fromkeys(skins))
            if len(skins) > MAX_TEXTURES:
                raise ValueError("模型最多支持 16 张贴图")
            textures = []
            for name in skins:
                if name not in files or not name.endswith(".png"):
                    raise ValueError("YSM 配置指定的 PNG 贴图缺失")
                entry = files[name]
                textures.append(_texture(PurePosixPath(entry.orig_filename.replace("\\", "/")).stem, _archive_read(archive, entry)))

            primary = documents.get(motion, {}).get("animations")
            if isinstance(primary, dict):
                animations = primary
            else:
                if motion:
                    warnings.add("YSM 配置指定的主动画缺失，使用可用动画")
                animations = {}
                animation_paths = sorted(
                    documents, key=lambda name: (PurePosixPath(name).name != "main.animation.json", name)
                )
                for name in animation_paths:
                    clips = documents[name].get("animations")
                    if isinstance(clips, dict) and "arm" not in PurePosixPath(name).name:
                        for clip_name, clip in clips.items():
                            animations.setdefault(clip_name, clip)
            if any("animation_controllers" in doc for doc in documents.values()):
                warnings.add("YSM 动画控制器未导入")
    except (BadZipFile, EOFError, ZlibError, NotImplementedError, RuntimeError) as exc:
        raise ValueError("ZIP 模型包损坏或压缩方式不受支持") from exc
    return geometry, textures, animations, warnings


def _summary(model):
    return {
        "id": model["id"],
        "name": model["name"],
        "texture_names": [texture["name"] for texture in model["textures"]],
        "warnings": list(model["warnings"]),
    }


class AvatarLibrary:
    def __init__(self, root):
        self.root = Path(root)
        self.models_dir = self.root / "models"
        self.catalog_path = self.root / "catalog.json"

    def _selection_path(self, scope_key):
        try:
            scope_id = sha256(_encoded(scope_key)).hexdigest()
        except (TypeError, UnicodeError, ValueError, RecursionError) as exc:
            raise ValueError("角色显示范围无效") from exc
        return self.root / "selections" / f"{scope_id}.json"

    def catalog(self, scope_key):
        selection = _read(self._selection_path(scope_key), DEFAULT_SELECTION.copy())
        models = _read(self.catalog_path, {})
        return {"models": [_summary(BUILTIN_MODEL), *models.values()], "selection": selection}

    def model(self, model_id):
        if model_id == "builtin":
            return deepcopy(BUILTIN_MODEL)
        if not isinstance(model_id, str) or not MODEL_ID.fullmatch(model_id):
            raise ValueError("角色模型标识无效")
        model = _read(self.models_dir / f"{model_id}.json", None)
        if model is None:
            raise ValueError("角色模型不存在")
        return model

    def import_package(self, filename, raw_bytes, name=""):
        filename = _text(filename, "模型文件名", 256)
        if "/" in filename or "\\" in filename or ":" in filename or filename in (".", ".."):
            raise ValueError("模型文件名无效")
        extension = PurePosixPath(filename).suffix.lower()
        if extension == ".ysm":
            raise ValueError("加密 .ysm 文件无法导入，请上传作者提供的未加密 ZIP 模型源文件")
        if not isinstance(raw_bytes, bytes) or not 0 < len(raw_bytes) <= MAX_PACKAGE_BYTES:
            raise ValueError("模型包不得为空或超过 8 MiB")
        if extension == ".zip":
            geometry, textures, animations, warnings = _zip_package(raw_bytes)
        elif extension == ".json":
            geometry, textures, animations, warnings = _json_package(raw_bytes)
        else:
            raise ValueError("请上传未加密 ZIP 或 JSON 模型包")
        geometry = _geometry(geometry, warnings)
        bone_set = {bone["name"] for bone in geometry["bones"]}
        molang_animations = _extract_molang_animations(animations, bone_set)
        animations = _animations(animations, bone_set, warnings)
        assets = {"geometry": geometry, "textures": textures, "animations": animations}
        model_id = sha256(_encoded(assets)).hexdigest()
        name = _text(name, "模型名称", empty=True).strip() or PurePosixPath(filename).stem[:120]
        model = {
            "id": model_id,
            "name": name,
            "format": "ysm-bedrock",
            **assets,
            **({"molang_animations": molang_animations} if molang_animations else {}),
            "warnings": sorted(warnings),
        }
        model_path = self.models_dir / f"{model_id}.json"
        with _library_lock(self.root):
            catalog = _read(self.catalog_path, {})
            if model_id in catalog:
                return self.model(model_id)
            existing = _read(model_path, None)
            if existing is not None:
                model = existing  # Recover an import interrupted before publishing the catalog.
            else:
                if sum(1 for path in self.models_dir.glob("*.json") if MODEL_ID.fullmatch(path.stem)) >= MAX_MODELS:
                    raise ValueError("角色模型库最多支持 32 个导入模型")
                _write(model_path, model)
            catalog[model_id] = _summary(model)
            _write(self.catalog_path, catalog)
        return model

    def select(self, scope_key, body):
        fields = {"model_id", "texture_index", "home_room_id", "garden_room_id", "expected_revision"}
        if not isinstance(body, dict) or body.keys() - fields:
            raise ValueError("角色设置字段无效")
        selection_path = self._selection_path(scope_key)
        with _library_lock(self.root):
            previous = _read(selection_path, DEFAULT_SELECTION)
            revision = body.get("expected_revision")
            if type(revision) is not int or revision != previous["revision"]:
                raise ValueError("角色设置已变化，请刷新后重试")
            model_id = body.get("model_id", previous["model_id"])
            catalog = _read(self.catalog_path, {})
            if not isinstance(model_id, str) or (model_id != "builtin" and model_id not in catalog):
                raise ValueError("角色模型不存在")
            available = catalog[model_id]["texture_names"] if model_id != "builtin" else []
            texture = body.get("texture_index", previous["texture_index"] if model_id == previous["model_id"] else 0)
            if type(texture) is not int or not 0 <= texture < max(1, len(available)):
                raise ValueError("角色贴图编号无效")
            selection = {
                "model_id": model_id,
                "texture_index": texture,
                "home_room_id": _text(body.get("home_room_id", previous["home_room_id"]), "小屋房间标识", 256, empty=True),
                "garden_room_id": _text(body.get("garden_room_id", previous["garden_room_id"]), "花园房间标识", 256, empty=True),
                "revision": revision + 1,
            }
            _write(selection_path, selection)
        return selection
