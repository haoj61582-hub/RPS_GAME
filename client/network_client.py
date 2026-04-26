from __future__ import annotations

import socket
import threading
from queue import Empty, Queue

from utils.network_protocol import receive_message, send_message


class NetworkClient:
    def __init__(self, name: str, host: str, port: int, faction: str = "rock"):
        self.name = name
        self.host = host
        self.port = int(port)
        self.faction = faction
        self.socket = None
        self.reader_thread = None
        self.stop_event = threading.Event()
        self.events = Queue()
        self.connected = False

    def connect(self, timeout=5):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(timeout)
        self.socket.connect((self.host, self.port))
        self.socket.settimeout(None)
        send_message(self.socket, {"name": self.name, "faction": self.faction})
        self.connected = True
        self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader_thread.start()

    def close(self):
        self.stop_event.set()
        self.connected = False
        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None

    def poll_events(self):
        events = []
        while True:
            try:
                events.append(self.events.get_nowait())
            except Empty:
                break
        return events

    def send_action(self, data):
        if not self.connected or not self.socket:
            raise ConnectionError("尚未连接到服务器")
        send_message(self.socket, data)

    def _reader_loop(self):
        try:
            while not self.stop_event.is_set():
                message = receive_message(self.socket)
                if not message:
                    break
                self.events.put(message)
        finally:
            self.connected = False
            self.events.put({"type": "connection_closed"})
