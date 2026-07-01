(function () {
  document.documentElement.classList.add("copy-guard");

  function getScroller(sideSelector) {
    const side = document.querySelector(sideSelector);
    if (!side) return null;
    return (
      side.querySelector(".md-sidebar__scrollwrap") ||
      side.querySelector(".md-sidebar__inner") ||
      side
    );
  }

  function getBestActiveLink(scroller) {
    if (!scroller) return null;
    return (
      scroller.querySelector(".md-nav__link--active") ||
      scroller.querySelector(".md-nav__item--active > .md-nav__link") ||
      null
    );
  }

  function keepActiveCentered(sideSelector, extraTop = 0) {
    const scroller = getScroller(sideSelector);
    const active = getBestActiveLink(scroller);
    if (!scroller || !active) return;

    const activeRect = active.getBoundingClientRect();
    const containerRect = scroller.getBoundingClientRect();
    const pad = 16;

    const outAbove = activeRect.top < containerRect.top + pad + extraTop;
    const outBelow = activeRect.bottom > containerRect.bottom - pad;
    if (!outAbove && !outBelow) return;

    const delta =
      (activeRect.top - containerRect.top) -
      (containerRect.height / 2 - activeRect.height / 2) -
      extraTop;

    scroller.scrollTo({
      top: Math.max(0, scroller.scrollTop + delta),
      behavior: "auto",
    });
  }

  // 取得右側 TOC 的可滾動容器
  function getTocScroller() {
    return getScroller(".md-sidebar--secondary");
  }

  // 取得當前 active 的 TOC 鏈接
  function getActiveLink(scroller) {
    if (!scroller) return null;
    return (
      scroller.querySelector(".md-nav__link--active") ||
      (function () {
        const li = scroller.querySelector(".md-nav__item--active > a.md-nav__link");
        return li || null;
      })()
    );
  }

  // 若 active 超出可視範圍，只把它捲回可視區，不主動置中
  function ensureActiveVisible() {
    const scroller = getTocScroller();
    const active = getActiveLink(scroller);
    if (!scroller || !active) return;

    const a = active.getBoundingClientRect();
    const c = scroller.getBoundingClientRect();
    const pad = 12; // 上下緩衝

    const outAbove = a.top < c.top + pad;
    const outBelow = a.bottom > c.bottom - pad;

    if (outAbove) {
      scroller.scrollTo({
        top: Math.max(0, scroller.scrollTop - ((c.top + pad) - a.top)),
        behavior: "auto",
      });
    } else if (outBelow) {
      scroller.scrollTo({
        top: Math.max(0, scroller.scrollTop + (a.bottom - (c.bottom - pad))),
        behavior: "auto",
      });
    }
  }

  // 用 rAF 節流，避免頻繁觸發
  let scheduled = false;
  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      ensureActiveVisible();
      keepActiveCentered(".md-sidebar--primary", 24);
    });
  }

  // 綁定：右側 TOC 結構或 active class 變化時檢查
  function bindObserver() {
    [".md-sidebar--secondary", ".md-sidebar--primary"].forEach((selector) => {
      const scroller = getScroller(selector);
      if (!scroller) return;
      const nav =
        scroller.querySelector(selector === ".md-sidebar--secondary" ? ".md-nav--secondary" : ".md-nav--primary") ||
        scroller;
      const mo = new MutationObserver(schedule);
      mo.observe(nav, { subtree: true, attributes: true, attributeFilter: ["class", "hidden"] });
    });
  }

  // 初次與延遲嘗試（應對 SPA 導航與延遲掛載）
  document.addEventListener("DOMContentLoaded", () => {
    schedule();
    bindObserver();
    // 再保險：首秒多次嘗試
    let tries = 6;
    const id = setInterval(() => {
      schedule();
      bindObserver();
      if (--tries <= 0) clearInterval(id);
    }, 200);
  });

  // Material 的即時導航事件（若啟用 navigation.instant 時更穩）
  document.addEventListener("navigation", schedule);
})();

(function () {
  const storageKey = "taxko-font-mode-v2";
  const modes = {
    typewriter: {
      className: "taxko-font-typewriter",
      label: "字體：打字機",
      title: "目前使用打字機字體，點一下切換成明體",
    },
    readable: {
      className: "taxko-font-readable",
      label: "字體：明體",
      title: "目前使用明體，點一下切回打字機字體",
    },
  };

  function getMode() {
    const saved = window.localStorage && localStorage.getItem(storageKey);
    return saved === "readable" ? "readable" : "typewriter";
  }

  function setMode(mode) {
    const html = document.documentElement;
    html.classList.remove(modes.typewriter.className, modes.readable.className);
    html.classList.add(modes[mode].className);
    if (window.localStorage) localStorage.setItem(storageKey, mode);
    updateButton(mode);
  }

  function updateButton(mode) {
    const button = document.querySelector(".taxko-font-toggle");
    if (!button) return;
    button.textContent = modes[mode].label;
    button.title = modes[mode].title;
    button.setAttribute("aria-label", modes[mode].title);
  }

  function ensureButton() {
    if (document.querySelector(".taxko-font-toggle")) {
      updateButton(getMode());
      return;
    }

    const button = document.createElement("button");
    button.type = "button";
    button.className = "taxko-font-toggle";
    button.addEventListener("click", () => {
      setMode(getMode() === "typewriter" ? "readable" : "typewriter");
    });
    document.body.appendChild(button);
    updateButton(getMode());
  }

  setMode(getMode());
  document.addEventListener("DOMContentLoaded", ensureButton);
  document.addEventListener("navigation", ensureButton);
})();

(function () {
  const blockedKeys = new Set(["c", "x", "p", "s", "u", "a"]);

  function isEditableTarget(target) {
    if (!target) return false;
    const el = target.nodeType === Node.TEXT_NODE ? target.parentElement : target;
    if (!el) return false;
    return Boolean(
      el.closest("input, textarea, select, [contenteditable='true'], .md-search")
    );
  }

  function blockEvent(event) {
    if (isEditableTarget(event.target)) return;
    event.preventDefault();
    event.stopPropagation();
  }

  ["contextmenu", "copy", "cut", "selectstart", "dragstart"].forEach((type) => {
    document.addEventListener(type, blockEvent, true);
  });

  document.addEventListener(
    "keydown",
    function (event) {
      if (isEditableTarget(event.target)) return;

      const key = event.key.toLowerCase();
      const command = event.ctrlKey || event.metaKey;
      const devToolsKey =
        event.key === "F12" ||
        (command && event.shiftKey && ["i", "j", "c"].includes(key));

      if ((command && blockedKeys.has(key)) || devToolsKey) {
        event.preventDefault();
        event.stopPropagation();
      }
    },
    true
  );
})();
