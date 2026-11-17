"""Validated, immutable image uploads for the authenticated World dashboard."""
import base64
import binascii
import hashlib
import io
import json
import os
import uuid
import warnings
from urllib.parse import urlsplit

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 16 * 1024 * 1024
FORMATS = {'PNG': ('png', 'image/png'), 'JPEG': ('jpg', 'image/jpeg'), 'WEBP': ('webp', 'image/webp')}


def open_image(raw):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            image = Image.open(io.BytesIO(raw))
            if image.format not in FORMATS or image.width * image.height > MAX_PIXELS or max(image.size) > 8192 or getattr(image, 'n_frames', 1) != 1:
                raise ValueError('请选择静态 PNG、JPEG 或 WebP，最多 1600 万像素、单边不超过 8192 像素')
            image.load()
            return image
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError('图片损坏或尺寸过大，请重新选择') from exc


class VisualAssetLibrary:
    def __init__(self, profiles):
        self.profiles = profiles

    def upload(self, body):
        role, label, value = body.get('role'), body.get('label'), body.get('image_base64')
        if role not in {'style', 'layout'}:
            raise ValueError('请选择画风参考或房间底图')
        if not isinstance(label, str) or not 1 <= len(label.strip()) <= 100:
            raise ValueError('素材名称需为 1–100 字')
        if not isinstance(value, str) or not value or len(value) > ((MAX_BYTES + 2) // 3) * 4:
            raise ValueError('图片不能超过 8 MB')
        try:
            raw = base64.b64decode(value, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError('图片编码不正确') from exc
        if not 0 < len(raw) <= MAX_BYTES:
            raise ValueError('图片不能超过 8 MB')
        source = body.get('source_url', '')
        if not isinstance(source, str) or len(source) > 300:
            raise ValueError('来源链接过长')
        source = source.strip()
        if source and (urlsplit(source).scheme not in {'http', 'https'} or not urlsplit(source).hostname or any(ord(c) < 32 for c in source)):
            raise ValueError('来源链接需为 http 或 https 地址')
        with open_image(raw) as image:
            extension, mime = FORMATS[image.format]
            width, height = image.size
        root = self.profiles.asset_root
        root.mkdir(parents=True, exist_ok=True)
        index = root / 'index.json'
        # Do not replace a malformed catalogue with an empty one.
        rows = json.loads(index.read_text('utf-8')) if index.exists() else {}
        if not isinstance(rows, dict):
            raise ValueError('素材目录需要修复，未修改现有素材')
        if len(rows) >= 32:
            raise ValueError('素材库已有 32 张图片，请先使用已有素材')
        asset_id = 'upload_' + uuid.uuid4().hex
        filename = asset_id + '.' + extension
        digest = hashlib.sha256(raw).hexdigest()
        row = {'file': filename, 'role': role, 'label': label.strip(), 'source_url': source,
               'sha256': digest, 'width': width, 'height': height, 'mime': mime, 'bytes': len(raw)}
        updated = dict(rows, **{asset_id: row})
        manifest = json.dumps(updated, ensure_ascii=False, indent=2).encode()
        if len(manifest) > 65536:
            raise ValueError('素材目录已满，未修改现有素材')
        target = root / filename
        stage = root / (asset_id + '.tmp')
        manifest_stage = root / ('index-' + uuid.uuid4().hex + '.tmp')
        try:
            stage.write_bytes(raw)
            os.replace(stage, target)
            manifest_stage.write_bytes(manifest)
            os.replace(manifest_stage, index)
        except Exception:
            stage.unlink(missing_ok=True)
            manifest_stage.unlink(missing_ok=True)
            # The previous index remains intact if commit failed.
            if not index.exists() or asset_id not in json.loads(index.read_text('utf-8')):
                target.unlink(missing_ok=True)
            raise
        return {'asset_id': asset_id, 'role': role, 'label': row['label'], 'sha256': digest,
                'source_url': source, 'width': width, 'height': height, 'bytes': len(raw)}

    def preview(self, asset_id):
        asset = self.profiles.assets().get(asset_id)
        if not asset:
            raise ValueError('参考图不存在或已损坏')
        from pathlib import Path
        raw = Path(asset['reference']).read_bytes()
        with open_image(raw) as original:
            width, height = original.size
            image = ImageOps.exif_transpose(original).convert('RGB')
            image.thumbnail((960, 640))
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=85)
        return {'asset_id': asset_id, 'label': asset['label'], 'sha256': asset['sha256'],
                'width': width, 'height': height, 'source_url': asset['source_url'],
                'data_url': 'data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode('ascii')}
