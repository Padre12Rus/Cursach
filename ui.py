

"""
ui.py – Графический интерфейс (Tkinter)

Отвечает ТОЛЬКО за взаимодействие с пользователем.
* Сетью занимается network.P2PNetwork
* Файлами – storage.py
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
from typing import Dict, List, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from PIL import Image, ImageTk  # type: ignore

from network import P2PNetwork
from storage import (
    load_chat_history,
    load_user_config,
    save_chat_history,
    save_user_config,
)


class ChatApp:
    """Tk‑inter‑based UI слой."""

    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 МБ

    def __init__(self, root: tk.Tk, net: P2PNetwork) -> None:
        self.root = root
        self.net = net

        # ---------- State -------------------------------------------------
        self.username, self.theme = load_user_config()
        self.peers: Dict[str, List[str]] = load_chat_history()
        self.online: Dict[str, bool] = {}
        self.last_seen: Dict[str, float] = {}
        self.current_chat: Optional[str] = None

        # ---------- UI ----------------------------------------------------
        self._build_ui()
        self._apply_theme()
        self._refresh_chat_list()

        # ---------- Bg tasks ----------------------------------------------
        asyncio.create_task(self._ping_loop())

    # =====================================================================
    # UI helpers
    # =====================================================================

    def _build_ui(self) -> None:
        self.root.title(f"P2P Chat — {self.username}")

        self.main = tk.Frame(self.root)
        self.main.pack(fill=tk.BOTH, expand=True)

        # ---------- Sidebar -------------------------------------------
        self.sidebar = tk.Frame(self.main, width=120, bd=0, highlightthickness=0, relief="flat")
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)

        self.chat_list = tk.Listbox(self.sidebar)
        self.chat_list.pack(fill=tk.BOTH, expand=True)
        self.chat_list.configure(bd=0, highlightthickness=0, relief="flat")
        self.chat_list.bind("<<ListboxSelect>>", self._select_chat)

        tk.Button(self.sidebar, text="Новый чат", command=self._new_chat).pack(
            pady=4
        )
        tk.Button(self.sidebar, text="Удалить чат", command=self._delete_chat).pack(
            pady=4
        )
        tk.Button(self.sidebar, text="🎨 Тема", command=self._toggle_theme).pack(
            pady=4
        )

        # ---------- Chat area -----------------------------------------
        self.chat = tk.Frame(self.main, bd=0, highlightthickness=0, relief="flat")
        self.chat.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.text = tk.Text(self.chat, state="disabled", bd=0, highlightthickness=0, relief="flat", wrap="word")
        self.text.pack(padx=8, pady=8, fill=tk.BOTH, expand=True)

        # drag‑and‑drop (если доступно)
        try:
            self.text.drop_target_register(tk.DND_FILES)
            self.text.dnd_bind("<<Drop>>", self._on_file_drop)
        except Exception:
            pass

        bottom = tk.Frame(self.chat, bd=0, highlightthickness=0, relief="flat")
        bottom.pack(fill=tk.X, padx=8, pady=(0, 8))

        self.entry = tk.Entry(bottom, bd=0, highlightthickness=0, relief="flat")
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry.bind("<Return>", self._send_text)

        tk.Button(bottom, text="📎", command=self._select_file).pack(side=tk.RIGHT)

    # ---------- Theme ----------------------------------------------------

    def _toggle_theme(self) -> None:
        self.theme = "light" if self.theme == "dark" else "dark"
        self._apply_theme()
        save_user_config(self.username, self.theme)

    def _apply_theme(self) -> None:
        dark = self.theme == "dark"

        # Цвета
        bg, fg = ("#000000", "#00ff00") if dark else ("#ffffff", "#000000")
        entry_bg = "#222222" if dark else "#ffffff"
        sidebar_bg = "#1e1e1e" if dark else "#d3d3d3"
        widget_bg = sidebar_bg  # для Listbox и кнопок

        # Окна/фреймы
        for w in (self.root, self.main, self.chat):
            w.configure(bg=bg)
        self.sidebar.configure(bg=sidebar_bg)

        # Текстовая область и поле ввода
        self.text.configure(bg=bg, fg=fg, insertbackground=fg)
        self.entry.configure(bg=entry_bg, fg=fg, insertbackground=fg)

        # Список чатов
        self.chat_list.configure(bg=widget_bg, fg=fg, selectbackground="#444444" if dark else "#cccccc",
                                 highlightthickness=0, relief="flat")

        # Кнопки на сайдбаре
        for child in self.sidebar.winfo_children():
            if isinstance(child, tk.Button):
                child.configure(bg=widget_bg, fg=fg, activebackground=entry_bg, activeforeground=fg,
                                relief="flat", bd=0)

    # =====================================================================
    # Chat‑list helpers
    # =====================================================================

    def _refresh_chat_list(self) -> None:
        selected = (
            self.chat_list.get(self.chat_list.curselection()).lstrip("🟢🔴 ").strip()
            if self.chat_list.curselection()
            else None
        )
        self.chat_list.delete(0, tk.END)
        for peer in sorted(self.peers):
            status = "🟢" if self.online.get(peer) else "🔴"
            self.chat_list.insert(tk.END, f"{status} {peer}")
        if selected:
            for i in range(self.chat_list.size()):
                if (
                    self.chat_list.get(i).lstrip("🟢🔴 ").strip()
                    == selected
                ):
                    self.chat_list.selection_set(i)
                    break

    def _select_chat(self, _event=None) -> None:
        if not self.chat_list.curselection():
            return
        peer = self.chat_list.get(self.chat_list.curselection()).lstrip("🟢🔴 ").strip()
        self.current_chat = peer

        self.text.configure(state="normal")
        self.text.delete("1.0", tk.END)
        for line in self.peers.get(peer, []):
            self.text.insert(tk.END, line + "\n")
        self.text.configure(state="disabled")

    def _new_chat(self) -> None:
        name = simpledialog.askstring("Новый чат", "Имя собеседника:")
        if name:
            self.peers.setdefault(name, [])
            self.online.setdefault(name, False)
            self._refresh_chat_list()

    def _delete_chat(self) -> None:
        if not self.chat_list.curselection():
            return
        peer = self.chat_list.get(self.chat_list.curselection()).lstrip("🟢🔴 ").strip()
        if not messagebox.askyesno("Удалить чат", f"Удалить чат с {peer}?"):
            return
        self.peers.pop(peer, None)
        self.online.pop(peer, None)
        if self.current_chat == peer:
            self.current_chat = None
            self.text.configure(state="normal")
            self.text.delete("1.0", tk.END)
            self.text.configure(state="disabled")
        save_chat_history(self.peers)
        self._refresh_chat_list()

    # =====================================================================
    # Outgoing
    # =====================================================================

    def _send_text(self, _event=None) -> None:
        txt = self.entry.get().strip()
        if not txt or not self.current_chat:
            return
        self.entry.delete(0, tk.END)

        payload = {"from": self.username, "type": "text", "content": txt}
        self._append_msg(f"Вы: {txt}")
        asyncio.create_task(self.net.send(json.dumps(payload)))

    def _select_file(self) -> None:
        path = filedialog.askopenfilename()
        if path:
            self._send_file(path)

    def _on_file_drop(self, event) -> None:
        path = (
            event.data[1:-1] if event.data.startswith("{") and event.data.endswith("}") else event.data
        )
        path = os.path.normpath(path)
        if os.path.isfile(path):
            self._send_file(path)

    def _send_file(self, path: str) -> None:
        if os.path.getsize(path) > self.MAX_FILE_SIZE:
            messagebox.showerror("Файл слишком большой", "Максимальный размер — 10 МБ")
            return
        filename = os.path.basename(path)
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        payload = {
            "from": self.username,
            "type": "file",
            "filename": filename,
            "content": data,
        }
        self._append_msg(f"Вы отправили файл: {filename}")
        asyncio.create_task(self.net.send(json.dumps(payload)))

    # =====================================================================
    # Incoming
    # =====================================================================

    def handle_incoming(self, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except Exception as e:
            self._append_msg(f"[Ошибка разбора JSON] {e}")
            return

        mtype = msg.get("type")
        if mtype == "ping":
            import time

            self.online[msg["from"]] = True
            self.last_seen[msg["from"]] = time.time()
            self._refresh_chat_list()
            return

        if mtype == "text":
            self._append_msg(f"{msg['from']}: {msg['content']}", sender=msg["from"])
        elif mtype == "file":
            self._handle_incoming_file(msg)
        else:
            self._append_msg(f"[Неизвестный тип] {mtype}")

    def _handle_incoming_file(self, msg: dict) -> None:
        filename = msg["filename"]
        folder = os.path.join("downloads", msg["from"])
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, filename)
        try:
            with open(path, "wb") as f:
                f.write(base64.b64decode(msg["content"]))
            self._append_msg(f"{msg['from']} отправил файл: {path}", sender=msg["from"])
            if filename.lower().endswith((".png", ".jpg", ".jpeg")):
                self._show_image(path)
        except Exception as e:
            self._append_msg(f"[Ошибка сохранения файла] {e}", sender=msg["from"])

    def _show_image(self, path: str) -> None:
        try:
            img = Image.open(path)
            img.thumbnail((200, 200))
            tk_img = ImageTk.PhotoImage(img)
            self.text.configure(state="normal")
            self.text.image_create(tk.END, image=tk_img)
            # сохраняем ссылку, чтобы TK не удалил изображение из памяти
            getattr(self.text, "_images", []).append(tk_img)  # type: ignore
            self.text.insert(tk.END, "\n")
            self.text.configure(state="disabled")
            self.text.see(tk.END)
        except Exception as e:
            self._append_msg(f"[Ошибка показа изображения] {e}")

    # =====================================================================
    # Misc helpers
    # =====================================================================

    def _append_msg(self, msg: str, sender: Optional[str] = None) -> None:
        if sender:
            self.peers.setdefault(sender, []).append(msg)
            self.online[sender] = True
        else:
            if self.current_chat:
                self.peers.setdefault(self.current_chat, []).append(msg)

        if not sender or sender == self.current_chat:
            self.text.configure(state="normal")
            self.text.insert(tk.END, msg + "\n")
            self.text.configure(state="disabled")
            self.text.see(tk.END)

        save_chat_history(self.peers)
        self._refresh_chat_list()

    async def _ping_loop(self) -> None:
        import time

        while True:
            await asyncio.sleep(10)
            await self.net.send(json.dumps({"from": self.username, "type": "ping"}))
            now = time.time()
            for peer, ts in list(self.last_seen.items()):
                if now - ts > 30:
                    self.online[peer] = False
            self._refresh_chat_list()