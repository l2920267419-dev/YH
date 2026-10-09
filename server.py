# -*- coding: utf-8 -*-
import http.server, os, json, re, hashlib, socket, sys, time, urllib.parse, webbrowser, ipaddress
from urllib.request import Request, urlopen

PORT = 8765
MAX_PORT_TRY = 10
# 以本文件所在目录为站点根目录：开发副本与 D:\夜航导航站 部署副本均可自洽运行
DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(DIR, "server.log")
PORT_FILE = os.path.join(DIR, "server.port")


def log(*parts):
    """轻量日志：写文件而非控制台（pythonw 无控制台，静默失败难排查）。超过 2MB 自动轮换。"""
    try:
        try:
            if os.path.getsize(LOG_FILE) > 2 * 1024 * 1024:
                os.replace(LOG_FILE, LOG_FILE + ".old")
        except OSError:
            pass
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " " + " ".join(str(p) for p in parts) + "\n")
    except Exception:
        pass


def _find_steam_wallpaper_roots():
    """自动发现 Wallpaper Engine（Steam appid 431960）创意工坊目录。

    从 Steam 注册表路径 + steamapps/libraryfolders.vdf 解析全部游戏库，
    对每个库检查 steamapps/workshop/content/431960 是否存在。这样发布版
    无需在 wallpaper_list.js 里预置任何路径也能自动同步壁纸。
    """
    found = []
    seen = set()

    def add_lib(lib):
        w = os.path.join(lib, "steamapps", "workshop", "content", "431960")
        key = os.path.normpath(w).lower()
        if os.path.isdir(w) and key not in seen:
            seen.add(key)
            found.append(w)

    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        try:
            steam, _ = winreg.QueryValueEx(k, "SteamPath")
            steam = os.path.normpath(steam)
            add_lib(steam)
        except OSError:
            pass
        vdf = os.path.join(steam, "steamapps", "libraryfolders.vdf")
        if os.path.isfile(vdf):
            with open(vdf, "r", encoding="utf-8", errors="ignore") as f:
                txt = f.read()
            for m in re.finditer(r'"path"\s*"([^"]+)"', txt):
                p = m.group(1).replace("\\\\", os.sep).replace("\\", os.sep)
                if os.path.isdir(p):
                    add_lib(p)
    except Exception as e:
        log("steam roots error:", repr(e))
    return found


def _load_allowed_roots():
    """从 wallpaper_list.js 提取 file:/// 路径的公共目录作为 /media 白名单根，
    避免写死 Steam 路径；站点目录本身始终允许。多磁盘时按盘符分别取公共目录。
    另自动发现 Wallpaper Engine 创意工坊目录，发布版开箱即用。"""
    roots = [DIR]
    try:
        with open(os.path.join(DIR, "wallpaper_list.js"), "r", encoding="utf-8") as f:
            src = f.read()
        paths = re.findall(r"file:///[^\"']+", src)
        if paths:
            norm = [os.path.normpath(p.replace("file:///", "").replace("/", os.sep)) for p in paths]
            groups = {}
            for p in norm:
                groups.setdefault(os.path.splitdrive(p)[0].lower(), []).append(os.path.dirname(p))
            for _drive, dirs in groups.items():
                try:
                    common = os.path.commonpath(dirs)
                    if common and os.path.isdir(common):
                        roots.append(common)
                        continue
                except ValueError:
                    pass
                # 同盘符但无法取公共目录（或路径异常）：逐个目录兜底
                for d in dirs:
                    if os.path.isdir(d) and d not in roots:
                        roots.append(d)
    except Exception as e:
        log("load allowed roots error:", repr(e))
    # 自动发现 Wallpaper Engine 创意工坊目录（新增能力：无需预置路径）
    for w in _find_steam_wallpaper_roots():
        if w not in roots:
            roots.append(w)
    return roots


ALLOWED_ROOTS = _load_allowed_roots()
_ROOT_SIG = None


