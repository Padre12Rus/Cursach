"""
main.py – Точка входа

Запускает:
* Tkinter‑GUI (ui.ChatApp)
* Сетевой уровень (network.P2PNetwork)
* Автоподключение к равноправному узлу в локальной подсети
"""

import asyncio
import socket
import tkinter as tk

from network import P2PNetwork
from ui import ChatApp


def _get_local_ip() -> str:
    """Определяем локальный IP‑адрес машины."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Нам не нужно реальное соединение, только IP интерфейса.
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


async def _auto_connect(net: P2PNetwork, on_msg) -> None:
    """
    Перебираем IP‑адреса в своей подсети, пытаемся подключиться к другому узлу.
    Если никто не отвечает, поднимаем собственный сервер.
    """
    ip = _get_local_ip()
    subnet = ".".join(ip.split(".")[:-1])

    for i in range(2, 255):
        peer_ip = f"{subnet}.{i}"
        if peer_ip == ip:
            continue
        try:
            await net.start_client(peer_ip, on_msg)
            print(f"[AUTO] Подключились к {peer_ip}")
            return
        except Exception:
            continue

    print("[AUTO] Никого не нашли – запускаем сервер")
    await net.start_server(on_msg)


async def main() -> None:
    """Создаём GUI, сеть и запускаем общий event‑loop."""
    root = tk.Tk()
    net = P2PNetwork()
    app = ChatApp(root, net)

    asyncio.create_task(_auto_connect(net, app.handle_incoming))

    while True:
        try:
            root.update()
            await asyncio.sleep(0.01)
        except tk.TclError:
            break


if __name__ == "__main__":
    asyncio.run(main())