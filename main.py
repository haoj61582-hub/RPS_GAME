import sys

from client.game_client import start_client
from gui.app import launch_app
from server.game_server import start_server


def run_cli_mode():
    print("=== RPS Battlegrounds · CLI 模式 ===\n")
    print("1. 创建服务器（房主）")
    print("2. 加入游戏（客人）")
    mode = input("请选择 (1/2): ").strip()

    name = input("请输入你的玩家名称: ").strip() or "玩家"

    if mode == "1":
        start_server(name)
    elif mode == "2":
        ip = input("请输入房主IP地址 (直接回车 = 本机测试): ").strip() or "127.0.0.1"
        start_client(name, ip)
    else:
        print("输入错误，程序退出")


if __name__ == "__main__":
    if "--cli" in sys.argv:
        run_cli_mode()
    else:
        launch_app()