def refresh_roots_if_changed():
    """wallpaper_list.js 变化时热更新允许根目录：新增壁纸目录无需重启服务。"""
    global ALLOWED_ROOTS, _ROOT_SIG
    try:
        st = os.stat(os.path.join(DIR, "wallpaper_list.js"))
        sig = (st.st_mtime_ns, st.st_size)
    except OSError:
        sig = None
    if sig != _ROOT_SIG:
        _ROOT_SIG = sig
        roots = _load_allowed_roots()
        if roots != ALLOWED_ROOTS:
            ALLOWED_ROOTS = roots
            log("allowed roots refreshed:", ";".join(roots))
    return ALLOWED_ROOTS


def _within_allowed(path):
    """规范化后必须位于某个允许根目录内（大小写不敏感）。"""
    refresh_roots_if_changed()
    try:
        p = os.path.normpath(os.path.abspath(path))
    except Exception:
        return False
    pl = p.lower()
    return any(pl == r.lower() or pl.startswith(r.rstrip("\\/").lower() + os.sep) for r in ALLOWED_ROOTS)


def project_title(dirpath):
    """Wallpaper Engine 创意工坊目录 project.json 里的官方标题。
    视频文件名常是哈希/代号（fragile_4k_ad799、28.2、Apoc1.0000），标题才是用户认识的名字。"""
    try:
        with open(os.path.join(dirpath, "project.json"), "r", encoding="utf-8-sig") as f:
            t = json.load(f).get("title")
        return str(t).strip() if t else ""
    except Exception:
        return ""


# 壁纸扫描缓存：前端每 5 秒轮询 /sync-state，全量 os.walk 壁纸目录代价高，
# 用「顶层目录 mtime 快速探测」判断变化；超过 _FORCE_FULL_INTERVAL 强制全量一次兜底，
# 保证深层新增壁纸也能被发现。
_WP_CACHE = {"quick": None, "items": None, "last_full": 0.0}
_FORCE_FULL_INTERVAL = 60  # 秒

# 自动同步开关：/sync-pause、/sync-resume 控制，随 /sync-state 返回给前端。
# 注意：以本变量为「前端可见状态」的权威来源；nav_sync.pyw 重启会复位为自动同步，
# 但重启需手动操作，一般不会发生。手动「立即同步」不受暂停影响。
_PAUSED = False


def _quick_sig():
    """轻量指纹：各允许根目录下顶层子目录的 (名称, mtime)。增删壁纸目录/文件通常会让
    其直接父目录 mtime 变化，从而改变本指纹。只 listdir + stat 顶层，成本远低于全量 walk。"""
    parts = []
    for root in ALLOWED_ROOTS:
        if root.lower() == DIR.lower():
            continue  # 只扫壁纸目录，站点文件不算壁纸
        try:
            with os.scandir(root) as it:
                entries = sorted(
                    (e.name, e.stat(follow_symlinks=False).st_mtime_ns)
                    for e in it if e.is_dir(follow_symlinks=False)
                )
            parts.append((root, entries))
        except OSError:
            parts.append((root, None))
    return tuple(parts)


def scan_wallpapers():
    """动态扫描壁纸目录，返回全部可播放视频（真实路径），空文件跳过。
    网页壁纸（同时含 index.html 和 project.json）是整体作品，其内部视频只作素材，不单独列出。
    带缓存：快速指纹无变化且未到强制刷新间隔时直接复用上次结果。"""
    refresh_roots_if_changed()
    now = time.time()
    quick = _quick_sig()
    if (_WP_CACHE["quick"] == quick and _WP_CACHE["items"] is not None
            and now - _WP_CACHE["last_full"] < _FORCE_FULL_INTERVAL):
        return _WP_CACHE["items"]
    items = _scan_wallpapers_full()
    _WP_CACHE["quick"], _WP_CACHE["items"], _WP_CACHE["last_full"] = quick, items, now
    return items


