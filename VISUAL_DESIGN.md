# 固定画面设定

世界保存设计与生图条件，视觉工坊负责图片生成与交付。设计记录存于活动代际 SQLite 的 `world_visual_profiles` 表，按角色实例和地图模式隔离；房间布局按房间 ID，外观按物品 ID 绑定。修改不会重置物品状态或日常。

参考文件放在活动数据目录的 `visual-assets/`，`index.json` 是管理员安装的素材索引。每项有 `file`（本目录图片文件名）、`role`（`style` 或 `layout`）、`sha256`、`label`、`source_url`。运行时验证散列、大小和路径，不在聊天热路径联网下载；素材缺失会标记 `generation_ready=false`。素材及生成图不随插件代码发布。

视觉工坊 `generation.image_generation_settings.llm_tool_reference_allowed_dirs` 仅需加入该 `visual-assets` 目录，保留 `whitelist` 模式，不开放整个数据目录。不要使用会被清理的工作台上传文件或跨群生成历史作为长期底图。

管理面板“世界地图 → 房间与物品 → 画风与固定外观”支持参考图缩略图、放大预览、房间布局和物品外观编辑，以及上传/替换图片。每部分独立保存，轮询不会覆盖草稿；遇到版本冲突须重新载入。上传新增不可变素材，选入编辑区后再保存绑定；原图和其他设定保留，可重新选回。只读模式仍可预览。

`GET /visual?umo=...` 和地图响应 `scene.visual_profile` 包含设定、素材来源、地图模式及写权限。管理 API `POST /visual`（宿主鉴权、写开关、迁移锁、乐观版本检查）接受 `umo`、`expected_revision` 以及：

- `action=style, asset_ids=[...]`：最多两张画风图；空列表清除。
- `action=room, target_id=<房间>, asset_id=<布局图>, layout=<描述>`。
- `action=item, target_id=<物品>, appearance=<外观>, home_room_id=<默认房间>, placement=<摆放位置>`。
- `action=remove, kind=rooms|items, target_id=...`：解除绑定。

`POST /visual_asset` 接受 `umo,role,label,source_url,image_base64`，只允许静态 PNG/JPEG/WebP，最大 8 MB、约 1600 万像素，素材库最多 32 张；校验实际图片内容后写入随机文件名，原子更新索引。浏览器不传文件路径，不请求远程来源链接。`GET /visual_asset?umo=...&asset_id=...` 仅返回已注册且哈希有效的图片预览，最长边限制在 960×640 范围内，原文件仍供生图读取。

回复模型得到当前房间布局、可见/携带物品的固定外观，以及按“布局、画风”排序的参考文件路径；路径只供工具 `references` 使用，不写入画面描述。普通问答不强制配图。无工具时不授权生成。

底图锁定空间与家具，画风图只参考绘制方法。天气、光线、物品余量、开关机和携带状态优先于参考图；已移动物品不会继续出现在原桌面。生成图不自动更新固定设计，不构成新的见闻或场景事实。

这是生成模型的图像与文字约束，不能保证每个像素或每个角度绝对一致；严格布局渲染仍需要几何场景或受控合成。固定底图应由管理员明确替换，不能逐次用新生成图滚动替换以免累积漂移。
