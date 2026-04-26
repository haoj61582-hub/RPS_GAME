# RPS Battlegrounds

一个带有 Rogue 成长系统的联机石头剪刀布游戏桌面版。

## 已实现

- 图形化主界面
- 房主创建房间并自动加入
- 访客通过 IP + 端口加入
- 联机大厅等待与房间人数展示
- 战斗出拳按钮与道具选择
- 商店购买、刷新、退出
- 游戏结束结算页
- macOS `.app` 打包脚本

## 运行

```bash
cd /Users/jiahao/Desktop/Game/rock_paper_scissor
python3 main.py
```

如果你还想使用旧的终端模式：

```bash
python3 main.py --cli
```

## 打包 macOS App

```bash
cd /Users/jiahao/Desktop/Game/rock_paper_scissor
./build_macos_app.sh
```

打包成功后，应用会出现在 `dist/RPSBattlegrounds.app`。

## 联机说明

- 房主先创建房间，然后把本机局域网 IP 和端口发给其他玩家。
- 其他玩家输入相同端口和房主 IP 即可加入。
- 如果需要跨公网联机，需要自己做端口映射或内网穿透。

