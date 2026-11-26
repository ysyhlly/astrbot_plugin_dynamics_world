# astrbot_plugin_dynamics_world v0.23.0

## v0.23.0 — 2026-11-26

- **正式版发布（GA）**：整合全部 `v0.23.0-rc.x` 角色生活、3D 实况小屋、双地图与天气、安全/存储/性能优化。
- **3D 小屋与 CI 修复**：补齐 `src/cabin3d.js` 中 `THREE.Plane` 具名导入并重打 `cabin3d.min.js`，补充全量 `THREE.*` 绑定回归检查；`package.json` 声明 `"type": "module"` 以兼容 Node 20 CI。

## v0.23.0-rc.11 — 2026-11-26

- 修复 3D 像素小屋启动崩溃：`src/cabin3d.js` 补齐 `THREE.Plane` 具名导入与绑定，重新构建 `pages/world/cabin3d.min.js` 并将 `pages/world/pixel-cabin.js` 模块缓存参数升级至 `?v=homes.2`，补充 `THREE.*` / `T.*` 符号绑定回归检查。
- 规范与测试修复：清理 `life/service.py` 未使用导入并通过 `ruff` 静态门禁，同步 `tests/test_series_shared_coordination.py` 对 `NarrativeProviderBusy` 异常类型的断言。

## v0.23.0-rc.10 — 2026-11-25

- 安全加固（Batch 1）：世界模块 Web API 全面强制 `require_series_admin` 与 CSRF 校验。
- 数据与存储修复（Batch 2）：消除 `narrative` 事务自死锁并治理存储膨胀。
- 性能与渲染优化（Batch 3）：修复明信片资源泄漏、修正前缀缓存哈希与预算语义，降低 3D 场景阴影渲染开销。
- 工程与发布治理（Batch 4）：收紧发布打包过滤、解除 CI 版本钉死、统一时区与别名配置并同步系列共享资产。

## v0.23.0-rc.9 — 2026-11-24

- 彻底消除主事件循环同步阻塞：`weather.py`、`resident_runtime.py`、`narrative.py` 管理接口与 `web_api.py` 全部下沉 `asyncio.to_thread`，`narrative_outreach` 改用轻量 `_outreach_snapshot`，`VisualProfiles.assets()` 按 `(mtime_ns, size)` 缓存。
- 重排 `narrative_prompt` 前缀顺序（静态角色资料+静态世界前置，模式专属规则与易变字段下沉），恢复跨模式 Prompt Cache 命中；压缩居民私有人设并截断 `own_knowledge` 上限。
- 同步最新 `series_panels.py`（支持结构化 `retry_after` 与 `provider_circuit_remaining()`）。

## v0.23.0-rc.8 — 2026-11-22

- 接入全系列共享 `ProviderBudget` 并发池与遥测统计（`life/service.py` 与 `life/core/generator.py` 走 `series_llm_call`，繁忙时延后不计入自动失败）。
- 全面下沉主控共享配置（SSOT）：替换全部 13 处硬编码 `Asia/Shanghai` 为共享时区解析；支持 `reply_provider` 兜底、`exclude_groups` 运行时排除护栏与总控矩阵「主控排除」展示，以及 `quiet_hours` 主动外联自动抑制。
- 同步按语言拆包的 `series-messages.js` 轻加载器（完全兼容 `Object.assign(messages, ...)`）及统一 `series_panels.py`。

## v0.23.0-rc.7 — 2026-11-21

- 升级系列面板 v2 与 3D 实况小屋体验：新增「今日生活手账」（`journal_feed`）、联邦搜索/群控矩阵只读钩子、可选小屋主题（`cabin_style`）及今日剩余日程手动重生成。
- 合入跨群字节级一致 `system_prompt` / `contexts[0]` 前缀缓存分段与低信号群聊环境闲聊/主动外联门控优化。
- 修复世界手账角色串味与未绑定群放宽问题，统一 `UTC+8` 自然日边界与显式 `[start_ts, end_ts)` 透传，补齐 `pages/world/whale-art-credit.txt` CC BY-NC-SA 4.0 单独素材许可说明。

## v0.23.0-rc.6 — 2026-11-20

- 优化世界叙事与后台 Tick 的前缀缓存命中率与调用成本（DW-1..DW-3）。
- 按“由慢到快”重排叙事与居民提示词区块以提升前缀缓存复用。
- 消除夜间 30 分钟无变化的睡眠/主动外联空转循环，并收紧输出篇幅以降低 Token 消耗。

## v0.23.0-rc.5

支持在原版 AstrBot 4.29.4 的插件区域直接切换已更新的群间面板。入口和目标均需更新，左侧菜单保留入口。

沿用 RC 3 的 SDK 日志修复，CI 固定对话主控提交，覆盖房间状态投影和注册表联动。

世界快照与后台 I/O 通过 AstrBot SDK 记录诊断。慢操作继续记为 INFO，常规操作记为 DEBUG。安装包构建会拒绝任何待打包 Python 文件直接导入标准库 `logging` 或其子模块。

系列面板显示安装版本及源码短提交号。

整合角色生活、因果事件、居民互动、3D 小屋和花园、天气与见闻书架；保留会话作用域、主动分享额度与持久化保护。统一发布元数据与构建检查。

这是发布候选。需要 AstrBot 4.29.4 或兼容的 4.x 版本。安装前保存旧插件目录、配置及对应 plugin_data；停止目标插件后安装，保留数据库与配置，再启用并检查加载日志。

如升级失败，先停用新版本并保留故障现场与新产生的数据；恢复升级前的代码与相匹配的数据备份。不要直接把旧数据库覆盖到运行中的插件，也不要假设较旧版本能够读取新版本写入的数据。

本候选的测试结果见发布批次验证报告。自动化检查不等于真实 QQ 收发或真实模型对话验收。
