"""Generate durable geography from pinned Azgaar assets and worldbook names."""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import tempfile
import time

from .spatial import identity, place_id, route


def suggested_places(character):
    names = []
    for item in character.get("world_items", []):
        # Only explicit, bounded location-like titles/scenes from global world
        # settings. Never pass chat text or scoped diaries to map generation.
        text = item.get("text", "")
        title = text.splitlines()[0] if text else ""
        match = re.match(r"(?:世界|地点|场景)[-—:：](.{1,32})$",title)
        if match:
            title_place = re.sub(r"(?:结构|介绍|概览)$","",match[1]).strip()
            # A region/island is the map's container, not a point within itself.
            if title_place and not title_place.endswith(("岛","世界","地区","大陆")):
                if title_place not in names:names.append(title_place)
            for landmark in re.findall(r"深林|森林|花田|湖泊|吊桥|海滩|港口|码头|海边|庭院|公园|(?<![\u4e00-\u9fff])湖(?=[、，；。])",text):
                if landmark=="森林" and "深林" in names:continue
                if landmark not in names:names.append(landmark)
        for name in re.findall(r"(?:^|\n)(?:适用场景[:：]\s*)?([^\n：:]{1,32}(?:馆|学校|教室|小镇|村|公园|海边|宿舍|卧室|广场|大厅|车站|书店|餐厅|咖啡店|庭院|图书室))(?:\n|$)", text):
            name = name.strip(" #-、")
            if name and name not in names:
                names.append(name)
    return names[:24]


