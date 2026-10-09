/* 夜航导航站 · 功能键
   模仿浏览器顶栏的圆角方块功能键：点击展开下拉菜单，聚合站点常用操作。 */
(function () {
  'use strict';
  if (window.__navFuncKeyInited) return;
  window.__navFuncKeyInited = true;

  var $ = function (s, r) { return (r || document).querySelector(s); };

  var svgChevron = '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>';

  /* ---------- 运行环境检测（桌面壳 / Edge / Chrome / 其他浏览器） ---------- */
  function detectEnv() {
    // pywebview 桌面壳会注入 window.pywebview；WebView2 的 UA 也带 WebView2 标记
    if (window.pywebview || /WebView2?\//i.test(navigator.userAgent)) return { id: 'webview', label: '桌面应用' };
    var ua = navigator.userAgent;
    if (/Edg(e|A|iOS)?\//.test(ua)) return { id: 'edge', label: 'Edge 浏览器' };
    if (/Chrome\//.test(ua) && /Google/i.test(navigator.vendor)) return { id: 'chrome', label: 'Chrome 浏览器' };
    if (/Firefox\//.test(ua)) return { id: 'firefox', label: 'Firefox 浏览器' };
    return { id: 'browser', label: '系统浏览器' };
  }

  /* ---------- 菜单项（全部复用页面已有入口） ---------- */
  var MENU = [
    { emoji: '🧭', name: '在浏览器打开', desc: '当前：' + detectEnv().label + ' · 跳转默认浏览器', action: function () { openInBrowser(); } },
    { emoji: '⌨️', name: '键盘快捷键', desc: 'Edge 风格按键速查', action: function () { if (window.__showShortcutsHelp) window.__showShortcutsHelp(); else toast('快捷键模块未加载', 'err'); } },
    { emoji: '🎨', name: '自定义设置', desc: '站点外观', action: function () { clickId('settingsBtn'); } },
    { emoji: '⬆️', name: '回到顶部', desc: '', action: function () { window.scrollTo({ top: 0, behavior: 'smooth' }); } },
    { emoji: '🔄', name: '刷新页面', desc: '', action: function () { location.reload(); } },
    { emoji: '🧹', name: '清空缓存', desc: '重置站点数据后刷新', danger: true, action: function () { clearCacheReload(); } }
  ];

  function clickId(id) {
    var el = document.getElementById(id);
    if (el) el.click();
  }

  /* ---------- 轻量 Toast（不依赖主站） ---------- */
  var toastEl = null, toastTimer = null;
  function toast(text, type) {
    if (!toastEl) {
      toastEl = document.createElement('div');
      toastEl.className = 'fk-toast';
      document.body.appendChild(toastEl);
    }
    toastEl.textContent = text;
    toastEl.className = 'fk-toast is-show' + (type === 'err' ? ' is-err' : '');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.className = 'fk-toast'; }, 2600);
  }

  /* ---------- 自定义确认弹层（pywebview 下 confirm 可能不可用） ---------- */
  function confirmBox(title, desc, okText) {
    return new Promise(function (resolve) {
      var overlay = document.createElement('div');
      overlay.className = 'fk-modal-overlay';
      overlay.innerHTML =
        '<div class="fk-modal">' +
        '<div class="fk-modal-title">' + title + '</div>' +
        '<div class="fk-modal-desc">' + desc + '</div>' +
        '<div class="fk-modal-actions">' +
        '<button type="button" class="fk-modal-btn" data-a="0">取消</button>' +
        '<button type="button" class="fk-modal-btn is-danger" data-a="1">' + okText + '</button>' +
        '</div></div>';
      function done(v) { overlay.remove(); document.removeEventListener('keydown', onKey); resolve(v); }
      function onKey(e) { if (e.key === 'Escape') done(false); if (e.key === 'Enter') done(true); }
      overlay.addEventListener('click', function (e) {
        if (e.target === overlay) return done(false);
        var b = e.target.closest('.fk-modal-btn');
        if (b) done(b.getAttribute('data-a') === '1');
      });
      document.addEventListener('keydown', onKey);
      document.body.appendChild(overlay);
    });
  }

  /* ---------- 动作①：在默认浏览器打开（桌面壳才调后端，普通浏览器提示当前环境） ---------- */
  function openInBrowser() {
    var env = detectEnv();
    if (env.id !== 'webview') {
      toast('当前已在' + env.label + '中运行');
      return;
    }
    fetch('/open-browser').then(function (r) { return r.json(); }).then(function (j) {
      if (j && j.ok) toast('已在默认浏览器打开本站');
      else toast('打开失败：' + ((j && j.error) || '未知错误'), 'err');
    }).catch(function (e) { toast('无法连接本地服务：' + e.message, 'err'); });
  }

  /* ---------- 动作③：清空 localStorage 并刷新 ---------- */
  async function clearCacheReload() {
    var ok = await confirmBox(
      '清空站点数据？',
      '将删除本机保存的全部站点设置与收藏布局，刷新后恢复初始状态。此操作不可撤销。',
      '全部清空并刷新'
    );
    if (!ok) return;
    try { localStorage.clear(); } catch (e) { /* 忽略存储异常继续刷新 */ }
    location.reload();
  }

  /* ---------- DOM ---------- */
  var btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'fk-btn';
  btn.id = 'funcKey';
  btn.title = '功能菜单';
  btn.setAttribute('aria-label', '功能菜单');
  btn.setAttribute('aria-haspopup', 'true');
  btn.innerHTML = '<span class="fk-chev">' + svgChevron + '</span>';

  var menu = document.createElement('div');
  menu.className = 'fk-menu';
  menu.setAttribute('role', 'menu');
  menu.innerHTML = MENU.map(function (item, idx) {
    return '<button type="button" class="fk-item' + (item.danger ? ' is-danger' : '') + '" role="menuitem" data-i="' + idx + '">' +
      '<span class="fk-emoji">' + item.emoji + '</span>' +
      '<span class="fk-tx"><span class="fk-name">' + item.name + '</span>' +
      (item.desc ? '<span class="fk-desc">' + item.desc + '</span>' : '') + '</span></button>';
  }).join('');

  var holder = document.createElement('div');
  holder.className = 'fk-wrap';
  holder.appendChild(btn);
  holder.appendChild(menu);

  var topbarRight = document.querySelector('.topbar-right');
  if (topbarRight) topbarRight.appendChild(holder);
  else document.body.appendChild(holder);

  /* ---------- 样式 ---------- */
  var style = document.createElement('style');
  style.textContent = [
    ".fk-wrap{position:relative;display:inline-flex;align-items:center}",
    ".fk-btn{width:37px;height:37px;border-radius:11px;display:grid;place-items:center;border:1px solid rgba(128,138,160,.35);background:linear-gradient(160deg,rgba(72,80,104,.42),rgba(34,40,58,.42));color:#dfe4ee;cursor:pointer;transition:transform .18s var(--ease-standard,ease),border-color .18s,background .18s,box-shadow .18s;padding:0;-webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px)}",
    ".fk-btn:hover{border-color:rgba(180,220,60,.6);color:#d9f08a;transform:translateY(-1px);box-shadow:0 8px 20px -10px rgba(180,220,60,.4)}",
    ".fk-chev{display:grid;transition:transform .24s var(--ease-standard,ease)}",
    ".fk-wrap.is-open .fk-chev{transform:rotate(180deg)}",
    ".fk-wrap.is-open .fk-btn{border-color:rgba(180,220,60,.7);color:#c9ee4a;box-shadow:0 0 0 3px rgba(180,220,60,.14)}",
    ".fk-menu{position:absolute;top:calc(100% + 10px);right:0;width:238px;padding:7px;border-radius:16px;background:linear-gradient(165deg,rgba(38,44,64,.94),rgba(15,19,32,.97));border:1px solid rgba(255,255,255,.11);box-shadow:0 26px 64px -18px rgba(0,0,0,.72),inset 0 1px 0 rgba(255,255,255,.08);-webkit-backdrop-filter:blur(30px) saturate(1.5);backdrop-filter:blur(30px) saturate(1.5);display:none;flex-direction:column;z-index:300}",
    ".fk-menu::before{content:'';position:absolute;top:-5px;right:14px;width:9px;height:9px;border-radius:2.5px;background:rgba(38,44,64,.96);border-left:1px solid rgba(255,255,255,.1);border-top:1px solid rgba(255,255,255,.1);transform:rotate(45deg)}",
    ".fk-wrap.is-open .fk-menu{display:flex;animation:fkPop .22s cubic-bezier(.2,.8,.2,1)}",
    "@keyframes fkPop{from{opacity:0;transform:translateY(-7px) scale(.985)}to{opacity:1;transform:none}}",
    ".fk-item{display:flex;align-items:center;gap:11px;width:100%;padding:9px 10px;border:none;background:transparent;border-radius:11px;cursor:pointer;text-align:left;font-family:inherit;color:inherit;transition:background .14s}",
    ".fk-item:hover{background:linear-gradient(90deg,rgba(180,220,60,.16),rgba(180,220,60,.04))}",
    ".fk-emoji{width:31px;height:31px;border-radius:9px;display:grid;place-items:center;font-size:16px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.07);flex:none}",
    ".fk-item:hover .fk-emoji{background:rgba(180,220,60,.16);border-color:rgba(180,220,60,.28)}",
    ".fk-tx{display:flex;flex-direction:column;gap:1px;min-width:0}",
    ".fk-name{font-size:13px;font-weight:600;color:#eaeef6;line-height:1.3}",
    ".fk-desc{font-size:10.5px;color:#8b94a6;line-height:1.3}",
    ".fk-item.is-danger .fk-name{color:#f87171}",
    ".fk-item.is-danger .fk-emoji{border-color:rgba(248,113,113,.3)}",
    ".fk-item.is-danger:hover{background:linear-gradient(90deg,rgba(229,72,77,.18),rgba(229,72,77,.04))}",
    ".fk-item.is-danger:hover .fk-emoji{background:rgba(229,72,77,.16);border-color:rgba(248,113,113,.3)}",
    ".fk-toast{position:fixed;left:50%;bottom:34px;transform:translate(-50%,14px);z-index:9999;max-width:84vw;padding:10px 18px;border-radius:12px;background:rgba(20,24,36,.96);border:1px solid rgba(120,200,120,.35);color:#d9f2d9;font-size:13px;font-weight:600;box-shadow:0 14px 40px -10px rgba(0,0,0,.6);opacity:0;pointer-events:none;transition:opacity .2s,transform .2s}",
    ".fk-toast.is-show{opacity:1;transform:translate(-50%,0)}",
    ".fk-toast.is-err{border-color:rgba(248,113,113,.45);color:#fecaca}",
    ".fk-modal-overlay{position:fixed;inset:0;z-index:9998;background:rgba(8,10,16,.56);-webkit-backdrop-filter:blur(4px);backdrop-filter:blur(4px);display:grid;place-items:center;animation:fkFade .16s ease}",
    "@keyframes fkFade{from{opacity:0}to{opacity:1}}",
    ".fk-modal{width:min(380px,90vw);padding:20px 20px 16px;border-radius:18px;background:linear-gradient(165deg,rgba(38,44,64,.98),rgba(17,21,33,.99));border:1px solid rgba(255,255,255,.12);box-shadow:0 26px 70px -18px rgba(0,0,0,.8)}",
    ".fk-modal-title{font-size:15px;font-weight:700;color:#f1f4fa;margin-bottom:8px}",
    ".fk-modal-desc{font-size:12.5px;line-height:1.65;color:#9aa4b7;margin-bottom:18px}",
    ".fk-modal-actions{display:flex;justify-content:flex-end;gap:9px}",
    ".fk-modal-btn{border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.05);color:#dfe4ee;font-size:12.5px;font-weight:600;padding:8px 16px;border-radius:10px;cursor:pointer;font-family:inherit}",
    ".fk-modal-btn:hover{background:rgba(255,255,255,.1)}",
    ".fk-modal-btn.is-danger{border-color:rgba(248,113,113,.4);background:rgba(229,72,77,.18);color:#fca5a5}",
    ".fk-modal-btn.is-danger:hover{background:rgba(229,72,77,.3)}"
  ].join('\n');
  document.head.appendChild(style);

  /* ---------- 交互 ---------- */
  function isOpen() { return holder.classList.contains('is-open'); }
  function openMenu() {
    holder.classList.add('is-open');
    btn.setAttribute('aria-expanded', 'true');
  }
  function closeMenu() {
    holder.classList.remove('is-open');
    btn.setAttribute('aria-expanded', 'false');
  }
  function toggleMenu() { isOpen() ? closeMenu() : openMenu(); }

  btn.addEventListener('click', function (e) {
    e.stopPropagation();
    toggleMenu();
  });
  menu.addEventListener('click', function (e) {
    var item = e.target.closest('.fk-item');
    if (!item) return;
    var i = parseInt(item.getAttribute('data-i'), 10);
    closeMenu();
    setTimeout(function () { MENU[i].action(); }, 90);
  });
  document.addEventListener('click', function (e) {
    if (isOpen() && !holder.contains(e.target)) closeMenu();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && isOpen()) closeMenu();
  });
})();
