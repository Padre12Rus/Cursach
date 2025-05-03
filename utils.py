import json
import os
import base64
import asyncio
import tkinter as tk
from tkinter import simpledialog, messagebox
from PIL import Image, ImageTk

class ChatApp:
    def __init__(self, root, send_func):
        self.root = root
        self.send_func = send_func
        self.send_callback = None
        self.last_seen = {}
        self.username = self.load_username()
        self.root.title(f"P2P Chat - {self.username}")
        self.peers = self.load_chat_history()  # {nickname: [сообщения]}
        self.current_chat = None
        self.online_status = {}
        self.theme = "dark"
        self.setup_ui()
        asyncio.create_task(self.ping_loop())

    def load_username(self):
        if os.path.exists("user.json"):
            with open("user.json", "r") as f:
                return json.load(f)["username"]
        else:
            name = simpledialog.askstring("Имя", "Введите ваше имя:")
            with open("user.json", "w") as f:
                json.dump({"username": name}, f)
            return name

    def load_chat_history(self):
        if os.path.exists("chat_history.json"):
            with open("chat_history.json", "r") as f:
                return json.load(f)
        return {}

    def save_chat_history(self):
        with open("chat_history.json", "w") as f:
            json.dump(self.peers, f, indent=2, ensure_ascii=False)

    def setup_ui(self):
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.sidebar = tk.Frame(self.main_frame, width=100, bg='lightgray')
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)

        self.chat_list = tk.Listbox(self.sidebar)
        self.chat_list.pack(fill=tk.BOTH, expand=True)
        self.chat_list.bind("<<ListboxSelect>>", self.select_chat)

        self.new_chat_btn = tk.Button(self.sidebar, text="Новый чат", command=self.new_chat)
        self.new_chat_btn.pack(pady=5)

        self.delete_chat_btn = tk.Button(self.sidebar, text="Удалить чат", command=self.delete_chat)
        self.delete_chat_btn.pack(pady=5)

        self.theme_btn = tk.Button(self.sidebar, text="🎨 Тема", command=self.toggle_theme)
        self.theme_btn.pack(pady=5)

        self.chat_frame = tk.Frame(self.main_frame)
        self.chat_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.text_area = tk.Text(self.chat_frame, state='disabled')
        self.text_area.pack(fill=tk.BOTH, expand=True)
        self.text_area.drop_target_register(tk.DND_FILES)
        self.text_area.dnd_bind('<<Drop>>', self.on_file_drop)

        self.entry = tk.Entry(self.chat_frame)
        self.entry.pack(fill=tk.X, side=tk.LEFT, expand=True)

        self.send_file_btn = tk.Button(self.chat_frame, text="Отправить файл", command=self.send_file_dialog)
        self.send_file_btn.pack(side=tk.RIGHT)

        self.apply_theme()

    def toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"
        self.apply_theme()

    def apply_theme(self):
        if self.theme == "dark":
            bg = "black"
            fg = "lime"
            entry_bg = "#222"
            sidebar_bg = "gray20"
        else:
            bg = "white"
            fg = "black"
            entry_bg = "white"
            sidebar_bg = "lightgray"

        self.root.configure(bg=bg)
        self.main_frame.configure(bg=bg)
        self.sidebar.configure(bg=sidebar_bg)
        self.chat_frame.configure(bg=bg)
        self.text_area.configure(bg=bg, fg=fg)
        self.entry.configure(bg=entry_bg, fg=fg, insertbackground=fg)

    def new_chat(self):
        name = simpledialog.askstring("Новый чат", "Введите имя собеседника:")
        if name:
            if name not in self.peers:
                self.peers[name] = []
                self.chat_list.insert(tk.END, name)

    def delete_chat(self):
        selection = self.chat_list.curselection()
        if not selection:
            return
        name = self.chat_list.get(selection)
        confirm = messagebox.askyesno("Удалить чат", f"Удалить чат с {name}?")
        if confirm:
            del self.peers[name]
            self.chat_list.delete(selection)
            if self.current_chat == name:
                self.current_chat = None
                self.text_area.configure(state='normal')
                self.text_area.delete(1.0, tk.END)
                self.text_area.configure(state='disabled')
            self.save_chat_history()

    def select_chat(self, event):
        if not self.chat_list.curselection():
            return
        name = self.chat_list.get(self.chat_list.curselection())
        self.current_chat = name
        if name not in self.peers:
            self.peers[name] = []
        self.text_area.configure(state='normal')
        self.text_area.delete(1.0, tk.END)
        for msg in self.peers.get(name, []):
            self.text_area.insert(tk.END, msg + "\n")
        self.text_area.configure(state='disabled')

    async def send_message(self):
        msg = self.entry.get()
        if msg.strip():
            payload = {
                "from": self.username,
                "type": "text",
                "content": msg
            }
            if self.send_callback:
                try:
                    await self.send_callback(json.dumps(payload))
                except Exception as e:
                    print(f"[Ошибка отправки]: {e}")

    async def send_file(self, filename):
        if os.path.getsize(filename) > 10 * 1024 * 1024:
            messagebox.showerror("Файл слишком большой", "Максимальный размер — 10 МБ")
            return
        try:
            with open(filename, "rb") as f:
                data = base64.b64encode(f.read()).decode()
            payload = {
                "from": self.username,
                "type": "file",
                "filename": filename,
                "content": data
            }
            if self.send_callback:
                try:
                    await self.send_callback(json.dumps(payload))
                except Exception as e:
                    print(f"[Ошибка отправки]: {e}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось отправить файл: {e}")

    def on_file_drop(self, event):
        filepath = os.path.normpath(event.data.strip('{}'))
        if not os.path.isfile(filepath):
            return
        self.send_dropped_file(filepath)

    def send_dropped_file(self, filepath):
        if os.path.getsize(filepath) > 10 * 1024 * 1024:
            messagebox.showerror("Файл слишком большой", "Максимальный размер — 10 МБ")
            return
        filename = os.path.basename(filepath)
        try:
            with open(filepath, "rb") as f:
                data = base64.b64encode(f.read()).decode("utf-8")
            payload = {
                "from": self.username,
                "type": "file",
                "filename": filename,
                "content": data
            }
            if self.send_callback:
                try:
                    asyncio.create_task(self.send_callback(json.dumps(payload)))
                except Exception as e:
                    print(f"[Ошибка отправки]: {e}")
            self.append_message(f"Вы отправили файл: {filename}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось отправить файл: {e}")

    def on_message(self, raw):
        try:
            msg = json.loads(raw)
            if msg["type"] == "ping":
                import time
                self.online_status[msg["from"]] = True
                self.last_seen[msg["from"]] = time.time()
                self.refresh_chat_list()
                return
            if msg["type"] == "text":
                self.append_message(f"{msg['from']}: {msg['content']}", sender=msg['from'])
            elif msg["type"] == "file":
                filename = msg["filename"]
                b64data = msg["content"]
                folder = os.path.join("downloads", msg['from'])
                os.makedirs(folder, exist_ok=True)
                filepath = os.path.join(folder, filename)
                with open(filepath, "wb") as f:
                    f.write(base64.b64decode(b64data))
                self.append_message(f"{msg['from']} отправил файл: {filepath}", sender=msg['from'])
                if filename.lower().endswith((".png", ".jpg", ".jpeg")):
                    try:
                        img = Image.open(filepath)
                        img.thumbnail((200, 200))
                        tk_img = ImageTk.PhotoImage(img)
                        self.text_area.configure(state='normal')
                        self.text_area.image_create(tk.END, image=tk_img)
                        self.text_area.image_ref = tk_img  # prevent GC
                        self.text_area.insert(tk.END, "\n")
                        self.text_area.configure(state='disabled')
                    except Exception as e:
                        self.append_message(f"[Ошибка показа изображения] {e}", sender=msg['from'])
        except Exception as e:
            self.append_message(f"[Ошибка обработки сообщения] {e}")

    def append_message(self, msg, sender=None):
        if sender:
            if sender not in self.peers:
                self.peers[sender] = []
                self.chat_list.insert(tk.END, sender)
            self.peers[sender].append(msg)
            if self.current_chat == sender:
                self.text_area.configure(state='normal')
                self.text_area.insert(tk.END, msg + "\n")
                self.text_area.configure(state='disabled')
                self.text_area.see(tk.END)
        else:
            if self.current_chat:
                self.peers.setdefault(self.current_chat, []).append(msg)
            self.text_area.configure(state='normal')
            self.text_area.insert(tk.END, msg + "\n")
            self.text_area.configure(state='disabled')
            self.text_area.see(tk.END)
        self.save_chat_history()

    def send_file_dialog(self):
        from tkinter import filedialog
        filename = filedialog.askopenfilename()
        if filename:
            asyncio.create_task(self.send_file(filename))

    async def ping_loop(self):
        import time
        while True:
            await asyncio.sleep(10)
            payload = {
                "from": self.username,
                "type": "ping"
            }
            if self.send_callback:
                try:
                    await self.send_callback(json.dumps(payload))
                except Exception as e:
                    print(f"[Ошибка отправки]: {e}")
            now = time.time()
            for peer, ts in self.last_seen.items():
                if now - ts > 30:
                    self.online_status[peer] = False
            self.refresh_chat_list()

    def refresh_chat_list(self):
        # This method should refresh the chat list UI to reflect online statuses.
        # Implementation depends on UI design; here is a simple placeholder.
        self.chat_list.delete(0, tk.END)
        for peer in sorted(self.peers.keys()):
            status = " (online)" if self.online_status.get(peer) else " (offline)"
            self.chat_list.insert(tk.END, peer + status)

"""
utils.py

Функционал модуля устарел и размазан по storage.py (хранение) и ui.py (UI).
Файл оставлен, чтобы не ломались импорты старых скриптов.
"""