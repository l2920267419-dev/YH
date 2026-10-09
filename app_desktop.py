# -*- coding: utf-8 -*-
"""夜航导航站 桌面版入口（PyInstaller 打包用）。

启动本地 HTTP 服务（复用 server.py）+ Edge WebView2 独立窗口。
站点根目录以 exe/本文件所在目录为准，打包后仍与 index.html 等文件放同一目录即可。
"""
import os
import sys
import threading
import time

import webview

SITE = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))

import server  # noqa: E402  （PyInstaller 会把它一起打进包）

server.DIR = SITE
server.LOG_FILE = os.path.join(SITE, "server.log")
server.PORT_FILE = os.path.join(SITE, "server.port")
server.ALLOWED_ROOTS = server._load_allowed_roots()


def _run_server():
    try:
        server.main()
    except Exception as e:
        server.log("app_desktop server error:", repr(e))


def _wait_port(timeout=10):
    """等服务就绪并读取实际端口（支持 8765 被占用时顺延）。"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with open(server.PORT_FILE, "r", encoding="utf-8") as f:
                port = int(f.read().strip())
            return port
        except Exception:
            time.sleep(0.1)
    return 8765


def main():
    threading.Thread(target=_run_server, daemon=True).start()
    port = _wait_port()
    window = webview.create_window(
        "夜航导航站",
        "http://127.0.0.1:%d/" % port,
        width=1360, height=860, min_size=(1024, 640),
    )
    webview.start()


if __name__ == "__main__":
    main()