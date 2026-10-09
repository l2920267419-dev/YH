/* ============================================================
 * 夜航导航站 · Edge 风格键盘快捷键
 * 浏览器与 Edge WebView2 桌面壳通用；不占用站点已有的
 * "/" 搜索、"Ctrl+K" 命令面板、"Esc" 关闭弹层等绑定。
 * ============================================================ */
(function () {
  'use strict';
  if (window.__shortcutsInstalled) return;
  window.__shortcutsInstalled = true;

  var ZOOM_KEY = 'site.zoom.v1';
  var ZOOM_MIN = 50, ZOOM_MAX = 200, ZOOM_STEP = 10;

  /* ---------- 环境判断 ---------- */
  function isDesktopShell() {
    return !!(window.pywebview || /WebView2?\//i.test(navigator.userAgent));
  }

  /* ---------- 极简提示条 ---------- */
  var toastEl = null, toastTimer = null;
  function toast(text) {
    if (!toastEl) {
      toastEl = document.createElement('div');
      toastEl.className = 'sc-toast';
      document.body.appendChild(toastEl);
    }
    toastEl.textContent = text;
    toastEl.classList.add('is-show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.classList.remove('is-show'); }, 1600);
  }

  /* ---------- 页面缩放（CSS zoom，Chromium 原生支持；记忆到 localStorage） ---------- */
  function getZoom() {
    var z = parseFloat(localStorage.getItem(ZOOM_KEY));
    if (isNaN(z)) return 100;
    return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, z));
  }
  function applyZoom(z) {
    z = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Math.round(z)));
    document.documentElement.style.zoom = (z / 100).toFixed(2);
    localStorage.setItem(ZOOM_KEY, String(z));
    toast('缩放 ' + z + '%');
  }
  // 页面载入即恢复上次缩放
  try {
    var savedZoom = getZoom();
    if (savedZoom !== 100) document.documentElement.style.zoom = (savedZoom / 100).toFixed(2);
  } catch (e) { /* localStorage 不可用时忽略 */ }

  /* ---------- 全屏 ---------- */
  function toggleFullscreen() {
    if (document.fullscreenElement) {
      if (document.exitFullscreen) document.exitFullscreen().catch(function () {});
    } else if (document.documentElement.requestFullscreen) {
      document.documentElement.requestFullscreen().catch(function () {
        toast('当前环境不支持全屏');
      });
    } else {
      toast('当前环境不支持全屏');
    }
  }

  /* ---------- 历史导航 ---------- */
  function goBack() {
    // history.length 在新标签页首屏为 1；WebView2 中同理
    if (history.length > 1) history.back();
    else toast('没有可返回的页面');
  }
  function goForward() {
    history.forward();
  }

  /* ---------- 刷新 ---------- */
  function reloadPage() {
    // server 已对 html/js/css 下发 Cache-Control: no-cache，普通 reload 即取最新
    location.reload();
  }

  /* ---------- 聚焦搜索框（对应 Edge 的 Ctrl+L 聚焦地址栏） ---------- */
  function focusSearch() {
    var input = document.getElementById('searchInput');
    if (input) {
      input.focus();
      try { input.select(); } catch (e) {}
    }
  }

  /* ---------- 快捷键速查面板 ---------- */
  var SHORTCUTS = [
    ['F5 / Ctrl + R', '刷新页面'],
    ['Ctrl + F5', '强制刷新'],
    ['F11', '全屏 / 退出全屏'],
    ['Ctrl + +', '放大页面'],
    ['Ctrl + -', '缩小页面'],
    ['Ctrl + 0', '缩放恢复 100%'],
    ['Alt + ← / →', '后退 / 前进'],
    ['Ctrl + L', '聚焦搜索框'],
    ['Ctrl + K', '打开命令面板'],
    ['/', '快速搜索（输入框外）'],
    ['Ctrl + F', '页内查找'],
    ['Esc', '关闭弹层 / 退出全屏'],
    ['?', '打开本快捷键列表']
  ];
  var helpOverlay = null;

  function closeHelp() {
    if (helpOverlay) helpOverlay.remove();
    helpOverlay = null;
    document.removeEventListener('keydown', onHelpKey, true);
  }
  function onHelpKey(e) {
    if (e.key === 'Escape') { e.stopPropagation(); closeHelp(); }
  }

  function openHelp() {
    if (helpOverlay) { closeHelp(); return; }
    helpOverlay = document.createElement('div');
    helpOverlay.className = 'sc-overlay';
    var rows = SHORTCUTS.map(function (r) {
      return '<div class="sc-row"><kbd>' + r[0] + '</kbd><span>' + r[1] + '</span></div>';
    }).join('');
    helpOverlay.innerHTML =
      '<div class="sc-panel" role="dialog" aria-label="键盘快捷键">' +
      '<div class="sc-head"><span>键盘快捷键</span><span class="sc-env">' +
      (isDesktopShell() ? '桌面版 · Edge 内核' : '浏览器版') +
      '</span></div>' +
      '<div class="sc-rows">' + rows + '</div>' +
      '<div class="sc-foot">按 <kbd>Esc</kbd> 或点击空白处关闭</div>' +
      '</div>';
    helpOverlay.addEventListener('click', function (e) { if (e.target === helpOverlay) closeHelp(); });
    document.addEventListener('keydown', onHelpKey, true);
    document.body.appendChild(helpOverlay);
  }
  window.__showShortcutsHelp = openHelp;

  /* ---------- 注入样式（跟随站点深色玻璃风变量） ---------- */
  var style = document.createElement('style');
  style.textContent = [
    '.sc-toast{position:fixed;left:50%;bottom:34px;transform:translate(-50%,14px);z-index:10000;',
    'padding:9px 17px;border-radius:11px;background:rgba(20,24,36,.95);color:#dfe4ee;',
    'font-size:13px;font-weight:600;border:1px solid rgba(255,255,255,.14);',
    'box-shadow:0 14px 40px -10px rgba(0,0,0,.6);opacity:0;pointer-events:none;',
    'transition:opacity .18s,transform .18s;font-family:inherit}',
    '.sc-toast.is-show{opacity:1;transform:translate(-50%,0)}',
    '.sc-overlay{position:fixed;inset:0;z-index:9999;background:rgba(8,10,16,.55);',
    '-webkit-backdrop-filter:blur(4px);backdrop-filter:blur(4px);display:grid;place-items:center;',
    'animation:scFade .15s ease}',
    '@keyframes scFade{from{opacity:0}to{opacity:1}}',
    '.sc-panel{width:min(440px,92vw);max-height:84vh;overflow:auto;border-radius:18px;padding:20px 22px;',
    'background:linear-gradient(165deg,rgba(38,44,64,.98),rgba(17,21,33,.99));',
    'border:1px solid rgba(255,255,255,.12);box-shadow:0 26px 70px -18px rgba(0,0,0,.8);',
    'color:#e8ecf3;font-family:inherit}',
    '.sc-head{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:14px}',
    '.sc-head>span:first-child{font-size:16px;font-weight:700}',
    '.sc-env{font-size:11px;color:#8b94a6;border:1px solid var(--line,rgba(255,255,255,.14));',
    'border-radius:20px;padding:2px 10px}',
    '.sc-rows{display:flex;flex-direction:column;gap:7px}',
    '.sc-row{display:flex;justify-content:space-between;align-items:center;gap:16px;font-size:13px;color:#c4ccda}',
    '.sc-row kbd{font-family:inherit;font-size:12px;color:#eaeef6;background:rgba(255,255,255,.07);',
    'border:1px solid rgba(255,255,255,.16);border-bottom-width:2px;border-radius:7px;padding:3px 9px;',
    'white-space:nowrap;min-width:128px;text-align:center}',
    '.sc-foot{margin-top:15px;padding-top:12px;border-top:1px solid rgba(255,255,255,.08);',
    'font-size:11.5px;color:#8b94a6;text-align:center}',
    '.sc-foot kbd{font-family:inherit;font-size:11px;background:rgba(255,255,255,.07);',
    'border:1px solid rgba(255,255,255,.16);border-radius:6px;padding:1px 7px}'
  ].join('\n');
  document.head.appendChild(style);

  /* ---------- 主快捷键分发 ---------- */
  document.addEventListener('keydown', function (e) {
    var key = e.key;
    var ctrl = e.ctrlKey || e.metaKey;

    // 速查面板打开时，按键交给面板自己的捕获处理器
    if (helpOverlay) return;

    // F5 刷新（WebView2 对 F5 支持不稳定，统一拦截）
    if (key === 'F5') { e.preventDefault(); reloadPage(); return; }

    // F11 全屏（WebView2 控件默认无此行为）
    if (key === 'F11') { e.preventDefault(); toggleFullscreen(); return; }

    if (ctrl) {
      var k = key.toLowerCase();

      // 刷新：Ctrl+R / Ctrl+Shift+R（强制刷新在 no-cache 策略下行为一致）
      if (k === 'r' && !e.altKey) { e.preventDefault(); reloadPage(); return; }

      // 缩放：Ctrl + =/+ 放大、- 缩小、0 复位（兼容小键盘 Add/Subtract）
      if (k === '=' || k === '+' || key === 'Add') { e.preventDefault(); applyZoom(getZoom() + ZOOM_STEP); return; }
      if (k === '-' || k === '_' || key === 'Subtract') { e.preventDefault(); applyZoom(getZoom() - ZOOM_STEP); return; }
      if (k === '0') { e.preventDefault(); applyZoom(100); return; }

      // 聚焦搜索框
      if (k === 'l') { e.preventDefault(); focusSearch(); return; }

      // DevTools（Ctrl+Shift+I/J/C）：桌面壳被 pywebview 禁用，给明确提示；普通浏览器不拦截
      if (e.shiftKey && (k === 'i' || k === 'j' || k === 'c')) {
        if (isDesktopShell()) { e.preventDefault(); toast('桌面版未开放开发者工具'); }
        return;
      }
    }

    // F12 开发者工具（不需要 Ctrl，独立判断）：桌面壳拦截并提示
    if (key === 'F12') {
      if (isDesktopShell()) { e.preventDefault(); toast('桌面版未开放开发者工具'); }
      return;
    }

    // Alt + 方向键：历史导航
    if (e.altKey && !ctrl) {
      if (key === 'ArrowLeft') { e.preventDefault(); goBack(); return; }
      if (key === 'ArrowRight') { e.preventDefault(); goForward(); return; }
    }

    // "?" 打开快捷键速查（仅非输入态，避免影响打字）
    if (key === '?' && !e.ctrlKey && !e.altKey && !e.metaKey) {
      var ae = document.activeElement;
      var typing = ae && (ae.tagName === 'INPUT' || ae.tagName === 'TEXTAREA' ||
                          ae.tagName === 'SELECT' || ae.isContentEditable);
      if (!typing) { e.preventDefault(); openHelp(); return; }
    }
  });
})();
