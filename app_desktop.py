# -*- coding: utf-8 -*-
"""夜航导航站 桌面版入口（PyInstaller 打包用）。

启动本地 HTTP 服务（复用 server.py）+ Edge WebView2 独立窗口。
站点根目录以 exe/本文件所在目录为准，打包后仍与 index.html 等文件放同一目录即可。
"""
import os
import sys
import threading
import time
import subprocess

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


def _start_sync_daemon():
    """自动拉起 Edge 收藏夹同步守护进程（nav_sync.exe / nav_sync.pyw）。

    打包版：启动同目录 nav_sync.exe；源码运行：用当前解释器跑 nav_sync.pyw。
    若 47831 已被占用（已有实例），新实例会自行退出，不影响。
    """
    try:
        if getattr(sys, "frozen", False):
            exe = os.path.join(SITE, "nav_sync.exe")
            if os.path.exists(exe):
                subprocess.Popen([exe], cwd=SITE)
        else:
            pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            if not os.path.exists(pyw):
                pyw = sys.executable
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen([pyw, os.path.join(SITE, "nav_sync.pyw")], cwd=SITE,
                             creationflags=flags)
    except Exception as e:
        server.log("sync daemon start failed:", repr(e))


def main():
    _start_sync_daemon()
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