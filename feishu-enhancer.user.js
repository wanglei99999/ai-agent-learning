// ==UserScript==
// @name         破解飞书的文本复制 | 右键复制图片 | 去除飞书水印
// @namespace    https://bytedance.com
// @version      0.4
// @description  综合多个功能，破解飞书的复制和右键限制，让你的飞书更好用
// @author       Tom-yang
// @match        *://*.feishu.cn/*
// @match        *://*.larkoffice.com/*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=feishu.cn
// @grant        none
// @license      MIT
// @run-at       document-start
// ==/UserScript==

(function () {
  'use strict';

  console.log('[飞书增强] 脚本已启动');

  // ==================== 1. 破解复制限制（API层） ====================

  const originalXHROpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    if (method === 'POST' && url.includes('permission/document/actions/state')) {
      this.addEventListener('readystatechange', function () {
        if (this.readyState !== 4) return;
        try {
          const response = JSON.parse(this.response);
          if (response.data?.actions?.copy !== 1) {
            response.data.actions.copy = 1;
            Object.defineProperty(this, 'response', { get: () => response });
            Object.defineProperty(this, 'responseText', { get: () => JSON.stringify(response) });
          }
        } catch (e) {}
      });
    }
    return originalXHROpen.call(this, method, url, ...rest);
  };

  const originalFetch = window.fetch;
  window.fetch = async function (input, init) {
    const response = await originalFetch.call(this, input, init);
    const url = typeof input === 'string' ? input : input.url;
    if (url.includes('permission/document/actions/state')) {
      try {
        const data = await response.clone().json();
        if (data.data?.actions?.copy !== 1) {
          data.data.actions.copy = 1;
          return new Response(JSON.stringify(data), {
            status: response.status,
            statusText: response.statusText,
            headers: response.headers
          });
        }
      } catch (e) {}
    }
    return response;
  };

  // ==================== 2. 核心复制功能 ====================

  document.addEventListener('contextmenu', (e) => e.stopPropagation(), true);

  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'c') {
      const selection = window.getSelection();
      if (!selection || !selection.toString()) return;

      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();

      const text = selection.toString();
      navigator.clipboard.writeText(text).then(() => {
        showToast('已复制');
      }).catch(() => {
        fallbackCopy(text);
      });
    }
  }, true);

  function fallbackCopy(text) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;left:-9999px';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    ta.remove();
    showToast('已复制');
  }

  ['copy', 'cut'].forEach(type => {
    document.addEventListener(type, e => e.stopPropagation(), true);
  });

  // ==================== 3. 图片右键菜单 ====================

  function setupImageMenu() {
    document.addEventListener('contextmenu', (e) => {
      const img = e.target.closest('img');
      if (!img) return;

      document.getElementById('feishu-menu')?.remove();

      const menu = document.createElement('div');
      menu.id = 'feishu-menu';
      menu.innerHTML = `
        <div style="position:fixed;left:${e.clientX}px;top:${e.clientY}px;background:#fff;border:1px solid #ddd;border-radius:6px;box-shadow:0 2px 10px rgba(0,0,0,.15);z-index:999999;padding:4px 0;min-width:100px;font-size:14px">
          <div class="fm-item" data-action="download" style="padding:8px 16px;cursor:pointer;color:#333">下载图片</div>
        </div>`;
      document.body.appendChild(menu);

      menu.querySelector('.fm-item').onmouseenter = function() { this.style.background = '#f5f5f5'; };
      menu.querySelector('.fm-item').onmouseleave = function() { this.style.background = ''; };

      menu.querySelector('[data-action="download"]').onclick = () => {
        const a = document.createElement('a');
        a.href = img.src;
        a.download = 'feishu-img-' + Date.now() + '.png';
        a.click();
        menu.remove();
      };

      setTimeout(() => document.addEventListener('click', () => menu.remove(), { once: true }), 0);
    });
  }

  // ==================== 4. 隐藏权限弹窗 ====================

  function hidePermDialog() {
    const obs = new MutationObserver((muts) => {
      muts.forEach(m => m.addedNodes.forEach(n => {
        if (n.nodeType === 1 && (n.textContent?.includes('父级页面权限') || n.textContent?.includes('如需复制请联系'))) {
          n.remove();
        }
      }));
    });
    document.body && obs.observe(document.body, { childList: true, subtree: true });
  }

  // ==================== 5. 去除水印 ====================

  function addStyle(css) {
    const s = document.createElement('style');
    s.textContent = css;
    (document.head || document.documentElement).appendChild(s);
  }

  addStyle(`
    [class*="watermark"], .ssrWaterMark, [class*="TIAWBFTROSIDWYKTTIAW"], #watermark-cache-container {
      background-image: none !important; opacity: 0 !important;
    }
    * { -webkit-user-select: text !important; user-select: text !important; }
  `);

  function setupWatermarkObserver() {
    const obs = new MutationObserver((muts) => {
      muts.forEach(m => m.addedNodes.forEach(n => {
        if (n.nodeType === 1 && (n.className?.includes?.('watermark') || n.id === 'watermark-cache-container')) {
          n.remove();
        }
      }));
    });
    document.body && obs.observe(document.body, { childList: true, subtree: true });
  }

  // ==================== 6. Toast 提示 ====================

  function showToast(msg) {
    const t = document.createElement('div');
    t.textContent = msg;
    t.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);background:rgba(0,0,0,.75);color:#fff;padding:10px 20px;border-radius:6px;z-index:999999;font-size:14px';
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 1500);
  }

  // ==================== 初始化 ====================

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      setupImageMenu();
      setupWatermarkObserver();
      hidePermDialog();
    });
  } else {
    setupImageMenu();
    setupWatermarkObserver();
    hidePermDialog();
  }

})();
