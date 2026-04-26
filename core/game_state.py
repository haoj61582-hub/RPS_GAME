from __future__ import annotations

import json

from core.player import Player
from core.rps_bag import generate_initial_bag
from utils.resources import data_path


DEFAULT_GAME_CONFIG = {
    "max_players": 2,
    "initial_health": 20,
    "initial_gold": 10,
    "initial_bag_size": 7,
    "initial_attack": 2,
    "initial_interest_rate": 0.2,
    "initial_shop_slots": 4,
    "port": 5555,
    "host": "0.0.0.0",
}


def load_game_config():
    try:
        with data_path("config.json").open(encoding="utf-8") as f:
            loaded = json.load(f)
    except Exception:
        loaded = {}

    config = dict(DEFAULT_GAME_CONFIG)
    config.update(loaded)
    return config

class GameState:
    def __init__(self, max_players: int | None = None):
        config = load_game_config()
        self.players: list[Player] = []
        self.current_round = 0
        self.max_players = max_players or int(config.get("max_players", 2))
        self.initial_health = int(config.get("initial_health", 20))
        self.initial_gold = int(config.get("initial_gold", 10))
        self.initial_bag_size = int(config.get("initial_bag_size", 7))
        self.initial_attack = int(config.get("initial_attack", 2))
        self.initial_interest_rate = float(config.get("initial_interest_rate", 0.2))
        self.initial_shop_slots = int(config.get("initial_shop_slots", 4))

    def add_player(self, player_id: str, name: str, faction: str = "rock"):
        bag_size = self.initial_bag_size
        bag = generate_initial_bag(bag_size)
        player = Player(
            id=player_id,
            name=name,
            faction=faction,
            health=self.initial_health,
            gold=self.initial_gold,
            bag_size=bag_size,
            attack=self.initial_attack,
            interest_rate=self.initial_interest_rate,
            shop_slots=self.initial_shop_slots,
            rps_bag=bag,
        )
        self.players.append(player)
        return player

    def remove_player(self, player_id: str):
        self.players = [p for p in self.players if p.id != player_id]

    def get_player_by_id(self, player_id: str):
        for p in self.players:
            if p.id == player_id:
                return p
        return None

    def alive_players(self):
        return [p for p in self.players if not p.is_eliminated]

    def is_game_over(self):
        return len(self.alive_players()) <= 1