def _scan_wallpapers_full():
    """全量扫描（内部函数，带缓存调用方为 scan_wallpapers）。"""
    exts = (".mp4", ".webm", ".mov", ".m4v")
    items, seen = [], set()
    for root in ALLOWED_ROOTS:
        if root.lower() == DIR.lower():
            continue  # 只扫壁纸目录，站点文件不算壁纸
        web_roots = set()
        try:
            for dp, _dd, ff in os.walk(root):
                if "index.html" in ff and "project.json" in ff:
                    web_roots.add(os.path.normpath(dp).lower())
        except Exception:
            pass
        try:
            for dirpath, _dirs, files in os.walk(root):
                dp_norm = os.path.normpath(dirpath).lower()
                if any(dp_norm == wr or dp_norm.startswith(wr + os.sep) for wr in web_roots):
                    continue  # 位于网页壁纸目录内，跳过其素材视频
                for fn in sorted(files):
                    if not fn.lower().endswith(exts):
                        continue
                    if re.search(r"-test\.", fn, re.IGNORECASE):
                        continue  # 跳过订阅项里的测试视频（如 884307090/N-test.webm）
                    fp = os.path.join(dirpath, fn)
                    try:
                        st = os.stat(fp)
                    except OSError:
                        continue
                    if st.st_size == 0:
                        continue  # 空文件无法播放
                    key = fp.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    img = ""
                    for pv in ("preview.jpg", "preview.png", "preview.gif", "preview.jpeg"):
                        if os.path.isfile(os.path.join(dirpath, pv)):
                            img = "file:///" + os.path.join(dirpath, pv).replace("\\", "/")
                            break
                    items.append({
                        "t": project_title(dirpath) or os.path.splitext(fn)[0],
                        "p": "file:///" + fp.replace("\\", "/"),
                        "img": img,
                        "size": st.st_size,
                        "mtime": st.st_mtime_ns,
                    })
        except Exception:
            continue
    items.sort(key=lambda x: (-x["size"], x["t"].lower()))
    return items


def wallpaper_signature(items):
    """壁纸列表指纹：路径+大小+修改时间，任一变化都会改变。"""
    raw = "|".join("%s:%d:%d" % (x["p"], x["size"], x["mtime"]) for x in items)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()



