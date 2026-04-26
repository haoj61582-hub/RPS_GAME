from __future__ import annotations

import json
import socket
from typing import Any


def send_message(conn: socket.socket, data: dict[str, Any]) -> None:
    message = json.dumps(data).encode("utf-8")
    header = len(message).to_bytes(4, "big")
    conn.sendall(header + message)


def recv_exact(conn: socket.socket, size: int) -> bytes:
    data = b""
    while len(data) < size:
        chunk = conn.recv(size - len(data))
        if not chunk:
            raise ConnectionError("连接已关闭")
        data += chunk
    return data


def receive_message(conn: socket.socket) -> dict[str, Any]:
    try:
        length_bytes = recv_exact(conn, 4)
        length = int.from_bytes(length_bytes, "big")
        data_bytes = recv_exact(conn, length)
        return json.loads(data_bytes.decode("utf-8"))
    except Exception:
        return {}

