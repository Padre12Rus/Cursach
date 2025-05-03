"""
storage.py – Все операции чтения/записи на диск
"""

from __future__ import annotations

import json
import os
from typing import Dict, List, Tuple

_USER_FILE = "user.json"
_CHAT_FILE = "chat_history.json"

# ---------- User config ------------------------------------------------------

def load_user_config() -> Tuple[str, str]:
    """
    Возвращает (username, theme).  При отсутствии файла создаёт его.

    Theme по умолчанию – "dark".
    """
    if os.path.exists(_USER_FILE):
        with open(_USER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data["username"], data.get("theme", "dark")

    name = input("Введите ваше имя: ").strip() or "Anonymous"
    data = {"username": name, "theme": "dark"}
    with open(_USER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return name, "dark"


def save_user_config(username: str, theme: str) -> None:
    with open(_USER_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"username": username, "theme": theme},
            f,
            ensure_ascii=False,
            indent=2,
        )

# ---------- Chat history -----------------------------------------------------

def load_chat_history() -> Dict[str, List[str]]:
    if os.path.exists(_CHAT_FILE):
        with open(_CHAT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_chat_history(history: Dict[str, List[str]]) -> None:
    with open(_CHAT_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)