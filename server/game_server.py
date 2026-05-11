from __future__ import annotations

import threading
import time
import random

from core.battle import run_match
from core.game_state import GameState, load_game_config
from core.shop import show_shop
from server.network import NetworkServer, broadcast_message, clients, send_message
from utils.logger import log


def _build_health_overview(players):
    return [
        {
            "name": p.name,
            "health": p.health,
            "is_eliminated": p.is_eliminated,
            "faction": getattr(p, "faction", "rock"),
        }
        for p in players
    ]


def _round_income(player):
    base_income = 5
    streak_bonus = 2 if max(player.win_streak, player.lose_streak) >= 2 else 0
    interest_income = min(5, int(player.gold * player.interest_rate))
    total_income = base_income + streak_bonus + interest_income
    return {
        "base": base_income,
        "streak": streak_bonus,
        "interest": interest_income,
        "total": total_income,
    }


def _has_talent_effect(player, effect_type):
    for talent in player.talents:
        effect = talent.get("effect", {})
        if effect.get("type") == effect_type:
            return True
    return False


def _send_state_update(player, players, phase):
    conn = clients.get(player.id)
    if not conn:
        return

    send_message(conn, {
        "type": "state_update",
        "phase": phase,
        "your_health": player.health,
        "your_gold": player.gold,
        "your_bag_size": player.bag_size,
        "your_attack": player.attack,
        "your_interest_rate": player.interest_rate,
        "your_win_streak": player.win_streak,
        "your_lose_streak": player.lose_streak,
        "your_faction": getattr(player, "faction", "rock"),
        "health_overview": _build_health_overview(players),
    })


class GameServer:
    def __init__(self, host="0.0.0.0", port=None, max_players=2):
        config = load_game_config()
        self.host = host
        self.port = port or int(config.get("port", 5555))
        self.game_state = GameState(max_players=max_players)
        self.network_server = NetworkServer(
            self.host,
            self.port,
            self.game_state,
            self._on_player_join,
            self._on_player_disconnect,
        )
        self.game_thread = None
        self.game_started = False
        self.game_finished = threading.Event()
        self.stopped = threading.Event()

    def start(self):
        self.network_server.start()

    def stop(self):
        if self.stopped.is_set():
            return
        self.stopped.set()
        self.network_server.stop()

    def wait(self):
        while not self.stopped.is_set():
            time.sleep(0.1)

    def _broadcast_lobby_update(self):
        players = [
            {
                "name": player.name,
                "health": player.health,
                "is_eliminated": player.is_eliminated,
                "faction": getattr(player, "faction", "rock"),
            }
            for player in self.game_state.players
        ]
        broadcast_message({
            "type": "lobby_update",
            "players": players,
            "connected_count": len(players),
            "max_players": self.game_state.max_players,
            "status": "starting" if len(players) >= self.game_state.max_players else "waiting",
            "port": self.port,
        })

    def _on_player_join(self, player, conn):
        log(
            f"✅ {player.name} 加入游戏 ({len(self.game_state.players)}/{self.game_state.max_players})",
            "green",
        )
        self._broadcast_lobby_update()

        if len(self.game_state.players) == self.game_state.max_players and not self.game_started:
            self.game_started = True
            broadcast_message({
                "type": "game_start",
                "players": [p.name for p in self.game_state.players],
                "max_players": self.game_state.max_players,
            })
            self.game_thread = threading.Thread(target=self.game_loop, daemon=True)
            self.game_thread.start()

    def _on_player_disconnect(self, player):
        if self.stopped.is_set() or self.game_finished.is_set():
            return

        if not self.game_started:
            log(f"⚠️ {player.name} 在大厅中断开连接", "yellow")
            self.game_state.remove_player(player.id)
            self._broadcast_lobby_update()
            return

        if not player.is_eliminated:
            player.health = 0
            player.is_eliminated = True
            log(f"⚠️ {player.name} 已断线并被判定淘汰", "yellow")

    def game_loop(self):
        while not self.game_state.is_game_over() and not self.stopped.is_set():
            self.game_state.current_round += 1
            log(f"\n=== 第 {self.game_state.current_round} 大回合 ===", "cyan")

            alive = [p for p in self.game_state.players if not p.is_eliminated]
            if len(alive) <= 1:
                break

            random.shuffle(alive)
            matches = []
            for i in range(0, len(alive) - 1, 2):
                matches.append((alive[i], alive[i + 1]))

            if len(alive) % 2 == 1:
                bye = alive[-1]
                log(f"👋 {bye.name} 本轮轮空，直接进入商店", "yellow")
                _send_state_update(bye, self.game_state.players, "bye")

            for p1, p2 in matches:
                winner, loser, is_draw = run_match(p1, p2)

                if is_draw:
                    log(f"🤝 {p1.name} 与 {p2.name} 平局，双方不掉血", "yellow")
                    p1.win_streak = 0
                    p1.lose_streak = 0
                    p2.win_streak = 0
                    p2.lose_streak = 0
                else:
                    winner.win_streak += 1
                    winner.lose_streak = 0
                    loser.lose_streak += 1
                    loser.win_streak = 0

                _send_state_update(p1, self.game_state.players, "post_match")
                _send_state_update(p2, self.game_state.players, "post_match")

            for player in list(alive):
                if player.is_eliminated:
                    continue
                income = _round_income(player)
                player.gold += income["total"]
                conn = clients.get(player.id)
                if conn:
                    send_message(conn, {
                        "type": "state_update",
                        "phase": "round_income",
                        "your_health": player.health,
                        "your_gold": player.gold,
                        "your_bag_size": player.bag_size,
                        "your_attack": player.attack,
                        "your_interest_rate": player.interest_rate,
                        "your_win_streak": player.win_streak,
                        "your_lose_streak": player.lose_streak,
                        "your_faction": getattr(player, "faction", "rock"),
                        "income": income,
                        "health_overview": _build_health_overview(self.game_state.players),
                    })

            log("\n=== 商店阶段 ===", "yellow")
            for player in list(alive):
                if not player.is_eliminated:
                    show_shop(player, _build_health_overview(self.game_state.players))

        winner = next((p for p in self.game_state.players if not p.is_eliminated), None)
        winner_name = winner.name if winner else "未知"
        self.game_finished.set()
        log(f"\n🏆 游戏结束！最终胜利者是：{winner_name} 🎉", "green")

        broadcast_message({
            "type": "game_over",
            "winner": winner_name,
            "health_overview": _build_health_overview(self.game_state.players),
        })
        time.sleep(0.5)
        self.stop()


def start_server(host_name, bind_host="0.0.0.0", port=None, max_players=2):
    server = GameServer(host=bind_host, port=port, max_players=max_players)
    server.start()
    try:
        server.wait()
    except KeyboardInterrupt:
        log("\n🛑 服务器主动关闭...", "red")
        server.stop()
