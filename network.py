"""
network.py – Сетевой уровень P2P‑чата

В этом модуле собрана ВСЯ логика работы по WebSocket, полностью изолированная
от GUI и диска.  UI-слой передаёт сюда callback, который вызывается на каждое
входящее сообщение.

Использование
-------------
net = P2PNetwork()
await net.start_server(on_message)   # либо start_client(ip, on_message)
await net.send(json.dumps(payload))
"""
from __future__ import annotations

import asyncio
import json
from typing import Awaitable, Callable, Optional

import websockets


class P2PNetwork:
    """Мини‑обёртка над websockets с внутренней очередью̆ю отправки."""

    PORT = 8765

    def __init__(self) -> None:
        self._send_queue: asyncio.Queue[str] = asyncio.Queue()
        self._send_callback_set: bool = False  # выставляется после старта
        # Сохраняем callback UI для отладки (может пригодиться в логах)
        self._ui_callback: Optional[Callable[[str], None]] = None

    # ---------- Публичный API -------------------------------------------------

    async def start_server(self, ui_callback: Callable[[str], None]) -> None:
        """Запустить WebSocket‑сервер и слушать входящие соединения."""
        self._ui_callback = ui_callback
        async with websockets.serve(self._handler, "0.0.0.0", self.PORT):
            print(f"[NETWORK] Сервер запущен на 0.0.0.0:{self.PORT}")
            await asyncio.Future()  # run forever

    async def start_client(
        self, ip: str, ui_callback: Callable[[str], None]
    ) -> None:
        """
        Подключиться к существующему узлу и начать обмен сообщениями.

        Бросает исключение, если соединиться не удалось.
        """
        self._ui_callback = ui_callback
        uri = f"ws://{ip}:{self.PORT}"
        print(f"[NETWORK] Подключаемся к {uri} …")
        async with websockets.connect(uri) as websocket:
            print(f"[NETWORK] Соединение установлено с {ip}")
            await self._pump(websocket)

    async def send(self, msg: str) -> None:
        """Поставить сообщение в очередь на отправку (не блокирует GUI)."""
        if not self._send_callback_set:
            # очередь ещё не связана с websocket; ждём старта сети
            await asyncio.sleep(0)  # уступаем управление
        self._send_queue.put_nowait(msg)

    # ---------- Внутренняя кухня -----------------------------------------------

    async def _handler(self, websocket) -> None:
        """Handler для websockets.serve()."""
        await self._pump(websocket)

    async def _pump(self, websocket) -> None:
        """Запускает задачи отправки и приёма, пока соединение живо."""
        self._send_callback_set = True

        async def receiver() -> None:
            async for raw in websocket:
                if self._ui_callback:
                    self._ui_callback(raw)

        async def sender() -> None:
            while True:
                msg = await self._send_queue.get()
                await websocket.send(msg)

        await asyncio.gather(receiver(), sender())