def convert(raw, seed, names, seconds_per_unit=10):
    points, neighbors, heights = raw["points"], raw["edges"], raw["heights"]
    if not 1 <= len(points) <= 100000 or len(neighbors) != len(points) or len(heights) != len(points):
        raise ValueError("生成器地形数据不完整")
    land = {i for i,h in enumerate(heights) if h >= 20}
    components = []
    while land:
        first = min(land);todo = [first];component = {first};land.remove(first)
        for cell in todo:
            for target in neighbors[cell]:
                if target in land:
                    land.remove(target);component.add(target);todo.append(target)
        components.append(component)
    if not components:
        raise ValueError("本次生成没有陆地，请更换种子")
    mainland = max(components, key=len)
    ordered = sorted(mainland)
    indices = {old:new for new,old in enumerate(ordered)}
    graph = {"points":[points[i] for i in ordered],
             "edges":[[indices[j] for j in neighbors[i] if j in mainland] for i in ordered]}
    burgs = [b for b in raw["burgs"] if b["cell"] in mainland]
    # Prefer well-spaced settlement anchors. Preserve supplied worldbook names.
    candidates = sorted(burgs, key=lambda b: hashlib.sha256((seed+str(b["cell"])).encode()).hexdigest())
    if not candidates:
        candidates = [{"cell":i,"name":"地点"+str(n+1)} for n,i in enumerate(ordered[::max(1,len(ordered)//12)])]
    labels = names or [b["name"] for b in candidates[:12]]
    if len(labels) > len(candidates):
        occupied = {b["cell"] for b in candidates}
        candidates += [{"cell":i,"name":"地点"} for i in ordered if i not in occupied]
    coastal = {i for i in mainland if any(heights[j]<20 for j in neighbors[i])}
    coast_distance = {i:0 for i in coastal}
    frontier = list(coastal)
    for cell in frontier:
        for target in neighbors[cell]:
            if target in mainland and target not in coast_distance:
                coast_distance[target]=coast_distance[cell]+1;frontier.append(target)
    places = []
    remaining = list(candidates)
    for label in labels:
        if names and re.search(r"海边|海岸|海滩|港口|码头|海滨|沙滩",label):
            anchor=min(remaining,key=lambda b:coast_distance.get(b["cell"],100000))
        elif names and re.search(r"山顶|山峰|高地",label):
            anchor=max(remaining,key=lambda b:heights[b["cell"]])
        else:
            anchor=remaining[0]
        remaining.remove(anchor)
        cell = indices[anchor["cell"]]
        x,y = graph["points"][cell]
        places.append({"id":place_id(label),"name":label,"x":x,"y":y,"cell":cell,
                       "origin":"worldbook_or_admin" if names else "generated"})
    document = {"schema_version":1,"generator":"Azgaar 1.156.0", "generator_commit":"67d555b83f0b2f40ae50b03c9bbfd018175acc6d",
                "seed":seed,"width":raw["width"],"height":raw["height"],"image":raw["image"],
                "places":places,"graph":graph,"seconds_per_unit":seconds_per_unit,"roads":[],"created_at":time.time()}
    # Connect places by a spanning tree, using actual walkable cells.
    connected = [places[0]] if places else []
    pending = places[1:]
    while pending:
        _,a,b = min(((math.dist([a["x"],a["y"]],[b["x"],b["y"]]),a,b) for a in connected for b in pending),key=lambda row:row[0])
        path,distance = route(document,a["cell"],b["cell"])
        document["roads"].append({"from":a["id"],"to":b["id"],"path":path,"distance":distance})
        pending.remove(b);connected.append(b)
    return document


class MapService:
    def __init__(self, plugin):
        self.plugin = plugin
        self.task = None
        self.process = None
        self.job = {"status":"idle"}

    async def close(self):
        if self.task and not self.task.done():
            self.task.cancel()
            await asyncio.gather(self.task,return_exceptions=True)

    async def suggest(self, scope):
        return self._suggest(scope, self.plugin.world.store)

    @staticmethod
    def _suggest(scope, store):
        # A global role read excludes arbitrary session-selected material.
        _,card,books = store.snapshot_global_character_inputs(scope["persona_id"])
        if card is None:return []
        character={"world_items":[{"text":entry.display_name()+"\n"+entry.content+
                        ("\n适用场景："+"\n".join(entry.scenarios) if entry.scenarios else "")}
                    for book in books for entry in book.entries if entry.enabled]}
        return suggested_places(character)

    async def start(self, scope, body):
        if self.task and not self.task.done():
            raise ValueError("已有地图正在生成，请等待完成")
        seed = str(body.get("seed", "")).strip()
        if not seed or len(seed)>64:
            raise ValueError("种子需为 1–64 个字符")
        names = body.get("places", [])
        if not isinstance(names,list) or len(names)>32 or any(not isinstance(n,str) or not n.strip() or len(n)>60 for n in names):
            raise ValueError("地点需为不超过 32 个名称，每个不超过 60 字")
        names = list(dict.fromkeys(n.strip() for n in names))
        if not names:
            names = await self.suggest(scope)
        speed = body.get("seconds_per_unit",10)
        if type(speed) not in (int,float) or not math.isfinite(speed) or not 1<=speed<=120:
            raise ValueError("地图行程比例需在 1–120 秒/地图单位之间")
        revision = body.get("expected_revision",0)
        if type(revision) is not int or revision<0:
            raise ValueError("无效地图版本")
        character = await self.plugin.world.get_character_context(dict(scope,umo="",platform=""))
        if not character.get("available"):
            raise ValueError("角色全局设定不可用")
        self.job = {"status":"running","seed":seed,"started_at":time.time(),"identity":identity(scope)}
        self.task = asyncio.create_task(self._generate(scope,seed,names,speed,revision,character["fingerprint"]))
        return {"status":"running"}

    async def _generate(self, scope, seed, names, speed, revision, fingerprint):
        try:
            with tempfile.TemporaryDirectory(prefix="dynamics-world-map-") as scratch:
                output = Path(scratch)/"generated.json"
                self.process = await asyncio.create_subprocess_exec(sys.executable,str(Path(__file__).with_name("map_renderer.py")),
                    seed,str(output),self.plugin.textures.selected_path() if hasattr(self.plugin,'textures') else '',stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.PIPE)
                try:
                    _,error = await asyncio.wait_for(self.process.communicate(),180)
                except BaseException:
                    if self.process.returncode is None:
                        self.process.terminate()
                        try:
                            await asyncio.wait_for(self.process.wait(),8)
                        except TimeoutError:
                            self.process.kill();await self.process.wait()
                    raise
                if self.process.returncode or not output.is_file():
                    # No request body, local paths or arbitrary browser logs in the UI.
                    raise RuntimeError("地图生成失败，请检查 Playwright Chromium 和离线生成器资源")
                if output.stat().st_size > 30*1024*1024:
                    raise ValueError("生成结果超过限制")
                raw = json.loads(output.read_text("utf-8"))
                document = await asyncio.to_thread(convert,raw,seed,names,speed)
                current = await self.plugin.world.get_character_context(dict(scope,umo="",platform=""))
                if self.plugin._terminating or current.get("fingerprint")!=fingerprint:
                    raise ValueError("生成期间角色设定已变化，请重新生成")
                spatial=self.plugin.life.narrative.spatial
                with spatial.engine._db() as db:
                    old=spatial.document(db,identity(scope))
                if old and old.get("map_type")=="real":
                    from .geography import switch_mode
                    result=switch_mode(spatial,scope,"virtual",revision,document)
                else:
                    result = spatial.install(scope,document,revision)
                self.job.update(status="complete",result=result,finished_at=time.time())
        except asyncio.CancelledError:
            self.job.update(status="cancelled");raise
        except Exception as exc:
            self.job.update(status="failed",error=str(exc)[:180])
        finally:
            self.process = None

    def status(self, scope):
        return {k:v for k,v in self.job.items() if k!="identity"} if self.job.get("identity")==identity(scope) else {"status":"idle"}
