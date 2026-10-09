# 夜航导航站 (YH)

个人导航站：Edge 收藏夹同步 · 搜索 · 壁纸 · 多主题

## 功能

- **Edge 收藏夹自动同步**：`nav_sync.pyw` 守护进程监控 Edge 书签文件，变化即自动生成 `nav_data.js`；设置面板可「取消/恢复」自动同步
- **一键立即同步**：点击后强制从 Edge 收藏夹重新读取，无需等待轮询
- 分类卡片式导航（收藏夹栏每个子文件夹一个分类）、全站搜索（支持搜索引擎 bang 快捷指令）、命令面板（Ctrl+K）
- 置顶 / 常用排序、点击计数、死链检测、备份导入导出
- 壁纸背景（支持 Wallpaper Engine 目录扫描）、深色 / 浅色 / 自动主题、Fluent 毛玻璃皮肤、粒子背景

## 运行

| 方式 | 操作 | 访问地址 |
|---|---|---|
| 浏览器版 | 双击 `启动导航站.bat` 或 `python server.py` | http://127.0.0.1:8765/ |
| 桌面版 | 双击 `启动桌面版.bat` 或 `python app_desktop.py` | 独立窗口 |

## 同步机制

- `nav_sync.pyw`：监控 `%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Bookmarks`，检测到变化自动重写 `nav_data.js`（防抖 1.5s）。单实例保护 + 命令通道（127.0.0.1:47831）：支持 `sync`（强制同步）、`pause`（暂停自动同步）、`resume`（恢复）
- `server.py`：静态服务 + 媒体流（`/media`，带壁纸目录白名单）+ 死链检测（`/check-link`，拒绝内网地址）+ 同步状态（`/sync-state`）+ 强制同步（`/sync`）与暂停控制（`/sync-pause`、`/sync-resume`）

## 文件结构

```
夜航导航站/
├─ index.html          主页面（内嵌 EDGE_DATA 兜底数据）
├─ server.py           本地 HTTP 服务
├─ nav_sync.pyw        Edge 书签同步守护进程
├─ app_desktop.py      桌面版入口（pywebview + WebView2）
├─ nav_data.js         Edge 收藏夹数据（自动生成）
├─ nav_preset.js       发现推荐 1900+ 条
├─ nav_extra.js        外部推荐数据
├─ wallpaper_list.js   壁纸目录白名单
├─ fluent_skin.css     Fluent 毛玻璃皮肤
├─ func_key.js         功能键菜单
└─ shortcuts.js        快捷键（/ 搜索、Ctrl+K 命令面板等）
```

## 说明

- `nav_data.js` 由同步守护进程自动生成，仓库中保留一份以便克隆后开箱即用
- 桌面版 exe 与 PyInstaller 打包依赖（`_internal/`）不包含在本仓库，如需打包：`pyinstaller app_desktop.py`
