# 角色自主布置

房间布置属于场景状态，与不可变参考图片及基础外观档案分别保存。`world_scene_state.state.room_designs` 按现有角色/地图模式、房间 ID 隔离。家具只能由管理员登记；角色在允许布置的房间里可选择移动已有家具、摆放手边物品、调灯、开合窗帘及展示已写纸页。

原生全局日常模型可在 `world_action` 中使用：

- `move_furniture(target_id,position)`：移动已登记家具，需在对应房间；床/书桌/书柜耗时 10 分钟，其余 2 分钟。建筑设施不可移动，搬书桌前须关电脑。
- `place_item(target_id,position)`：一分钟内调整物品摆放，可放下随身物品；电脑只能关机后在原房间书桌上调整。
- `set_lighting(target_id=<room>,mode=bright|warm|dim|off)`：10 秒。
- `set_curtains(target_id=<room>,mode=open|half|closed)`：20 秒。
- `display_note(target_id=<notebook>,record_id,position)`：90 秒，将已经写成的纸页摊开展示。它是同一本纸本，不生成副本、相框、耗材或新正文；take/put 收起展示。

动作沿用现有流程的时间、暂停、取消、失败、恢复和版本检查。只有完成时才修改摆位并追加前后变化，保留最近 12 条布置摘要，完整步骤仍在场景事件表。取消不撤销已完成步骤。普通聊天仍不能提交共享世界动作，也不新增主动联系或生图权限。

`scene.room_designs` 提供已登记家具、允许位置、灯光、窗帘和变化记录。只有当前房间的布置进入聊天及视觉输入；当前状态优先于旧底图。物品外观保持固定，实际摆位优先于基础外观档案中的默认摆位。笔记页只用不可读笔迹表示，不自动将正文交给生图。

管理员可通过现有 `POST /scene` 注册：`action=room_design, umo, expected_revision, place_id, room_id, enabled, furniture=[{name,kind,position,movable}], lighting?, curtains?`。最多 12 件家具，类型 bed/desk/chair/bookcase/lamp/window/fixture。已有登记只接受 enabled 开关，调整通过动作完成，避免覆盖历史。面板显示当前房间的家具位置、设施和最近变化，并可暂停/允许布置。

初次上线仅登记既有底图中已经确认的家具，不强制启动一次装修，不改变位置、物品正文或已有作息。角色会在正常日常规划时按需要决定是否布置，并非定时强制改动。摆位使用房间内相对区域，尚不是精确尺寸的三维碰撞模拟。
