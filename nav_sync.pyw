# -*- coding: utf-8 -*-
import os, json, time, io, socket, sys
from urllib.parse import urlparse

# 单实例保护：绑定本地固定端口，第二个实例绑定失败即静默退出。
# 同一 socket 兼作「强制同步」命令通道：外部（server.py /sync）连入发送任意数据即触发一次
# 立即从 Edge 收藏夹重新读取，无需等待轮询。
_lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    _lock.bind(("127.0.0.1", 47831))
except OSError:
    sys.exit(0)
_lock.listen(1)
_lock.setblocking(False)

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_JS = os.path.join(BASE, "nav_data.js")
LOG = os.path.join(BASE, "_sync.log")

# Edge Profile（当前仅 Default；如以后新增 Profile，在列表里加 "Profile 1" 等）
PROFILES = ["Default"]
BM_PATHS = [os.path.join(os.environ["LOCALAPPDATA"], "Microsoft", "Edge",
                         "User Data", p, "Bookmarks") for p in PROFILES]

def log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except Exception:
        pass

def clean(s):
    s = (s or "").strip()
    return s or "未命名"

def link_node(node):
    u = node.get("url", "")
    if not (u.startswith("http://") or u.startswith("https://")):
        return None
    return {"name": clean(node.get("name")) or urlparse(u).netloc,
            "url": u,
            "desc": urlparse(u).netloc}

def folder_node(node, seen):
    links, groups = [], []
    for ch in node.get("children", []):
        t = ch.get("type")
        if t == "url":
            ln = link_node(ch)
            if ln and ln["url"] not in seen:
                seen.add(ln["url"])
                links.append(ln)
        elif t == "folder":
            sub = folder_node(ch, seen)
            if sub["links"] or sub["groups"]:
                groups.append(sub)
    return {"name": clean(node.get("name")), "links": links, "groups": groups}

def collect(bm_path):
    with io.open(bm_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    seen = set()
    folders = []
    roots = data.get("roots", {})
    bar = roots.get("bookmark_bar") or {}
    other = roots.get("other") or {}
    synced = roots.get("synced") or {}
    # 收藏夹栏：每个子文件夹就是一个分类
    for ch in bar.get("children", []):
        if ch.get("type") == "folder":
            sub = folder_node(ch, seen)
            if sub["links"] or sub["groups"]:
                folders.append(sub)
    # 收藏夹栏根级链接 + 移动收藏夹 -> 归入「未分类」
    unclassified = {"name": "未分类", "links": [], "groups": []}
    for root in (bar, synced):
        for ch in root.get("children", []):
            if ch.get("type") == "url":
                ln = link_node(ch)
                if ln and ln["url"] not in seen:
                    seen.add(ln["url"])
                    unclassified["links"].append(ln)
    if unclassified["links"]:
        folders.append(unclassified)
    # 其他收藏夹
    if other.get("type") == "folder":
        others = folder_node(other, seen)
        others["name"] = "其他收藏"
        if others["links"] or others["groups"]:
            folders.append(others)
    return folders

def signature():
    sig = []
    for p in BM_PATHS:
        try:
            st = os.stat(p)
            sig.append((st.st_mtime_ns, st.st_size))
        except OSError:
            sig.append((0, 0))
    return tuple(sig)

def count_links(folders):
    total = 0
    def walk(g):
        nonlocal total
        total += len(g.get("links", []))
        for sg in g.get("groups", []):
            walk(sg)
    for f in folders:
        walk(f)
    return total

def write_data():
    folders = []
    for p in BM_PATHS:
        if not os.path.exists(p):
            continue
        folders = collect(p)   # 单 Profile：直接采用该文件的结构
        break
    total = count_links(folders)
    version = signature()[0][0]
    payload = ("/* 由 nav_sync.pyw 自动生成，请勿手改 */\n"
               "window.NAV_EDGE = "
               + json.dumps({"version": version,
                             "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
                             "count": total,
                             "folders": folders}, ensure_ascii=False, indent=0)
               + ";\n")
    tmp = DATA_JS + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(payload)
    os.replace(tmp, DATA_JS)
    return total

def drain_cmd():
    """非阻塞收取命令通道连接并解析命令：
    pause=暂停自动同步；resume=恢复自动同步；其它（如 sync）=强制同步一次。
    返回 (cmd, 当前是否暂停)。"""
    global _paused
    try:
        conn, _ = _lock.accept()
        try:
            data = conn.recv(16).strip().lower()
        finally:
            conn.close()
        if data in (b"pause", b"p"):
            _paused = True
            return ("pause", _paused)
        if data in (b"resume", b"r"):
            _paused = False
            return ("resume", _paused)
        return ("sync", _paused)
    except (BlockingIOError, OSError):
        return (None, _paused)


_paused = False  # True=暂停自动同步；手动「立即同步」始终有效


def main():
    global _paused
    log("sync service started; watching %s" % BM_PATHS)
    last = None
    _paused = False
    while True:
        try:
            sig = signature()
            cmd, _paused = drain_cmd()
            if cmd == "pause":
                log("auto-sync paused")
            elif cmd == "resume":
                log("auto-sync resumed")
                last = None  # 恢复后立即同步一次
            forced = cmd == "sync"
            if forced or (not _paused and sig != last):
                time.sleep(0.3)          # 防抖：等 Edge 写完 / 命令通道收尾
                n = write_data()
                log("updated, %d links%s" % (n, " (forced)" if forced else ""))
                last = signature()
        except Exception as e:
            log("error: %r" % e)
            time.sleep(2)
        time.sleep(1.2)

if __name__ == "__main__":
    main()
