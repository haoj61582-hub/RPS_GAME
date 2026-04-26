from __future__ import annotations

import socket
import threading
from queue import Empty, Queue
from uuid import uuid4

from utils.logger import log
from utils.network_protocol import receive_message, send_message

clients: dict[str, socket.socket] = {}
player_queues: dict[str, Queue] = {}


def reset_network_state():
    for conn in list(clients.values()):
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
    clients.clear()
    player_queues.clear()


def broadcast_message(data):
    disconnected = []
    for player_id, conn in list(clients.items()):
        try:
            send_message(conn, data)
        except Exception:
            disconnected.append(player_id)

    for player_id in disconnected:
        clients.pop(player_id, None)


def get_message(player_id, timeout=None):
    if player_id not in player_queues:
        return {}
    try:
        if timeout is None:
            return player_queues[player_id].get()
        return player_queues[player_id].get(timeout=timeout)
    except Empty:
        return {}


class NetworkServer:
    def __init__(self, host, port, game_state, on_player_join, on_player_disconnect=None):
        self.host = host
        self.port = port
        self.game_state = game_state
        self.on_player_join = on_player_join
        self.on_player_disconnect = on_player_disconnect
        self.server_socket = None
        self.stop_event = threading.Event()
        self.accept_thread = None

    def start(self):
        reset_network_state()
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(8)
        self.server_socket.settimeout(0.5)
        log(f"✅ 服务器已启动，端口 {self.port}，等待玩家加入...", "green")
        self.accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self.accept_thread.start()

    def stop(self):
        self.stop_event.set()
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
            self.server_socket = None
        reset_network_state()

    def _accept_loop(self):
        while not self.stop_event.is_set():
            if len(self.game_state.players) >= self.game_state.max_players:
                break

            try:
                conn, addr = self.server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            threading.Thread(
                target=self._handle_client,
                args=(conn, addr),
                daemon=True,
            ).start()

    def _handle_client(self, conn, addr):
        player_id = f"player_{uuid4().hex[:8]}"

        try:
            name_msg = receive_message(conn)
            if not name_msg:
                conn.close()
                return

            name = name_msg.get("name", f"玩家{len(self.game_state.players) + 1}")
            faction = name_msg.get("faction", "rock")
            player = self.game_state.add_player(player_id, name, faction)
            clients[player_id] = conn
            player_queues[player_id] = Queue()

            log(f"✅ {name} 加入游戏 ({addr[0]})", "green")
            self.on_player_join(player, conn)

            while not self.stop_event.is_set():
                msg = receive_message(conn)
                if msg:
                    player_queues[player_id].put(msg)
                else:
                    break
        finally:
            player = self.game_state.get_player_by_id(player_id)
            if player_id in player_queues:
                player_queues[player_id].put({"choice": "none", "__disconnected__": True})
            clients.pop(player_id, None)
            try:
                conn.close()
            except Exception:
                pass
            if self.on_player_disconnect and player:
                self.on_player_disconnect(player)
