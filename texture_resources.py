"""Optional pinned map textures, cached outside the plugin installation."""

import asyncio
import hashlib
import json
import os
from pathlib import Path

import aiohttp


class TextureResources:
    def __init__(self, data_root):
        self.root = Path(data_root) / "map-resources" / "textures"
        self.manifest = json.loads(
            Path(__file__).with_name("texture-manifest.json").read_text("utf-8")
        )
        self.task = None
        self.progress = {"state": "idle", "message": ""}
        self._verified = {}

    def valid(self, row):
        p = self.root / row["name"]
        try:
            stat = p.stat()
            key = (p.name, stat.st_size, stat.st_mtime_ns)
            if key not in self._verified:
                self._verified[key] = (
                    stat.st_size == row["bytes"]
                    and hashlib.sha256(p.read_bytes()).hexdigest() == row["sha256"]
                )
            return self._verified[key]
        except OSError:
            return False

    def selected(self):
        try:
            value = json.loads((self.root / "selection.json").read_text("utf-8")).get(
                "selected", ""
            )
            return (
                value
                if isinstance(value, str)
                and value in {r["name"] for r in self.manifest["files"]}
                else ""
            )
        except (OSError, ValueError, AttributeError):
            return ""

    def selected_path(self):
        name = self.selected()
        row = next((r for r in self.manifest["files"] if r["name"] == name), None)
        return str(self.root / name) if row and self.valid(row) else ""

    def status(self):
        ready = [r["name"] for r in self.manifest["files"] if self.valid(r)]
        return {
            **self.progress,
            "installed": len(ready) == len(self.manifest["files"]),
            "completed": len(ready),
            "total": len(self.manifest["files"]),
            "download_bytes": sum(r["bytes"] for r in self.manifest["files"]),
            "selected": self.selected(),
            "files": [
                {"name": r["name"], "available": r["name"] in ready}
                for r in self.manifest["files"]
            ],
        }

    def select(self, name):
        if not isinstance(name, str):
            raise ValueError("请选择纹理")
        row = next((r for r in self.manifest["files"] if r["name"] == name), None)
        if name and (not row or not self.valid(row)):
            raise ValueError("请先下载并校验所选纹理")
        self.root.mkdir(parents=True, exist_ok=True)
        p = self.root / "selection.json"
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"selected": name}))
        os.replace(tmp, p)
        return {"saved": True, "selected": name}

    def start(self):
        if self.task and not self.task.done():
            return self.status()
        self.progress = {"state": "running", "message": "正在下载并校验可选纹理"}
        self.task = asyncio.create_task(self.download())
        return self.status()

    async def fetch(self, session, row):
        url = self.manifest["base_url"] + row["name"]
        async with session.get(url, allow_redirects=False) as response:
            if response.status != 200:
                raise ValueError("纹理下载服务暂时不可用")
            data = bytearray()
            async for chunk in response.content.iter_chunked(65536):
                data.extend(chunk)
                if len(data) > row["bytes"]:
                    raise ValueError("纹理大小不符")
        if (
            len(data) != row["bytes"]
            or hashlib.sha256(data).hexdigest() != row["sha256"]
        ):
            raise ValueError("纹理校验失败")
        return bytes(data)

    async def download(self):
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            async with asyncio.timeout(300):
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=40), trust_env=True
                ) as session:
                    for row in self.manifest["files"]:
                        if self.valid(row):
                            continue
                        data = await self.fetch(session, row)
                        path = self.root / row["name"]
                        tmp = path.with_suffix(path.suffix + ".part")
                        try:
                            tmp.write_bytes(data)
                            os.replace(tmp, path)
                        finally:
                            tmp.unlink(missing_ok=True)
                        self.progress["message"] = "已校验 " + row["name"]
            self.progress = {
                "state": "ready",
                "message": "全部纹理已下载并校验；选择后用于新生成的地图",
            }
        except (ValueError, TimeoutError, aiohttp.ClientError, OSError):
            self.progress = {
                "state": "failed",
                "message": "下载未完成或校验失败，可重试；已校验的文件会复用，基础地图不受影响",
            }
        except asyncio.CancelledError:
            self.progress = {"state": "cancelled", "message": "下载已暂停，下次可继续"}
            raise

    async def close(self):
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
