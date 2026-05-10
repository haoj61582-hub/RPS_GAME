from __future__ import annotations

import math
import socket
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext

from client.network_client import NetworkClient
from server.game_server import GameServer
from utils.resources import resource_path

APP_BG = "#07141B"
PANEL_BG = "#10232D"
CARD_BG = "#163340"
BORDER = "#2E5968"
TEXT = "#F3F5F7"
MUTED = "#92A6B2"
ACCENT = "#FFB454"
ACCENT_2 = "#49D4B1"
SUCCESS = "#85E89D"
WARNING = "#FFD166"
DANGER = "#FF7B72"

FACTIONS = {
    "rock": {
        "name": "磐岩壁垒",
        "title": "熔心守望",
        "style": "重甲 / 韧性 / 压迫",
        "subtitle": "由黑曜岩甲与余烬核心铸成的前线军团，风格稳重强硬，擅长正面碾压。",
        "motto": "裂岩不退，王座不让。",
        "accent": "#F2A65A",
    },
    "scissors": {
        "name": "迅刃风暴",
        "title": "影锋执裁",
        "style": "机动 / 猎杀 / 先手",
        "subtitle": "以翠锋双刃与疾影战法闻名的决斗派系，追求节奏、精度与一击制胜。",
        "motto": "风过无痕，锋至分胜负。",
        "accent": "#49D4B1",
    },
    "paper": {
        "name": "秘纸教团",
        "title": "白印议会",
        "style": "谋略 / 奥术 / 控局",
        "subtitle": "操纵符纸阵列与折叠秘术的法印教团，偏好用布局与资源差拿下全局。",
        "motto": "以墨定局，以印封喉。",
        "accent": "#E8D8A8",
    },
}


def detect_lan_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        sock.close()


def short_rps_name(choice):
    mapping = {"rock": "石头", "scissors": "剪刀", "paper": "布"}
    return mapping.get(choice, choice or "未知")


def rarity_name(rarity):
    mapping = {
        "common": "普通",
        "rare": "稀有",
        "epic": "史诗",
        "legendary": "传说",
    }
    return mapping.get((rarity or "").lower(), "普通")


def choice_accent(choice):
    mapping = {
        "rock": ACCENT,
        "scissors": ACCENT_2,
        "paper": WARNING,
        "none": MUTED,
        None: MUTED,
    }
    return mapping.get(choice, BORDER)


class BattlegroundApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RPS Battlegrounds")
        self.geometry("1320x860")
        self.minsize(1120, 760)
        self.configure(bg=APP_BG)

        self.player_name_var = tk.StringVar(value="玩家")
        self.host_port_var = tk.StringVar(value="5555")
        self.host_player_count_var = tk.StringVar(value="2")
        self.join_ip_var = tk.StringVar()
        self.join_port_var = tk.StringVar(value="5555")
        self.player_faction_var = tk.StringVar(value="rock")

        self.status_var = tk.StringVar(value="准备就绪")
        self.banner_var = tk.StringVar(value="三大阵营争夺竞技场王座")
        self.screen = "home"
        self.visual_assets = {}

        self.server = None
        self.client = None
        self.is_host = False
        self.share_ip = detect_lan_ip()
        self.share_port = 5555
        self.room_capacity = 2
        self.lobby_players = []
        self.awaiting_action = False
        self.selected_item_id = None
        self.latest_notice = "在左侧选择创建房间或加入房间，游戏开始后会自动进入战斗流程。"
        self.log_lines = []
        self.recent_feed = []
        self.final_result = None
        self.current_battle = None
        self.current_shop = None
        self.current_round_score = {"you": 0, "opponent": 0}
        self.last_round_snapshot = None
        self.last_match_snapshot = None
        self._rendered_screen = None
        self.guide_window = None
        self.phase_title = "待命中"
        self.phase_description = "先创建房间或加入房间，进入大厅后自动等待开局。"
        self.player_state = {
            "health": 20,
            "gold": 10,
            "bag_size": 7,
            "attack": 2,
            "interest_rate": 0.2,
            "win_streak": 0,
            "lose_streak": 0,
            "bag": {"rock": 0, "scissors": 0, "paper": 0},
            "health_overview": [],
            "owned_items": [],
            "owned_talents": [],
            "faction": "rock",
        }

        self._load_visual_assets()
        self._build_shell()
        self._render()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(120, self._poll_network)

    def _build_shell(self):
        header = tk.Frame(self, bg=APP_BG)
        header.pack(fill="x", padx=28, pady=(24, 10))

        title_col = tk.Frame(header, bg=APP_BG)
        title_col.pack(side="left", fill="x", expand=True)

        brand_row = tk.Frame(title_col, bg=APP_BG)
        brand_row.pack(anchor="w")
        crest = self.visual_assets.get("app_crest_small")
        if crest:
            tk.Label(brand_row, image=crest, bg=APP_BG).pack(side="left", padx=(0, 12))

        title_stack = tk.Frame(brand_row, bg=APP_BG)
        title_stack.pack(side="left")
        tk.Label(
            title_stack,
            text="RPS Battlegrounds",
            bg=APP_BG,
            fg=TEXT,
            font=("Avenir Next", 28, "bold"),
        ).pack(anchor="w")
        tk.Label(
            title_stack,
            textvariable=self.banner_var,
            bg=APP_BG,
            fg=MUTED,
            font=("Avenir Next", 12),
        ).pack(anchor="w", pady=(4, 0))

        badge = tk.Label(
            header,
            textvariable=self.status_var,
            bg=CARD_BG,
            fg=ACCENT,
            font=("Avenir Next", 11, "bold"),
            padx=18,
            pady=10,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        badge.pack(side="right")

        shell = tk.Frame(self, bg=APP_BG)
        shell.pack(fill="both", expand=True, padx=(28, 16), pady=(0, 20))

        self.page_canvas = tk.Canvas(
            shell,
            bg=APP_BG,
            highlightthickness=0,
            bd=0,
            relief="flat",
        )
        self.page_canvas.pack(side="left", fill="both", expand=True)

        self.page_scrollbar = tk.Scrollbar(
            shell,
            orient="vertical",
            command=self.page_canvas.yview,
            troughcolor=PANEL_BG,
            bg=CARD_BG,
            activebackground=ACCENT,
        )
        self.page_scrollbar.pack(side="right", fill="y", padx=(10, 0))

        self.page_canvas.configure(yscrollcommand=self.page_scrollbar.set)

        self.content = tk.Frame(self.page_canvas, bg=APP_BG)
        self.content_window = self.page_canvas.create_window(
            (0, 0),
            window=self.content,
            anchor="nw",
        )

        self.content.bind("<Configure>", self._on_content_configure)
        self.page_canvas.bind("<Configure>", self._on_canvas_configure)
        self.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        self.bind_all("<Button-4>", self._on_mousewheel, add="+")
        self.bind_all("<Button-5>", self._on_mousewheel, add="+")

    def _clear_content(self):
        for widget in self.content.winfo_children():
            widget.destroy()

    def _load_visual_assets(self):
        self.visual_assets = {
            "app_crest": self._load_photo("assets/icons/app_crest.png", max_width=112, max_height=112),
            "app_crest_small": self._load_photo("assets/icons/app_crest.png", max_width=46, max_height=46),
            "hero_banner": self._load_photo("assets/backgrounds/home_banner.png", max_width=1100, max_height=420),
            "factions": {
                "rock": {
                    "card": self._load_photo("assets/portraits/faction_rock.png", max_width=250, max_height=320),
                    "panel": self._load_photo("assets/portraits/faction_rock.png", max_width=210, max_height=280),
                    "lobby": self._load_photo("assets/portraits/faction_rock.png", max_width=110, max_height=140),
                },
                "scissors": {
                    "card": self._load_photo("assets/portraits/faction_scissors.png", max_width=250, max_height=320),
                    "panel": self._load_photo("assets/portraits/faction_scissors.png", max_width=210, max_height=280),
                    "lobby": self._load_photo("assets/portraits/faction_scissors.png", max_width=110, max_height=140),
                },
                "paper": {
                    "card": self._load_photo("assets/portraits/faction_paper.png", max_width=250, max_height=320),
                    "panel": self._load_photo("assets/portraits/faction_paper.png", max_width=210, max_height=280),
                    "lobby": self._load_photo("assets/portraits/faction_paper.png", max_width=110, max_height=140),
                },
            },
        }
        crest = self.visual_assets.get("app_crest")
        if crest:
            try:
                self.iconphoto(True, crest)
            except tk.TclError:
                pass

    def _load_photo(self, relative_path, max_width=None, max_height=None):
        path = resource_path(*relative_path.split("/"))
        if not path.exists():
            return None

        try:
            photo = tk.PhotoImage(file=str(path))
        except tk.TclError:
            return None

        width = photo.width() or 1
        height = photo.height() or 1
        shrink = 1
        if max_width and width > max_width:
            shrink = max(shrink, math.ceil(width / max_width))
        if max_height and height > max_height:
            shrink = max(shrink, math.ceil(height / max_height))
        if shrink > 1:
            photo = photo.subsample(shrink, shrink)
        return photo

    def _current_faction_id(self):
        faction_id = self.player_faction_var.get()
        if faction_id not in FACTIONS:
            faction_id = "rock"
        return faction_id

    def _faction_meta(self, faction_id=None):
        return FACTIONS.get(faction_id or self._current_faction_id(), FACTIONS["rock"])

    def _faction_image(self, faction_id, variant):
        return self.visual_assets.get("factions", {}).get(faction_id, {}).get(variant)

    def _set_faction(self, faction_id):
        if faction_id not in FACTIONS:
            return
        self.player_faction_var.set(faction_id)
        self.player_state["faction"] = faction_id
        if self.screen == "home":
            faction = self._faction_meta(faction_id)
            self.status_var.set(f"阵营已选择：{faction['name']}")
            self.banner_var.set(f"{faction['name']} 已整装待发，准备争夺竞技场王座")
        self._render()

    def _poll_network(self):
        if self.client:
            for message in self.client.poll_events():
                self._handle_message(message)
        self.after(120, self._poll_network)

    def _handle_message(self, message):
        msg_type = message.get("type")
        previous_health = self.player_state.get("health", 20)
        self._sync_player_state(message)
        player_name = self._local_player_name()

        if msg_type == "lobby_update":
            self.screen = "lobby"
            self.lobby_players = message.get("players", [])
            self.room_capacity = message.get("max_players", self.room_capacity)
            count = len(self.lobby_players)
            self.latest_notice = f"当前房间人数 {count}/{self.room_capacity}，满员后会自动开局。"
            self.status_var.set("大厅等待中")
            self.banner_var.set("分享房主 IP 给朋友后，对方即可直接加入")
            self._set_phase("联机大厅", f"已连接 {count}/{self.room_capacity} 名玩家，满员后自动进入战斗。")

        elif msg_type == "game_start":
            self.screen = "game"
            self.awaiting_action = False
            self.current_round_score = {"you": 0, "opponent": 0}
            self.last_round_snapshot = None
            self.last_match_snapshot = None
            players = " / ".join(message.get("players", []))
            self.latest_notice = f"全员已就位，战斗开始：{players}"
            self.status_var.set("战斗开始")
            self.banner_var.set("每一回合先对战，再进入商店补强阵容")
            self._append_log(self.latest_notice)
            self._add_feed_item("战斗开始", players, tone="accent")
            self._set_phase("开局阶段", "准备进入第一场对战，目标是抢先拿到小局优势。")

        elif msg_type == "choose_rps":
            self.screen = "game"
            if message.get("round_no", 1) == 1:
                self.current_round_score = {"you": 0, "opponent": 0}
                self.last_round_snapshot = None
            self.last_match_snapshot = None
            self.current_battle = {
                **message,
                "score_you": self.current_round_score.get("you", 0),
                "score_opponent": self.current_round_score.get("opponent", 0),
                "round_locked": False,
            }
            self.current_shop = None
            self.awaiting_action = False
            self.selected_item_id = None
            self.latest_notice = f"第 {message.get('round_no', 1)}/{message.get('max_rounds', 5)} 小局，对手：{message.get('opponent', '未知')}"
            self.status_var.set("请选择出拳")
            self._append_log(self.latest_notice)
            self._set_phase("对战阶段", "先选道具，再打出本小局拳型。率先 3 分，或在 5 小局后保持领先。")

            bag = message.get("bag", {})
            if not any(bag.get(choice, 0) > 0 for choice in ("rock", "scissors", "paper")):
                self.awaiting_action = True
                self.client.send_action({"choice": "none", "use_item": None})
                self._append_log("没有可用出拳，已自动跳过本小局。")

        elif msg_type == "round_result":
            winner = message.get("round_winner")
            self.current_round_score = {
                "you": message.get("score_you", 0),
                "opponent": message.get("score_opponent", 0),
            }
            if winner:
                self.latest_notice = f"小局胜者：{winner}，比分 {message.get('score_you', 0)}:{message.get('score_opponent', 0)}"
            else:
                self.latest_notice = f"本小局平局/无效，比分 {message.get('score_you', 0)}:{message.get('score_opponent', 0)}"
            self.status_var.set("回合结算")
            self.awaiting_action = True
            round_detail_parts = [
                f"你出 {short_rps_name(message.get('your_choice'))}，"
                f"对手出 {short_rps_name(message.get('opponent_choice'))}，"
                f"当前比分 {message.get('score_you', 0)}:{message.get('score_opponent', 0)}"
            ]
            if message.get("item_used_you"):
                round_detail_parts.append(f"你触发了 {message.get('item_used_you')}")
            if message.get("item_used_opponent"):
                round_detail_parts.append(f"对手触发了 {message.get('item_used_opponent')}")
            round_detail = "，".join(round_detail_parts)
            self._append_log(
                f"{round_detail}。{self.latest_notice}"
            )
            if winner == player_name:
                tone = "success"
                title = "你赢下了这一小局"
            elif winner is None:
                tone = "warning"
                title = "本小局未分胜负"
            else:
                tone = "danger"
                title = f"{winner} 赢下了这一小局"
            self.last_round_snapshot = {
                "title": title,
                "tone": tone,
                "round_no": message.get("round_no", 1),
                "max_rounds": message.get("max_rounds", 5),
                "your_choice": message.get("your_choice"),
                "opponent_choice": message.get("opponent_choice"),
                "score_you": message.get("score_you", 0),
                "score_opponent": message.get("score_opponent", 0),
                "item_used_you": message.get("item_used_you"),
                "item_used_opponent": message.get("item_used_opponent"),
                "opponent": (self.current_battle or {}).get("opponent", "对手"),
                "opponent_faction": message.get("opponent_faction"),
            }
            if self.current_battle:
                self.current_battle = {
                    **self.current_battle,
                    "score_you": message.get("score_you", 0),
                    "score_opponent": message.get("score_opponent", 0),
                    "round_locked": True,
                }
            self._add_feed_item(title, round_detail, tone=tone)
            self._set_phase("回合结算", "本小局结果已经揭示，旧输入已锁定。等待下一手开始，继续争夺比分优势。")

        elif msg_type == "match_result":
            result = message.get("result")
            result_map = {"win": "本场胜利", "lose": "本场失利", "draw": "本场平局"}
            self.current_battle = None
            self.awaiting_action = False
            self.last_round_snapshot = None
            self.latest_notice = f"{result_map.get(result, '本场结束')}，比分 {message.get('score_you', 0)}:{message.get('score_opponent', 0)}"
            self.status_var.set("对战结束")
            self._append_log(self.latest_notice)
            health_after = message.get("your_health", previous_health)
            health_loss = max(0, previous_health - health_after)
            health_text = f"承受 {health_loss} 点伤害" if health_loss else "血量未变化"
            match_detail = f"本场比分 {message.get('score_you', 0)}:{message.get('score_opponent', 0)}，{health_text}，当前血量 {health_after}"
            match_tone = {"win": "success", "lose": "danger", "draw": "warning"}.get(result, "accent")
            self.last_match_snapshot = {
                "title": result_map.get(result, "对战结束"),
                "tone": match_tone,
                "score_you": message.get("score_you", 0),
                "score_opponent": message.get("score_opponent", 0),
                "health_after": health_after,
                "health_loss": health_loss,
                "opponent_faction": message.get("opponent_faction"),
                "winner": message.get("winner"),
            }
            self._add_feed_item(result_map.get(result, "对战结束"), match_detail, tone=match_tone)
            self._set_phase("本场结束", "本场对战已经结算，接下来会进入经济结算与商店阶段。")

        elif msg_type == "state_update":
            phase = message.get("phase", "unknown")
            phase_text = {
                "post_match": "对战结束，等待经济结算",
                "round_income": "回合经济已结算",
                "bye": "本回合轮空，直接进入商店",
            }.get(phase, f"状态更新：{phase}")
            self.latest_notice = phase_text
            self._append_log(phase_text)
            if phase == "round_income":
                self.status_var.set("经济结算")
                income = message.get("income", {})
                income_detail = (
                    f"基础 +{income.get('base', 0)}，"
                    f"连胜/连败 +{income.get('streak', 0)}，"
                    f"利息 +{income.get('interest', 0)}，"
                    f"合计 +{income.get('total', 0)}"
                )
                self._add_feed_item("经济结算完成", income_detail, tone="accent")
                self._set_phase("经济结算", "本回合收益已经到账，准备进入商店继续成长。")
            elif phase == "bye":
                self._add_feed_item("本回合轮空", "你没有被匹配到对手，将直接进入商店。", tone="warning")
                self._set_phase("轮空回合", "这回合无需对战，可以直接规划商店消费。")
            else:
                self._set_phase("状态同步", phase_text)

        elif msg_type == "shop_menu":
            self.screen = "game"
            self.current_shop = message
            self.current_battle = None
            self.awaiting_action = False
            self.latest_notice = "商店已开启，选择购买、刷新，或直接结束商店阶段。"
            self.status_var.set("商店阶段")
            self._append_log("进入商店阶段。")
            self._add_feed_item("商店开启", f"当前金币 {message.get('gold', 0)}，可用槽位 {message.get('shop_slots', 4)}", tone="accent")
            self._set_phase("商店阶段", "购买道具与天赋，强化下一场对战的拳袋、经济与伤害。")

        elif msg_type == "shop_refresh":
            self.current_shop = {**(self.current_shop or {}), **message}
            self.awaiting_action = False
            self.latest_notice = f"商店已刷新，当前刷新费用 {message.get('refresh_cost', 1)} 金币。"
            self._append_log(self.latest_notice)
            self._add_feed_item("商店刷新", f"剩余金币 {message.get('gold', 0)}，下次刷新费用 {message.get('refresh_cost', 1)}", tone="warning")
            self._set_phase("商店阶段", "商店内容已更新，继续补强阵容或保存经济。")

        elif msg_type == "game_over":
            self.screen = "game_over"
            self.final_result = message
            self.current_battle = None
            self.current_shop = None
            self.awaiting_action = False
            self.last_round_snapshot = None
            self.status_var.set("对局结束")
            self.latest_notice = f"冠军诞生：{message.get('winner', '未知')}"
            self.banner_var.set("这场联机对局已经完成，可以返回首页重新开房")
            self._append_log(self.latest_notice)
            self._add_feed_item("冠军诞生", message.get("winner", "未知"), tone="success")
            self._set_phase("冠军诞生", "本局已经结束，可以回到首页开始新的联机对局。")

        elif msg_type == "connection_closed":
            if self.screen != "game_over":
                self.status_var.set("连接已关闭")
                self.latest_notice = "与服务器的连接已关闭。"
                self._append_log(self.latest_notice)
                self._set_phase("连接已关闭", "请返回首页重新建立房间，或再次加入其他房间。")

        self._render()

    def _sync_player_state(self, message):
        mapping = {
            "your_health": "health",
            "health": "health",
            "your_gold": "gold",
            "gold": "gold",
            "your_bag_size": "bag_size",
            "bag_size": "bag_size",
            "your_attack": "attack",
            "attack": "attack",
            "your_interest_rate": "interest_rate",
            "interest_rate": "interest_rate",
            "your_win_streak": "win_streak",
            "win_streak": "win_streak",
            "your_lose_streak": "lose_streak",
            "lose_streak": "lose_streak",
        }

        for source_key, target_key in mapping.items():
            if source_key in message:
                self.player_state[target_key] = message[source_key]

        if "bag" in message:
            self.player_state["bag"] = dict(message.get("bag", {}))
        if "health_overview" in message:
            self.player_state["health_overview"] = message.get("health_overview", [])
        if "owned_items" in message:
            self.player_state["owned_items"] = message.get("owned_items", [])
        if "owned_talents" in message:
            self.player_state["owned_talents"] = message.get("owned_talents", [])
        if "your_faction" in message and message.get("your_faction") in FACTIONS:
            self.player_state["faction"] = message["your_faction"]
            self.player_faction_var.set(message["your_faction"])

    def _append_log(self, line):
        if not line:
            return
        timestamp = time.strftime("%H:%M:%S")
        self.log_lines.append(f"[{timestamp}] {line}")
        self.log_lines = self.log_lines[-80:]

    def _local_player_name(self):
        return self.player_name_var.get().strip() or "玩家"

    def _set_phase(self, title, description):
        self.phase_title = title
        self.phase_description = description

    def _add_feed_item(self, title, detail, tone="accent"):
        self.recent_feed.insert(0, {
            "title": title,
            "detail": detail,
            "tone": tone,
        })
        self.recent_feed = self.recent_feed[:6]

    def _render(self):
        previous_screen = self._rendered_screen
        self._clear_content()

        if self.screen == "home":
            self._render_home()
        elif self.screen == "lobby":
            self._render_lobby()
        elif self.screen == "game":
            self._render_game()
        elif self.screen == "game_over":
            self._render_game_over()

        self._rendered_screen = self.screen
        self.after_idle(self._refresh_scroll_area)
        if previous_screen != self.screen:
            self.after_idle(lambda: self.page_canvas.yview_moveto(0))

    def _on_content_configure(self, _event):
        self._refresh_scroll_area()

    def _on_canvas_configure(self, event):
        self.page_canvas.itemconfigure(self.content_window, width=event.width)
        self._refresh_scroll_area()

    def _refresh_scroll_area(self):
        self.page_canvas.update_idletasks()
        self.page_canvas.configure(scrollregion=self.page_canvas.bbox("all"))

    def _page_can_scroll(self):
        first, last = self.page_canvas.yview()
        return first > 0 or last < 1

    def _compact_layout(self, threshold=1240):
        width = self.page_canvas.winfo_width() or self.winfo_width()
        return width < threshold

    def _widget_uses_own_scroll(self, widget):
        current = widget
        while current is not None:
            widget_class = current.winfo_class()
            if widget_class in {"Text", "Entry", "TEntry", "Scrollbar", "TScrollbar", "Spinbox"}:
                return True
            if current == self.content:
                break
            current = current.master
        return False

    def _on_mousewheel(self, event):
        if self._widget_uses_own_scroll(event.widget):
            return None

        if not self._page_can_scroll():
            return None

        if getattr(event, "num", None) == 4:
            step = -1
        elif getattr(event, "num", None) == 5:
            step = 1
        elif event.delta:
            step = int(-event.delta / 120) if abs(event.delta) >= 120 else (-1 if event.delta > 0 else 1)
        else:
            return None

        if step == 0:
            return None

        self.page_canvas.yview_scroll(step, "units")
        return "break"

    def _card(self, parent, title, subtitle=None):
        card = tk.Frame(
            parent,
            bg=PANEL_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
            padx=18,
            pady=16,
        )
        tk.Label(
            card,
            text=title,
            bg=PANEL_BG,
            fg=TEXT,
            font=("Avenir Next", 16, "bold"),
        ).pack(anchor="w")
        if subtitle:
            tk.Label(
                card,
                text=subtitle,
                bg=PANEL_BG,
                fg=MUTED,
                justify="left",
                wraplength=520,
                font=("Avenir Next", 11),
            ).pack(anchor="w", pady=(6, 0))
        body = tk.Frame(card, bg=PANEL_BG)
        body.pack(fill="both", expand=True, pady=(16, 0))
        return card, body

    def _action_button(self, parent, text, command, bg=ACCENT, fg=APP_BG, width=18):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=bg,
            activeforeground=fg,
            relief="flat",
            bd=0,
            padx=14,
            pady=10,
            width=width,
            cursor="hand2",
            font=("Avenir Next", 11, "bold"),
        )

    def _accent_color(self, tone):
        mapping = {
            "accent": ACCENT,
            "success": SUCCESS,
            "warning": WARNING,
            "danger": DANGER,
        }
        return mapping.get(tone, ACCENT)

    def _score_state_text(self, score_you, score_opponent):
        if score_you > score_opponent:
            return "你暂时领先"
        if score_you < score_opponent:
            return "对手暂时领先"
        return "当前比分持平"

    def _render_scoreboard(self, parent, score_you, score_opponent):
        board = tk.Frame(
            parent,
            bg=CARD_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
            padx=14,
            pady=12,
        )
        board.pack(fill="x", pady=(0, 14))

        top = tk.Frame(board, bg=CARD_BG)
        top.pack(fill="x")
        tk.Label(top, text="当前比分", bg=CARD_BG, fg=MUTED, font=("Avenir Next", 10, "bold")).pack(side="left")
        tk.Label(
            top,
            text=self._score_state_text(score_you, score_opponent),
            bg=CARD_BG,
            fg=TEXT,
            font=("Avenir Next", 10, "bold"),
        ).pack(side="right")

        score_row = tk.Frame(board, bg=CARD_BG)
        score_row.pack(fill="x", pady=(12, 0))

        def score_tile(container, label, score, color):
            tile = tk.Frame(
                container,
                bg=PANEL_BG,
                highlightbackground=color,
                highlightthickness=1,
                padx=16,
                pady=12,
            )
            tile.pack(side="left", fill="x", expand=True)
            tk.Label(tile, text=label, bg=PANEL_BG, fg=MUTED, font=("Avenir Next", 10, "bold")).pack(anchor="w")
            tk.Label(tile, text=str(score), bg=PANEL_BG, fg=color, font=("Avenir Next", 28, "bold")).pack(anchor="w", pady=(6, 0))

        score_tile(score_row, "你", score_you, SUCCESS if score_you >= score_opponent else TEXT)
        tk.Label(score_row, text="VS", bg=CARD_BG, fg=MUTED, font=("Avenir Next", 12, "bold"), padx=10).pack(side="left")
        score_tile(score_row, "对手", score_opponent, DANGER if score_opponent > score_you else TEXT)

    def _render_round_spotlight(self, parent):
        snapshot = self.last_round_snapshot
        if not snapshot:
            return

        tone_color = self._accent_color(snapshot.get("tone"))
        card = tk.Frame(
            parent,
            bg=CARD_BG,
            highlightbackground=tone_color,
            highlightthickness=1,
            padx=14,
            pady=12,
        )
        card.pack(fill="x", pady=(0, 14))

        top = tk.Frame(card, bg=CARD_BG)
        top.pack(fill="x")
        tk.Label(top, text="上一手回放", bg=CARD_BG, fg=MUTED, font=("Avenir Next", 10, "bold")).pack(side="left")
        tk.Label(
            top,
            text=snapshot.get("title", "小局结算"),
            bg=CARD_BG,
            fg=tone_color,
            font=("Avenir Next", 13, "bold"),
        ).pack(side="right")

        tk.Label(
            card,
            text=f"第 {snapshot.get('round_no', 1)}/{snapshot.get('max_rounds', 5)} 小局",
            bg=CARD_BG,
            fg=TEXT,
            font=("Avenir Next", 11),
        ).pack(anchor="w", pady=(8, 10))

        duel = tk.Frame(card, bg=CARD_BG)
        duel.pack(fill="x")

        def reveal_tile(container, title, choice, item_used):
            tile = tk.Frame(
                container,
                bg=PANEL_BG,
                highlightbackground=choice_accent(choice),
                highlightthickness=1,
                padx=12,
                pady=12,
            )
            tile.pack(side="left", fill="both", expand=True)
            tk.Label(tile, text=title, bg=PANEL_BG, fg=MUTED, font=("Avenir Next", 10, "bold")).pack(anchor="w")
            tk.Label(
                tile,
                text=short_rps_name(choice),
                bg=PANEL_BG,
                fg=choice_accent(choice),
                font=("Avenir Next", 18, "bold"),
            ).pack(anchor="w", pady=(8, 0))
            tk.Label(
                tile,
                text=f"道具：{item_used or '未触发'}",
                bg=PANEL_BG,
                fg=TEXT,
                justify="left",
                wraplength=220,
                font=("Avenir Next", 10),
            ).pack(anchor="w", pady=(8, 0))

        reveal_tile(duel, "你的出拳", snapshot.get("your_choice"), snapshot.get("item_used_you"))
        tk.Label(duel, text="VS", bg=CARD_BG, fg=MUTED, font=("Avenir Next", 12, "bold"), padx=10).pack(side="left")
        reveal_tile(duel, snapshot.get("opponent", "对手"), snapshot.get("opponent_choice"), snapshot.get("item_used_opponent"))

        tk.Label(
            card,
            text=f"比分更新为 {snapshot.get('score_you', 0)} : {snapshot.get('score_opponent', 0)}",
            bg=CARD_BG,
            fg=TEXT,
            font=("Avenir Next", 11, "bold"),
        ).pack(anchor="w", pady=(10, 0))

    def _render_match_spotlight(self, parent):
        snapshot = self.last_match_snapshot
        if not snapshot:
            return

        tone_color = self._accent_color(snapshot.get("tone"))
        card = tk.Frame(
            parent,
            bg=CARD_BG,
            highlightbackground=tone_color,
            highlightthickness=1,
            padx=14,
            pady=12,
        )
        card.pack(fill="x", pady=(0, 14))

        tk.Label(card, text="上一场战斗结算", bg=CARD_BG, fg=MUTED, font=("Avenir Next", 10, "bold")).pack(anchor="w")
        tk.Label(
            card,
            text=snapshot.get("title", "对战结束"),
            bg=CARD_BG,
            fg=tone_color,
            font=("Avenir Next", 16, "bold"),
        ).pack(anchor="w", pady=(8, 0))
        tk.Label(
            card,
            text=f"最终比分 {snapshot.get('score_you', 0)} : {snapshot.get('score_opponent', 0)}",
            bg=CARD_BG,
            fg=TEXT,
            font=("Avenir Next", 11, "bold"),
        ).pack(anchor="w", pady=(8, 0))

        health_loss = snapshot.get("health_loss", 0)
        health_line = f"你承受了 {health_loss} 点伤害" if health_loss else "这场战斗没有让你掉血"
        tk.Label(
            card,
            text=f"{health_line}，当前血量 {snapshot.get('health_after', 0)}",
            bg=CARD_BG,
            fg=TEXT,
            justify="left",
            wraplength=540,
            font=("Avenir Next", 11),
        ).pack(anchor="w", pady=(6, 0))

    def _open_guide(self):
        if self.guide_window and self.guide_window.winfo_exists():
            self.guide_window.lift()
            self.guide_window.focus_force()
            return

        self.guide_window = tk.Toplevel(self)
        self.guide_window.title("玩法说明")
        self.guide_window.geometry("760x620")
        self.guide_window.configure(bg=APP_BG)
        self.guide_window.transient(self)

        frame = tk.Frame(
            self.guide_window,
            bg=PANEL_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
            padx=24,
            pady=22,
        )
        frame.pack(fill="both", expand=True, padx=18, pady=18)

        tk.Label(
            frame,
            text="RPS Battlegrounds 玩法说明",
            bg=PANEL_BG,
            fg=TEXT,
            font=("Avenir Next", 22, "bold"),
        ).pack(anchor="w")
        tk.Label(
            frame,
            text="这是一个带 Rogue 成长系统的联机石头剪刀布游戏：每回合先对战，再用金币去商店成长。",
            bg=PANEL_BG,
            fg=MUTED,
            justify="left",
            wraplength=680,
            font=("Avenir Next", 12),
        ).pack(anchor="w", pady=(8, 18))

        sections = (
            ("1. 对战怎么赢", "每场对战最多 5 个小局，先拿到 3 分直接获胜；若打满 5 小局，则比分高的一方获胜。"),
            ("2. 出拳怎么选", "石头克剪刀，剪刀克布，布克石头。你的可选拳型取决于当前拳袋里的数量。"),
            ("3. 道具怎么用", "在对战阶段可以先选 1 个战斗道具，再点击要打出的拳型。不同道具会提供加拳、加分、重置等效果。"),
            ("4. 商店怎么成长", "每个大回合结束后会进入商店。你可以刷新、购买道具或天赋，提升经济、伤害、商店槽位和拳袋能力。"),
            ("5. 经济怎么滚", "每回合都会获得基础金币，还可能拿到连胜/连败奖励和利息收益。合理留钱会让后期更强。"),
            ("6. 联机怎么进房", "房主创建房间后把 IP 与端口发给其他玩家。所有玩家到齐后，房间会自动开始游戏。"),
        )

        for title, desc in sections:
            section = tk.Frame(frame, bg=CARD_BG, padx=16, pady=14, highlightbackground=BORDER, highlightthickness=1)
            section.pack(fill="x", pady=6)
            tk.Label(section, text=title, bg=CARD_BG, fg=ACCENT, font=("Avenir Next", 13, "bold")).pack(anchor="w")
            tk.Label(
                section,
                text=desc,
                bg=CARD_BG,
                fg=TEXT,
                justify="left",
                wraplength=640,
                font=("Avenir Next", 11),
            ).pack(anchor="w", pady=(6, 0))

        self._action_button(frame, "关闭说明", self.guide_window.destroy, bg=ACCENT_2, width=14).pack(anchor="e", pady=(18, 0))

    def _render_stat_tiles(self, parent, stat_specs, compact=False):
        columns = 3 if compact else max(1, len(stat_specs))
        for col in range(columns):
            parent.grid_columnconfigure(col, weight=1)

        for idx, (label, value, color) in enumerate(stat_specs):
            tile = tk.Frame(
                parent,
                bg=PANEL_BG,
                highlightbackground=BORDER,
                highlightthickness=1,
                padx=16,
                pady=12,
            )
            row = idx // columns
            col = idx % columns
            tile.grid(
                row=row,
                column=col,
                sticky="nsew",
                padx=(0, 10 if col < columns - 1 else 0),
                pady=(0, 10 if compact and row == 0 else 0),
            )
            tk.Label(tile, text=label, bg=PANEL_BG, fg=MUTED, font=("Avenir Next", 10, "bold")).pack(anchor="w")
            tk.Label(tile, text=str(value), bg=PANEL_BG, fg=color, font=("Avenir Next", 18, "bold")).pack(anchor="w", pady=(6, 0))

    def _render_phase_banner(self, parent, grid_kwargs=None):
        banner = tk.Frame(
            parent,
            bg=CARD_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
            padx=18,
            pady=14,
        )
        if grid_kwargs is None:
            banner.pack(fill="x", pady=(0, 16))
        else:
            banner.grid(**grid_kwargs)

        top = tk.Frame(banner, bg=CARD_BG)
        top.pack(fill="x")
        tk.Label(top, text="当前阶段", bg=CARD_BG, fg=MUTED, font=("Avenir Next", 10, "bold")).pack(side="left")
        tk.Label(top, text=self.phase_title, bg=CARD_BG, fg=ACCENT, font=("Avenir Next", 16, "bold")).pack(side="left", padx=(12, 0))
        faction_meta = self._faction_meta(self.player_state.get("faction"))
        tk.Label(
            top,
            text=f"{'房主' if self.is_host else '访客'} | {faction_meta['name']} | {self.share_ip}:{self.share_port}",
            bg=CARD_BG,
            fg=TEXT,
            font=("Avenir Next", 10, "bold"),
        ).pack(side="right")

        tk.Label(
            banner,
            text=self.phase_description,
            bg=CARD_BG,
            fg=TEXT,
            justify="left",
            wraplength=980,
            font=("Avenir Next", 11),
        ).pack(anchor="w", pady=(8, 0))

    def _render_recent_feed(self, parent):
        feed_card, feed_body = self._card(parent, "最近回顾", "这里会高亮最近几个关键节点，帮助你快速掌握局势。")
        feed_card.pack(fill="x", pady=(0, 12))

        if not self.recent_feed:
            tk.Label(
                feed_body,
                text="战斗开始后，最近回顾会显示在这里。",
                bg=PANEL_BG,
                fg=MUTED,
                font=("Avenir Next", 11),
            ).pack(anchor="w")
            return

        for entry in self.recent_feed:
            row = tk.Frame(
                feed_body,
                bg=CARD_BG,
                highlightbackground=BORDER,
                highlightthickness=1,
                padx=12,
                pady=10,
            )
            row.pack(fill="x", pady=4)

            accent = self._accent_color(entry.get("tone"))
            strip = tk.Frame(row, bg=accent, width=6, height=46)
            strip.pack(side="left", fill="y")

            text_col = tk.Frame(row, bg=CARD_BG)
            text_col.pack(side="left", fill="both", expand=True, padx=(12, 0))
            tk.Label(
                text_col,
                text=entry.get("title", "事件"),
                bg=CARD_BG,
                fg=TEXT,
                font=("Avenir Next", 11, "bold"),
            ).pack(anchor="w")
            tk.Label(
                text_col,
                text=entry.get("detail", ""),
                bg=CARD_BG,
                fg=MUTED,
                justify="left",
                wraplength=420,
                font=("Avenir Next", 10),
            ).pack(anchor="w", pady=(4, 0))

    def _render_faction_selector(self, parent, compact=False):
        faction_card, faction_body = self._card(
            parent,
            "选择阵营风格",
            "阵营会出现在大厅、血量榜和局内档案卡中，目前主要影响身份展示与视觉表达。",
        )
        faction_card.pack(fill="x", pady=(0, 18))

        grid = tk.Frame(faction_body, bg=PANEL_BG)
        grid.pack(fill="x")
        columns = 1 if compact else 3
        for col in range(columns):
            grid.grid_columnconfigure(col, weight=1)

        for idx, faction_id in enumerate(("rock", "scissors", "paper")):
            meta = self._faction_meta(faction_id)
            selected = self._current_faction_id() == faction_id
            card = tk.Frame(
                grid,
                bg=CARD_BG,
                highlightbackground=meta["accent"] if selected else BORDER,
                highlightthickness=2 if selected else 1,
                padx=14,
                pady=14,
            )
            row = idx if compact else 0
            col = 0 if compact else idx
            card.grid(
                row=row,
                column=col,
                sticky="nsew",
                padx=(0, 10 if not compact and col < columns - 1 else 0),
                pady=(0, 12 if compact and row < 2 else 0),
            )

            portrait = self._faction_image(faction_id, "card")
            if portrait:
                tk.Label(card, image=portrait, bg=CARD_BG).pack(anchor="center", pady=(0, 10))

            tk.Label(card, text=meta["name"], bg=CARD_BG, fg=TEXT, font=("Avenir Next", 15, "bold")).pack(anchor="w")
            tk.Label(card, text=meta["title"], bg=CARD_BG, fg=meta["accent"], font=("Avenir Next", 11, "bold")).pack(anchor="w", pady=(4, 0))
            tk.Label(card, text=meta["style"], bg=CARD_BG, fg=MUTED, font=("Avenir Next", 10, "bold")).pack(anchor="w", pady=(4, 0))
            tk.Label(
                card,
                text=meta["subtitle"],
                bg=CARD_BG,
                fg=TEXT,
                justify="left",
                wraplength=260 if not compact else 620,
                font=("Avenir Next", 11),
            ).pack(anchor="w", pady=(10, 0))
            tk.Label(
                card,
                text=meta["motto"],
                bg=CARD_BG,
                fg=MUTED,
                justify="left",
                wraplength=260 if not compact else 620,
                font=("Avenir Next", 10, "italic"),
            ).pack(anchor="w", pady=(8, 0))

            button = self._action_button(
                card,
                "当前阵营" if selected else "选择此阵营",
                lambda selected_id=faction_id: self._set_faction(selected_id),
                bg=meta["accent"],
                width=14,
            )
            if selected:
                button.configure(state="disabled", cursor="arrow", disabledforeground=APP_BG)
            button.pack(anchor="w", pady=(14, 0))

    def _render_faction_panel(self, parent):
        faction_id = self.player_state.get("faction", self._current_faction_id())
        meta = self._faction_meta(faction_id)
        faction_card, faction_body = self._card(parent, "当前阵营", f"{meta['name']} · {meta['title']}")
        faction_card.pack(fill="x", pady=(0, 12))

        row = tk.Frame(faction_body, bg=PANEL_BG)
        row.pack(fill="x")
        portrait = self._faction_image(faction_id, "panel")
        if portrait:
            tk.Label(row, image=portrait, bg=PANEL_BG).pack(side="left", padx=(0, 12))

        text_col = tk.Frame(row, bg=PANEL_BG)
        text_col.pack(side="left", fill="both", expand=True)
        tk.Label(text_col, text=meta["style"], bg=PANEL_BG, fg=meta["accent"], font=("Avenir Next", 11, "bold")).pack(anchor="w")
        tk.Label(
            text_col,
            text=meta["subtitle"],
            bg=PANEL_BG,
            fg=TEXT,
            justify="left",
            wraplength=260,
            font=("Avenir Next", 10),
        ).pack(anchor="w", pady=(6, 0))
        tk.Label(
            text_col,
            text=meta["motto"],
            bg=PANEL_BG,
            fg=MUTED,
            justify="left",
            wraplength=260,
            font=("Avenir Next", 10, "italic"),
        ).pack(anchor="w", pady=(8, 0))

    def _render_home(self):
        compact = self._compact_layout(1180)
        current_faction = self._faction_meta()

        hero, body = self._card(
            self.content,
            "三大阵营已集结，竞技场正在等待下一位挑战者",
            "房主会在本机启动服务器并自动加入房间；其他玩家只需要输入房主 IP 和端口即可入局。",
        )
        hero.pack(fill="x", pady=(0, 18))

        banner = self.visual_assets.get("hero_banner")
        if banner:
            tk.Label(body, image=banner, bg=PANEL_BG).pack(fill="x", pady=(0, 14))

        selection_strip = tk.Frame(
            body,
            bg=CARD_BG,
            highlightbackground=current_faction["accent"],
            highlightthickness=1,
            padx=14,
            pady=12,
        )
        selection_strip.pack(fill="x", pady=(0, 14))
        tk.Label(selection_strip, text="当前阵营", bg=CARD_BG, fg=MUTED, font=("Avenir Next", 10, "bold")).pack(anchor="w")
        tk.Label(selection_strip, text=f"{current_faction['name']} · {current_faction['title']}", bg=CARD_BG, fg=current_faction["accent"], font=("Avenir Next", 15, "bold")).pack(anchor="w", pady=(4, 0))
        tk.Label(selection_strip, text=current_faction["motto"], bg=CARD_BG, fg=TEXT, font=("Avenir Next", 11)).pack(anchor="w", pady=(6, 0))

        highlights = tk.Frame(body, bg=PANEL_BG)
        highlights.pack(fill="x")
        for label_text, color in (
            ("图形界面战斗", ACCENT),
            ("联机大厅等待", ACCENT_2),
            ("阵营视觉风格", current_faction["accent"]),
        ):
            chip = tk.Label(
                highlights,
                text=label_text,
                bg=color,
                fg=APP_BG,
                padx=14,
                pady=8,
                font=("Avenir Next", 10, "bold"),
            )
            chip.pack(side="left", padx=(0, 10))

        hero_actions = tk.Frame(body, bg=PANEL_BG)
        hero_actions.pack(fill="x", pady=(16, 0))
        self._action_button(hero_actions, "查看玩法说明", self._open_guide, bg=ACCENT_2, width=14).pack(side="left")

        self._render_faction_selector(self.content, compact=compact)

        grid = tk.Frame(self.content, bg=APP_BG)
        grid.pack(fill="both", expand=True)
        grid.grid_columnconfigure(0, weight=1)
        if not compact:
            grid.grid_columnconfigure(1, weight=1)

        host_card, host_body = self._card(
            grid,
            "创建房间",
            "适合你当房主。创建后会显示本机可分享地址，玩家满员自动开始。",
        )
        host_card.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(0, 10 if not compact else 0),
            pady=(0, 14 if compact else 0),
        )

        join_card, join_body = self._card(
            grid,
            "加入房间",
            "适合朋友输入房主的局域网地址后加入。若你们跨网络，需要先做端口转发或使用内网穿透。",
        )
        join_card.grid(
            row=1 if compact else 0,
            column=0 if compact else 1,
            sticky="nsew",
            padx=(0 if compact else 10, 0),
        )

        self._render_form_row(host_body, "玩家昵称", self.player_name_var)
        self._render_form_row(host_body, "房间端口", self.host_port_var)
        self._render_form_row(host_body, "房间人数", self.host_player_count_var)

        tk.Label(
            host_body,
            text=f"推荐分享地址：{self.share_ip}:{self.host_port_var.get() or '5555'}",
            bg=PANEL_BG,
            fg=ACCENT_2,
            font=("Avenir Next", 11, "bold"),
        ).pack(anchor="w", pady=(8, 12))
        tk.Label(
            host_body,
            text=f"出战阵营：{current_faction['name']} · {current_faction['style']}",
            bg=PANEL_BG,
            fg=current_faction["accent"],
            justify="left",
            font=("Avenir Next", 11, "bold"),
        ).pack(anchor="w", pady=(0, 12))

        self._action_button(host_body, "创建房间并加入", self._host_game).pack(anchor="w")

        self._render_form_row(join_body, "玩家昵称", self.player_name_var)
        self._render_form_row(join_body, "房主 IP", self.join_ip_var)
        self._render_form_row(join_body, "房主端口", self.join_port_var)
        tk.Label(
            join_body,
            text=f"加入时将携带阵营身份：{current_faction['name']}",
            bg=PANEL_BG,
            fg=current_faction["accent"],
            justify="left",
            font=("Avenir Next", 11, "bold"),
        ).pack(anchor="w", pady=(0, 12))
        self._action_button(join_body, "加入联机房间", self._join_game, bg=ACCENT_2).pack(anchor="w")

        tips, tips_body = self._card(
            self.content,
            "当前版本说明",
            "已经支持本地房主、联机加入、阵营视觉资源、战斗 UI、商店 UI 和游戏结束结算。若需要跨公网联机，请确保端口可达。",
        )
        tips.pack(fill="x", pady=(18, 0))

        for line in (
            "1. 房主先创建房间，把局域网 IP 和端口发给朋友。",
            "2. 双方可以先在首页选择阵营，阵营会同步到大厅与局内档案。",
            "3. 朋友在加入房间里填昵称、IP、端口后连接，满员后自动开局。",
        ):
            tk.Label(
                tips_body,
                text=line,
                bg=PANEL_BG,
                fg=TEXT,
                justify="left",
                font=("Avenir Next", 11),
            ).pack(anchor="w", pady=2)

    def _render_lobby(self):
        compact = self._compact_layout(1180)
        layout = tk.Frame(self.content, bg=APP_BG)
        layout.pack(fill="both", expand=True)
        layout.grid_columnconfigure(0, weight=1 if compact else 3)
        if not compact:
            layout.grid_columnconfigure(1, weight=2)

        lobby_card, lobby_body = self._card(
            layout,
            "联机大厅",
            "玩家满员后自动开始。房主可把下方地址分享给其他玩家。",
        )
        lobby_card.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(0, 10 if not compact else 0),
            pady=(0, 14 if compact else 0),
        )

        address = f"{self.share_ip}:{self.share_port}"
        tk.Label(
            lobby_body,
            text=f"分享地址：{address}",
            bg=PANEL_BG,
            fg=ACCENT,
            font=("Avenir Next", 16, "bold"),
        ).pack(anchor="w")

        btn_row = tk.Frame(lobby_body, bg=PANEL_BG)
        btn_row.pack(fill="x", pady=(14, 18))
        self._action_button(btn_row, "复制地址", self._copy_share_address, width=14).pack(side="left")
        self._action_button(
            btn_row,
            "返回首页",
            self._leave_session,
            bg=DANGER,
            fg=TEXT,
            width=14,
        ).pack(side="left", padx=(10, 0))

        tk.Label(
            lobby_body,
            text=self.latest_notice,
            bg=PANEL_BG,
            fg=TEXT,
            justify="left",
            wraplength=560,
            font=("Avenir Next", 12),
        ).pack(anchor="w", pady=(0, 16))

        for idx in range(max(self.room_capacity, len(self.lobby_players))):
            slot = tk.Frame(
                lobby_body,
                bg=CARD_BG,
                highlightbackground=BORDER,
                highlightthickness=1,
                padx=14,
                pady=12,
            )
            slot.pack(fill="x", pady=6)
            if idx < len(self.lobby_players):
                player = self.lobby_players[idx]
                row = tk.Frame(slot, bg=CARD_BG)
                row.pack(fill="x")
                faction_id = player.get("faction", "rock")
                portrait = self._faction_image(faction_id, "lobby")
                if portrait:
                    tk.Label(row, image=portrait, bg=CARD_BG).pack(side="left", padx=(0, 12))

                info = tk.Frame(row, bg=CARD_BG)
                info.pack(side="left", fill="both", expand=True)
                faction_meta = self._faction_meta(faction_id)
                tk.Label(
                    info,
                    text=f"{idx + 1}. {player.get('name', '未知玩家')}",
                    bg=CARD_BG,
                    fg=TEXT,
                    font=("Avenir Next", 13, "bold"),
                ).pack(anchor="w")
                tk.Label(
                    info,
                    text=f"{faction_meta['name']} · {faction_meta['title']}",
                    bg=CARD_BG,
                    fg=faction_meta["accent"],
                    font=("Avenir Next", 11, "bold"),
                ).pack(anchor="w", pady=(4, 0))
                tk.Label(
                    info,
                    text=f"生命值 {player.get('health', 20)}",
                    bg=CARD_BG,
                    fg=MUTED,
                    font=("Avenir Next", 11),
                ).pack(anchor="w", pady=(4, 0))
            else:
                tk.Label(
                    slot,
                    text=f"{idx + 1}. 等待玩家加入…",
                    bg=CARD_BG,
                    fg=MUTED,
                    font=("Avenir Next", 13),
                ).pack(anchor="w")

        log_card, log_body = self._card(
            layout,
            "对局日志",
            "这里会显示连接状态、房间变化和后续所有战斗播报。",
        )
        log_card.grid(
            row=1 if compact else 0,
            column=0 if compact else 1,
            sticky="nsew",
            padx=(0 if compact else 10, 0),
        )
        self._render_log(log_body, height=28)

    def _render_game(self):
        compact = self._compact_layout(1280)
        wrapper = tk.Frame(self.content, bg=APP_BG)
        wrapper.pack(fill="both", expand=True)
        wrapper.grid_columnconfigure(0, weight=1 if compact else 7)
        if not compact:
            wrapper.grid_columnconfigure(1, weight=5)

        self._render_phase_banner(
            wrapper,
            grid_kwargs={"row": 0, "column": 0, "columnspan": (1 if compact else 2), "sticky": "ew", "pady": (0, 16)},
        )

        top_stats = tk.Frame(wrapper, bg=APP_BG)
        top_stats.grid(row=1, column=0, columnspan=(1 if compact else 2), sticky="ew", pady=(0, 16))

        stat_specs = (
            ("生命", self.player_state.get("health", 0), DANGER),
            ("金币", self.player_state.get("gold", 0), WARNING),
            ("拳袋", self.player_state.get("bag_size", 0), ACCENT_2),
            ("伤害", self.player_state.get("attack", 0), ACCENT),
            ("利息", f"{int(self.player_state.get('interest_rate', 0) * 100)}%", TEXT),
            ("连胜/连败", f"{self.player_state.get('win_streak', 0)} / {self.player_state.get('lose_streak', 0)}", SUCCESS),
        )
        self._render_stat_tiles(top_stats, stat_specs, compact=compact)

        action_card, action_body = self._card(
            wrapper,
            "当前行动",
            self.latest_notice,
        )
        action_card.grid(
            row=2,
            column=0,
            sticky="nsew",
            padx=(0, 10 if not compact else 0),
            pady=(0, 14 if compact else 0),
        )

        if self.current_battle:
            self._render_battle_panel(action_body)
        elif self.current_shop:
            self._render_shop_panel(action_body)
        else:
            self._render_waiting_panel(action_body)

        side = tk.Frame(wrapper, bg=APP_BG)
        side.grid(
            row=3 if compact else 2,
            column=0 if compact else 1,
            sticky="nsew",
            padx=(0 if compact else 10, 0),
        )

        self._render_faction_panel(side)
        self._render_recent_feed(side)

        bag_card, bag_body = self._card(side, "出拳包", "每场对战会重置基础拳袋，商店和天赋会影响你能打出的组合。")
        bag_card.pack(fill="x", pady=(0, 12))
        for choice in ("rock", "scissors", "paper"):
            count = self.player_state.get("bag", {}).get(choice, 0)
            tk.Label(
                bag_body,
                text=f"{short_rps_name(choice)}：{count}",
                bg=PANEL_BG,
                fg=TEXT,
                font=("Avenir Next", 12),
            ).pack(anchor="w", pady=2)

        inventory_card, inventory_body = self._card(side, "道具与天赋", "商店购买结果会实时同步到这里。")
        inventory_card.pack(fill="x", pady=(0, 12))
        owned_items = self.player_state.get("owned_items", [])
        owned_talents = self.player_state.get("owned_talents", [])
        if owned_items:
            tk.Label(inventory_body, text="道具", bg=PANEL_BG, fg=ACCENT, font=("Avenir Next", 11, "bold")).pack(anchor="w")
            for item in owned_items[:6]:
                tk.Label(
                    inventory_body,
                    text=f"• {item.get('name', '未知')} [{rarity_name(item.get('rarity'))}]",
                    bg=PANEL_BG,
                    fg=TEXT,
                    justify="left",
                    wraplength=420,
                    font=("Avenir Next", 11),
                ).pack(anchor="w", pady=1)
        if owned_talents:
            tk.Label(inventory_body, text="天赋", bg=PANEL_BG, fg=ACCENT_2, font=("Avenir Next", 11, "bold")).pack(anchor="w", pady=(10, 0))
            for talent in owned_talents[:6]:
                tk.Label(
                    inventory_body,
                    text=f"• {talent.get('name', '未知')}",
                    bg=PANEL_BG,
                    fg=TEXT,
                    justify="left",
                    wraplength=420,
                    font=("Avenir Next", 11),
                ).pack(anchor="w", pady=1)
        if not owned_items and not owned_talents:
            tk.Label(
                inventory_body,
                text="还没有购买过道具或天赋。",
                bg=PANEL_BG,
                fg=MUTED,
                font=("Avenir Next", 11),
            ).pack(anchor="w")

        board_card, board_body = self._card(side, "全局血量榜", "实时查看其他玩家的存活状态。")
        board_card.pack(fill="both", expand=True, pady=(0, 12))
        overview = self.player_state.get("health_overview", [])
        if overview:
            for idx, player in enumerate(overview, start=1):
                state_text = "淘汰" if player.get("is_eliminated") else "存活"
                state_color = DANGER if player.get("is_eliminated") else SUCCESS
                faction_meta = self._faction_meta(player.get("faction", "rock"))
                row = tk.Frame(board_body, bg=PANEL_BG)
                row.pack(fill="x", pady=2)
                tk.Label(
                    row,
                    text=f"{idx}. {player.get('name', '未知')} · {faction_meta['name']}",
                    bg=PANEL_BG,
                    fg=TEXT,
                    font=("Avenir Next", 11, "bold"),
                ).pack(side="left")
                tk.Label(
                    row,
                    text=f"❤️ {player.get('health', 0)}  {state_text}",
                    bg=PANEL_BG,
                    fg=state_color,
                    font=("Avenir Next", 11),
                ).pack(side="right")
        else:
            tk.Label(board_body, text="暂时没有排行榜数据。", bg=PANEL_BG, fg=MUTED, font=("Avenir Next", 11)).pack(anchor="w")

        log_card, log_body = self._card(side, "战报日志")
        log_card.pack(fill="both", expand=True)
        self._render_log(log_body, height=12)

    def _render_game_over(self):
        self._render_phase_banner(self.content)

        result_card, result_body = self._card(
            self.content,
            f"冠军：{(self.final_result or {}).get('winner', '未知')}",
            "对局已经结束，可以返回首页继续新的一轮联机。",
        )
        result_card.pack(fill="both", expand=True)

        overview = (self.final_result or {}).get("health_overview", [])
        if overview:
            for idx, player in enumerate(overview, start=1):
                state_text = "淘汰" if player.get("is_eliminated") else "存活"
                faction_meta = self._faction_meta(player.get("faction", "rock"))
                tk.Label(
                    result_body,
                    text=f"{idx}. {player.get('name', '未知')} · {faction_meta['name']}  ❤️ {player.get('health', 0)}  {state_text}",
                    bg=PANEL_BG,
                    fg=TEXT if not player.get("is_eliminated") else MUTED,
                    font=("Avenir Next", 13),
                ).pack(anchor="w", pady=4)

        actions = tk.Frame(result_body, bg=PANEL_BG)
        actions.pack(anchor="w", pady=(20, 20))
        self._action_button(actions, "返回首页", self._leave_session).pack(side="left")
        self._action_button(actions, "退出程序", self._on_close, bg=DANGER, fg=TEXT).pack(side="left", padx=(10, 0))

        log_card, log_body = self._card(self.content, "本局日志")
        log_card.pack(fill="both", expand=True, pady=(18, 0))
        self._render_log(log_body, height=14)

    def _render_battle_panel(self, parent):
        msg = self.current_battle or {}

        top = tk.Frame(parent, bg=PANEL_BG)
        top.pack(fill="x", pady=(0, 16))
        opponent_line = f"对手：{msg.get('opponent', '未知')}"
        opponent_faction = msg.get("opponent_faction")
        if opponent_faction in FACTIONS:
            opponent_line = f"{opponent_line} · {self._faction_meta(opponent_faction)['name']}"
        tk.Label(
            top,
            text=f"{opponent_line} | 小局 {msg.get('round_no', 1)}/{msg.get('max_rounds', 5)}",
            bg=PANEL_BG,
            fg=ACCENT,
            font=("Avenir Next", 18, "bold"),
        ).pack(anchor="w")

        self._render_scoreboard(parent, msg.get("score_you", 0), msg.get("score_opponent", 0))
        self._render_round_spotlight(parent)

        items = msg.get("items", [])
        if items:
            tk.Label(
                parent,
                text="战斗道具（先点道具，再点出拳）",
                bg=PANEL_BG,
                fg=MUTED,
                font=("Avenir Next", 11, "bold"),
            ).pack(anchor="w", pady=(0, 8))

            item_wrap = tk.Frame(parent, bg=PANEL_BG)
            item_wrap.pack(fill="x", pady=(0, 14))
            for item in items:
                selected = self.selected_item_id == item.get("id")
                button = self._action_button(
                    item_wrap,
                    f"{item.get('name')} [{rarity_name(item.get('rarity'))}]",
                    lambda item_id=item.get("id"): self._toggle_item(item_id),
                    bg=ACCENT if selected else CARD_BG,
                    fg=APP_BG if selected else TEXT,
                    width=20,
                )
                button.pack(side="left", padx=(0, 8), pady=4)

        bag = msg.get("bag", {})
        choices = tk.Frame(parent, bg=PANEL_BG)
        choices.pack(fill="x", pady=(8, 8))
        round_locked = msg.get("round_locked", False)

        for choice, color in (
            ("rock", ACCENT),
            ("scissors", ACCENT_2),
            ("paper", WARNING),
        ):
            count = bag.get(choice, 0)
            button = self._action_button(
                choices,
                f"{short_rps_name(choice)}  x{count}",
                lambda choice_name=choice: self._submit_battle_choice(choice_name),
                bg=color,
                width=16,
            )
            if self.awaiting_action or count <= 0 or round_locked:
                button.configure(state="disabled", cursor="arrow")
            button.pack(side="left", padx=(0, 10), pady=8)

        tk.Label(
            parent,
            text=f"已选道具：{self._selected_item_name(items)}",
            bg=PANEL_BG,
            fg=TEXT,
            font=("Avenir Next", 12),
        ).pack(anchor="w", pady=(8, 0))

        if round_locked:
            tk.Label(
                parent,
                text="本小局结算中，旧输入已锁定。下一手开始后会自动解锁。",
                bg=PANEL_BG,
                fg=WARNING,
                font=("Avenir Next", 12, "italic"),
            ).pack(anchor="w", pady=(12, 0))
        elif self.awaiting_action:
            tk.Label(
                parent,
                text="已提交出拳，正在等待其他玩家…",
                bg=PANEL_BG,
                fg=MUTED,
                font=("Avenir Next", 12, "italic"),
            ).pack(anchor="w", pady=(12, 0))

    def _render_shop_panel(self, parent):
        msg = self.current_shop or {}
        self._render_match_spotlight(parent)

        header = tk.Frame(parent, bg=PANEL_BG)
        header.pack(fill="x", pady=(0, 12))

        tk.Label(
            header,
            text=f"当前刷新费用：{msg.get('refresh_cost', 1)} 金币 | 商店槽位：{msg.get('shop_slots', 4)}",
            bg=PANEL_BG,
            fg=ACCENT_2,
            font=("Avenir Next", 16, "bold"),
        ).pack(anchor="w")

        actions = tk.Frame(parent, bg=PANEL_BG)
        actions.pack(fill="x", pady=(0, 14))
        refresh_btn = self._action_button(actions, "刷新商店", lambda: self._submit_shop_choice("refresh"), bg=ACCENT_2)
        exit_btn = self._action_button(actions, "结束商店", lambda: self._submit_shop_choice("exit"), bg=DANGER, fg=TEXT)
        if self.awaiting_action:
            refresh_btn.configure(state="disabled", cursor="arrow")
            exit_btn.configure(state="disabled", cursor="arrow")
        refresh_btn.pack(side="left")
        exit_btn.pack(side="left", padx=(10, 0))

        offers_wrap = tk.Frame(parent, bg=PANEL_BG)
        offers_wrap.pack(fill="both", expand=True)
        offers_wrap.grid_columnconfigure(0, weight=1)
        offers_wrap.grid_columnconfigure(1, weight=1)

        offers = msg.get("offers", [])
        for idx, offer in enumerate(offers):
            offer_card = tk.Frame(
                offers_wrap,
                bg=CARD_BG,
                highlightbackground=BORDER,
                highlightthickness=1,
                padx=14,
                pady=14,
            )
            offer_card.grid(row=idx // 2, column=idx % 2, sticky="nsew", padx=6, pady=6)

            kind = "天赋" if offer.get("kind") == "talent" else rarity_name(offer.get("rarity"))
            tk.Label(
                offer_card,
                text=offer.get("name", "未知"),
                bg=CARD_BG,
                fg=TEXT,
                font=("Avenir Next", 14, "bold"),
            ).pack(anchor="w")
            tk.Label(
                offer_card,
                text=f"{kind} | 价格 {offer.get('cost', 0)} 金币",
                bg=CARD_BG,
                fg=ACCENT,
                font=("Avenir Next", 11, "bold"),
            ).pack(anchor="w", pady=(4, 6))
            tk.Label(
                offer_card,
                text=offer.get("description", ""),
                bg=CARD_BG,
                fg=MUTED,
                justify="left",
                wraplength=320,
                font=("Avenir Next", 11),
            ).pack(anchor="w")

            buy_btn = self._action_button(
                offer_card,
                "购买",
                lambda slot=idx: self._submit_shop_choice(f"slot_{slot}"),
                width=12,
            )
            if self.awaiting_action:
                buy_btn.configure(state="disabled", cursor="arrow")
            buy_btn.pack(anchor="w", pady=(12, 0))

        if not offers:
            tk.Label(parent, text="本轮没有可购买内容。", bg=PANEL_BG, fg=MUTED, font=("Avenir Next", 12)).pack(anchor="w")

    def _render_waiting_panel(self, parent):
        self._render_match_spotlight(parent)
        tk.Label(
            parent,
            text=self.latest_notice,
            bg=PANEL_BG,
            fg=TEXT,
            justify="left",
            wraplength=600,
            font=("Avenir Next", 14),
        ).pack(anchor="w")
        self._action_button(parent, "返回首页", self._leave_session, bg=DANGER, fg=TEXT, width=14).pack(anchor="w", pady=(18, 0))

    def _render_log(self, parent, height=16):
        log_box = scrolledtext.ScrolledText(
            parent,
            height=height,
            bg=APP_BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            bd=0,
            padx=12,
            pady=12,
            font=("Menlo", 11),
        )
        log_box.pack(fill="both", expand=True)
        log_box.insert("1.0", "\n".join(self.log_lines) if self.log_lines else "日志会显示在这里。")
        log_box.configure(state="disabled")

    def _render_form_row(self, parent, label_text, variable):
        frame = tk.Frame(parent, bg=PANEL_BG)
        frame.pack(fill="x", pady=(0, 12))
        tk.Label(
            frame,
            text=label_text,
            bg=PANEL_BG,
            fg=MUTED,
            font=("Avenir Next", 11, "bold"),
        ).pack(anchor="w", pady=(0, 6))
        entry = tk.Entry(
            frame,
            textvariable=variable,
            bg=APP_BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            bd=0,
            highlightbackground=BORDER,
            highlightthickness=1,
            font=("Avenir Next", 12),
        )
        entry.pack(fill="x", ipady=10)

    def _selected_item_name(self, items):
        if not self.selected_item_id:
            return "未选择"
        for item in items:
            if item.get("id") == self.selected_item_id:
                return item.get("name", "未知")
        return "未选择"

    def _toggle_item(self, item_id):
        if self.awaiting_action:
            return
        self.selected_item_id = None if self.selected_item_id == item_id else item_id
        self._render()

    def _submit_battle_choice(self, choice):
        if not self.client or self.awaiting_action:
            return
        try:
            self.client.send_action({
                "choice": choice,
                "use_item": self.selected_item_id,
            })
            self.awaiting_action = True
            self._append_log(
                f"已提交出拳：{short_rps_name(choice)}"
                + (f" + 道具 {self._selected_item_name((self.current_battle or {}).get('items', []))}" if self.selected_item_id else "")
            )
            self.status_var.set("等待对手中")
            self._render()
        except Exception as exc:
            messagebox.showerror("发送失败", str(exc))

    def _submit_shop_choice(self, choice):
        if not self.client or self.awaiting_action:
            return
        try:
            self.client.send_action({"choice": choice})
            self.awaiting_action = True
            if choice == "refresh":
                self._append_log("已请求刷新商店。")
            elif choice == "exit":
                self._append_log("已结束商店阶段。")
            else:
                self._append_log(f"已请求购买槽位 {choice.split('_')[-1]}.")
            self._render()
        except Exception as exc:
            messagebox.showerror("发送失败", str(exc))

    def _host_game(self):
        name = self.player_name_var.get().strip() or "玩家"
        port = self._parse_port(self.host_port_var.get())
        max_players = self._parse_player_count(self.host_player_count_var.get())
        if port is None or max_players is None:
            return

        self._leave_session(silent=True)

        try:
            self.server = GameServer(port=port, max_players=max_players)
            self.server.start()
            time.sleep(0.15)
            self.client = NetworkClient(
                name=name,
                host="127.0.0.1",
                port=port,
                faction=self._current_faction_id(),
            )
            self.client.connect()
        except Exception as exc:
            if self.server:
                self.server.stop()
                self.server = None
            messagebox.showerror("创建房间失败", str(exc))
            return

        self.is_host = True
        self.share_ip = detect_lan_ip()
        self.share_port = port
        self.room_capacity = max_players
        self.screen = "lobby"
        self.player_state["faction"] = self._current_faction_id()
        self.status_var.set("房间已创建")
        self.banner_var.set("房主已经加入房间，等待其他玩家连接")
        self.latest_notice = f"房间已创建，请将 {self.share_ip}:{port} 分享给其他玩家。"
        self._append_log(self.latest_notice)
        self._render()

    def _join_game(self):
        name = self.player_name_var.get().strip() or "玩家"
        ip = self.join_ip_var.get().strip()
        port = self._parse_port(self.join_port_var.get())
        if not ip:
            messagebox.showerror("缺少地址", "请输入房主 IP。")
            return
        if port is None:
            return

        self._leave_session(silent=True)

        try:
            self.client = NetworkClient(
                name=name,
                host=ip,
                port=port,
                faction=self._current_faction_id(),
            )
            self.client.connect()
        except Exception as exc:
            self.client = None
            messagebox.showerror("加入失败", str(exc))
            return

        self.is_host = False
        self.share_ip = ip
        self.share_port = port
        self.screen = "lobby"
        self.player_state["faction"] = self._current_faction_id()
        self.status_var.set("已连接服务器")
        self.banner_var.set("正在等待房间满员，游戏会自动开始")
        self.latest_notice = f"已连接到 {ip}:{port}，等待房主开局。"
        self._append_log(self.latest_notice)
        self._render()

    def _leave_session(self, silent=False):
        if self.client:
            self.client.close()
            self.client = None
        if self.server:
            self.server.stop()
            self.server = None

        self.screen = "home"
        self.is_host = False
        self.lobby_players = []
        self.awaiting_action = False
        self.selected_item_id = None
        self.current_battle = None
        self.current_shop = None
        self.current_round_score = {"you": 0, "opponent": 0}
        self.last_round_snapshot = None
        self.last_match_snapshot = None
        self.final_result = None
        self.recent_feed = []
        self.status_var.set("准备就绪")
        self.banner_var.set("三大阵营争夺竞技场王座")
        self.latest_notice = "在左侧选择创建房间或加入房间，游戏开始后会自动进入战斗流程。"
        self.player_state = {
            "health": 20,
            "gold": 10,
            "bag_size": 7,
            "attack": 2,
            "interest_rate": 0.2,
            "win_streak": 0,
            "lose_streak": 0,
            "bag": {"rock": 0, "scissors": 0, "paper": 0},
            "health_overview": [],
            "owned_items": [],
            "owned_talents": [],
            "faction": self._current_faction_id(),
        }
        self._set_phase("待命中", "先创建房间或加入房间，进入大厅后自动等待开局。")
        if not silent:
            self._append_log("已返回首页。")
        self._render()

    def _copy_share_address(self):
        address = f"{self.share_ip}:{self.share_port}"
        self.clipboard_clear()
        self.clipboard_append(address)
        self.status_var.set("地址已复制")
        self._append_log(f"已复制房间地址：{address}")
        self._render()

    def _parse_port(self, raw):
        try:
            port = int(raw)
            if 1 <= port <= 65535:
                return port
        except Exception:
            pass
        messagebox.showerror("端口错误", "端口必须是 1 到 65535 之间的数字。")
        return None

    def _parse_player_count(self, raw):
        try:
            count = int(raw)
            if 2 <= count <= 8:
                return count
        except Exception:
            pass
        messagebox.showerror("人数错误", "房间人数建议设置在 2 到 8 之间。")
        return None

    def _on_close(self):
        if self.client:
            self.client.close()
            self.client = None
        if self.server:
            self.server.stop()
            self.server = None
        self.destroy()


def launch_app():
    app = BattlegroundApp()
    app.mainloop()