class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=DIR, **kw)

    def _allowed_origin(self):
        """仅允许本站页面跨域访问，其余 Origin 一律不返回 CORS 头（浏览器会拦截）。"""
        origin = self.headers.get("Origin")
        if origin:
            host = urllib.parse.urlparse(origin).netloc
            if host in ("127.0.0.1:%d" % self.server.server_port,
                        "localhost:%d" % self.server.server_port):
                return origin
        return None

    def _send_json(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception:
            pass

    def do_OPTIONS(self):
        origin = self._allowed_origin()
        if origin:
            self.send_response(204)
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Range")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        else:
            self.send_response(403)
        self.end_headers()

    def _query_param(self, name):
        """取查询参数并做一次 URL 解码（保留 +，避免文件名里的 + 被当成空格）。"""
        q = urllib.parse.urlparse(self.path).query
        for kv in q.split("&"):
            if kv.startswith(name + "="):
                return urllib.parse.unquote(kv[len(name) + 1:])
        return ""

    def _resolve_media(self):
        p = self._query_param("p")
        p = p.replace("file:///", "").replace("/", os.sep)
        if not p:
            return None, "empty path"
        # 历史数据可能被双重编码（如 %20 又被 encodeURIComponent 一次），找不到时再解一次兜底
        if not os.path.isfile(p) and "%" in p:
            p2 = urllib.parse.unquote(p)
            if os.path.isfile(p2):
                p = p2
        if not _within_allowed(p):
            return None, "path not allowed"
        if not os.path.isfile(p):
            return None, "file not found"
        return p, None

    def _serve_media(self):
        p, err = self._resolve_media()
        if err:
            log("media denied:", self.headers.get("Referer", "-"), err, self.path[:200])
            try:
                self.send_error(404, err)
            except Exception:
                pass
            return
        try:
            size = os.path.getsize(p)
            ext = p.lower()
            if ext.endswith(".mp4"):
                ct = "video/mp4"
            elif ext.endswith(".webm"):
                ct = "video/webm"
            elif ext.endswith(".png"):
                ct = "image/png"
            elif ext.endswith(".gif"):
                ct = "image/gif"
            else:
                ct = "image/jpeg"
            rng = self.headers.get("Range")
            if rng:
                # 解析 "bytes=start-end"，end 可省略；越界返回 416
                parts = rng.replace("bytes=", "").split("-")
                start = int(parts[0]) if parts[0] else 0
                end = int(parts[1]) if len(parts) > 1 and parts[1] else size - 1
                end = min(end, size - 1)
                if start > end or start >= size:
                    self.send_error(416, "Range Not Satisfiable")
                    return
                length = end - start + 1
                self.send_response(206)
                self.send_header("Content-Type", ct)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
                self.send_header("Content-Length", str(length))
                self.end_headers()
                # 必须与声明的 Content-Length 完全一致地写出，否则浏览器报 CONTENT_LENGTH_MISMATCH
                with open(p, "rb") as f:
                    f.seek(start)
                    remaining = length
                    while remaining > 0:
                        c = f.read(min(1024 * 1024, remaining))
                        if not c:
                            break
                        self.wfile.write(c)
                        remaining -= len(c)
            else:
                self.send_response(200)
                self.send_header("Content-Type", ct)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(size))
                self.end_headers()
                with open(p, "rb") as f:
                    while True:
                        c = f.read(1024 * 1024)
                        if not c:
                            break
                        self.wfile.write(c)
        except Exception as e:
            try:
                self.send_error(404, str(e)[:100])
            except Exception:
                pass

    def _check_link(self):
        """后端死链检测：真实 HEAD/GET 状态码，不再受浏览器 no-cors 限制。"""
        u = self._query_param("u")
        parsed = urllib.parse.urlparse(u)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            self._send_json(400, {"ok": False, "error": "仅支持 http/https 链接"})
            return
        host = parsed.hostname.lower()
        blocked = host in ("localhost", "127.0.0.1", "::1", "0.0.0.0")
        if not blocked:
            try:
                ip = ipaddress.ip_address(host)
                blocked = (ip.is_private or ip.is_loopback or ip.is_link_local
                           or ip.is_multicast or ip.is_reserved)
            except ValueError:
                pass  # 域名交给系统解析；服务仅监听回环，风险可控
        if blocked:
            self._send_json(400, {"ok": False, "error": "不允许检测内网/本机地址"})
            return
        t0 = time.time()
        try:
            req = Request(u, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) nav-check/1.0",
                "Range": "bytes=0-0",
            })
            with urlopen(req, timeout=8) as resp:
                status = resp.status
                resp.read(4096)  # 读取少量内容即关闭，避免大文件下载
            ms = int((time.time() - t0) * 1000)
            self._send_json(200, {"ok": status < 400, "status": status, "ms": ms})
        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            # 401/403 等「服务器明确拒绝」不算死链；无法判断的（超时/解析失败）标记未验证
            code = getattr(e, "code", 0)
            if code in (401, 403):
                self._send_json(200, {"ok": True, "status": code, "ms": ms})
            else:
                self._send_json(200, {"ok": code >= 400, "status": code, "ms": ms,
                                      "error": str(e)[:120]})

    def _list_wallpapers(self):
        self._send_json(200, scan_wallpapers())


    def _file_state(self, name):
        """站点数据文件的状态（修改时间 + 大小）。"""
        try:
            st = os.stat(os.path.join(DIR, name))
            return {"m": st.st_mtime_ns, "s": st.st_size}
        except OSError:
            return None

    def _sync_state(self):
        """统一同步状态：前端定期轮询，据此自动发现所有数据变化。"""
        items = scan_wallpapers()
        files = {}
        for name in ("nav_data.js", "wallpaper_list.js", "nav_extra.js", "nav_preset.js",
                     "func_key.js", "shortcuts.js", "index.html", "fluent_skin.css"):
            files[name] = self._file_state(name)
        self._send_json(200, {
            "wp": wallpaper_signature(items),
            "wpn": len(items),
            "paused": _PAUSED,
            "files": files,
            "time": int(time.time() * 1000),
        })

    def do_GET(self):
        if self.path.startswith("/sync-state"):
            self._sync_state()
            return
        if self.path.startswith("/wallpapers"):
            self._list_wallpapers()
            return
        if self.path.startswith("/media?"):
            self._serve_media()
            return
        if self.path.startswith("/open-browser"):
            # 在系统默认浏览器打开本站。URL 固定为本机服务地址，不接受外部传入
            try:
                url = "http://127.0.0.1:%d/" % self.server.server_port
                webbrowser.open(url, new=2)
                self._send_json(200, {"ok": True, "url": url})
            except Exception as e:
                self._send_json(500, {"ok": False, "error": str(e)[:120]})
            return
        if self.path.startswith("/check-link"):
            self._check_link()
            return
        if self.path.startswith("/sync-pause"):
            self._set_sync_pause(True)
            return
        if self.path.startswith("/sync-resume"):
            self._set_sync_pause(False)
            return
        if self.path.startswith("/sync"):
            self._trigger_sync()
            return
        return super().do_GET()

    def _set_sync_pause(self, paused):
        """取消/恢复自动同步：向 nav_sync.pyw 命令通道发送 pause/resume。"""
        global _PAUSED
        try:
            s = socket.create_connection(("127.0.0.1", 47831), timeout=3)
            try:
                s.sendall(b"pause" if paused else b"resume")
            finally:
                s.close()
            _PAUSED = paused
            self._send_json(200, {"ok": True, "paused": _PAUSED})
        except OSError:
            self._send_json(502, {"ok": False, "error": "同步服务未运行"})

    def _trigger_sync(self):
        """「立即同步」：通知 nav_sync.pyw 立即从 Edge 收藏夹重读并生成 nav_data.js，
        等待其写盘完成后返回。pyw 未运行（47831 无监听）时返回 502。"""
        try:
            s = socket.create_connection(("127.0.0.1", 47831), timeout=3)
            try:
                s.sendall(b"sync")
            finally:
                s.close()
        except OSError:
            self._send_json(502, {"ok": False, "error": "同步服务未运行"})
            return
        nd = os.path.join(DIR, "nav_data.js")
        try:
            before = os.stat(nd).st_mtime_ns
        except OSError:
            before = 0
        t0 = time.time()
        while time.time() - t0 < 5:
            time.sleep(0.15)
            try:
                if os.stat(nd).st_mtime_ns != before:
                    self._send_json(200, {"ok": True, "synced": True})
                    return
            except OSError:
                pass
        self._send_json(200, {"ok": True, "synced": False})

    def log_message(self, fmt, *args):
        log("http:", self.address_string(), fmt % args)

    def end_headers(self):
        # 仅本站 Origin 放行跨域读取（静态文件/媒体/JSON 统一处理），外部页面拿不到 CORS 头
        origin = self._allowed_origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
        # 前端模块/样式/页面始终重新验证：桌面本地服务无带宽成本，
        # 避免 ES Module 图被浏览器启发式缓存导致「改了代码但页面跑旧版」。
        if self.path.split("?", 1)[0].endswith((".js", ".css", ".html")):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def find_port():
    """8765 起逐个探测空闲端口，返回可用端口。"""
    for port in range(PORT, PORT + MAX_PORT_TRY):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return None


def main():
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    port = find_port()
    if port is None:
        log("ERROR: 端口 %d-%d 均被占用，无法启动" % (PORT, PORT + MAX_PORT_TRY - 1))
        sys.exit(1)
    try:
        with open(PORT_FILE, "w", encoding="utf-8") as f:
            f.write(str(port))
    except Exception:
        pass
    log("server start, port=%d, allowed roots: %s" % (port, ";".join(ALLOWED_ROOTS)))
    # 多线程处理请求：壁纸大文件流式传输时不再阻塞书签同步等其他请求
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), H) as httpd:
        log("listening on http://127.0.0.1:%d/" % port)
        httpd.serve_forever()


if __name__ == "__main__":
    main()