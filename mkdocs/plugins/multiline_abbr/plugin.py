import html
import re
from pathlib import Path
from mkdocs.plugins import BasePlugin

# 針對「條、項、款、目、次」與常見編號的層級規則
LEVEL_RULES = [
    (re.compile(r"^\s*第\s*\d+[-－]?\d*\s*條"), 0),
    (re.compile(r"^\s*第\s*\d+\s*項[：:]"), 1),
    (re.compile(r"^\s*第\s*\d+\s*款[：:]"), 2),
    (re.compile(r"^\s*第\s*\d+\s*目[：:]"), 3),
    (re.compile(r"^\s*第\s*\d+\s*次[：:]"), 4),
    # 中文數字條列（全形頓號）
    (re.compile(r"^\s*[一二三四五六七八九十]+、"), 2),
    # 括號數字/字母
    (re.compile(r"^\s*（\d+）"), 3),
    (re.compile(r"^\s*\(\d+\)"), 3),
    (re.compile(r"^\s*（[一二三四五六七八九十]+）"), 3),
    (re.compile(r"^\s*\([a-zA-Z]\)"), 4),
    # 阿拉伯數字+頓號
    (re.compile(r"^\s*\d+、"), 2),
]

def detect_level(line: str) -> int:
    for pat, lvl in LEVEL_RULES:
        if pat.search(line):
            return lvl
    return 0

def lines_to_html(lines):
    """將多行內容依規則縮排並轉為 tooltip HTML。"""
    out = []
    for raw in lines:
        s = raw.rstrip()
        lvl = detect_level(s)
        # 保留原文字，轉義後再用 <span> 包裝，縮排以 CSS 控制
        esc = html.escape(s)
        out.append(f'<div class="mlabbr-line mlabbr-l{lvl}">{esc}</div>')
    return "".join(out)

ABBR_DEF_RE = re.compile(r"^\*\[([^\]]+)\]\s*:\s*$")  # *[KEY]:

class MultilineAbbrPlugin(BasePlugin):
    def on_config(self, config):
        # 讀 includes/abbreviations.md
        root = Path(config.config_file_path).parent
        self.abbr_file = root / "includes" / "abbreviations.md"
        self.abbr_map = self._load_abbrs(self.abbr_file) if self.abbr_file.exists() else {}
        # 建立整頁替換的正則（避開空集合）
        if self.abbr_map:
            # 鍵可能含連字號，不能簡單用 \b，改用邊界：前後不得是字母或數字
            keys = sorted(self.abbr_map.keys(), key=len, reverse=True)
            pattern = r"(?<![A-Za-z0-9])(" + "|".join(map(re.escape, keys)) + r")(?![A-Za-z0-9])"
            self.key_re = re.compile(pattern)
        else:
            self.key_re = None
        print(f">>> multiline_abbr plugin loaded successfully ({len(self.abbr_map)} items)")
        return config

    
    def _load_abbrs(self, path: Path):
        """解析 *[KEY]: 區塊，支援多行，並忽略 <!-- ... --> 註解。"""
        text = path.read_text(encoding="utf-8")
        # 移除整段 HTML 註解
        text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
        abbr_map = {}
        key = None
        buf = []
        for line in text.splitlines():
            # 跳過單行註解（即使沒封閉區塊）
            if re.match(r"^\s*<!--", line):
                continue
            m = ABBR_DEF_RE.match(line)
            if m:
                if key and buf:
                    abbr_map[key] = lines_to_html(buf)
                key = m.group(1).strip()
                buf = []
                continue
            if key is not None:
                if line.strip() == "" and (not buf or buf[-1].strip() == ""):
                    continue
                buf.append(line)
        if key and buf:
            abbr_map[key] = lines_to_html(buf)
        return abbr_map

    def _replace_in_plain(self, text: str):
        """對普通段落替換鍵為帶 tooltip 的 span。"""
        if not self.key_re:
            return text

        def repl(m):
            k = m.group(1)
            html_title = self.abbr_map.get(k)
            if not html_title:
                return k
            # 用 data-mlabbr 承載 HTML，前端以自訂 tooltip 顯示多行
            return f'<span class="mlabbr" data-mlabbr="{html.escape(html_title)}">{k}</span>'

        return self.key_re.sub(repl, text)

    def on_page_markdown(self, markdown, **kwargs):
        """避開程式碼區塊只處理正文。"""
        parts = re.split(r"(```.*?```|~~~.*?~~~)", markdown, flags=re.S)
        for i in range(0, len(parts), 2):  # 偶數索引為非程式碼
            parts[i] = self._replace_in_plain(parts[i])
        return "".join(parts)

    def on_post_page(self, output_content, **kwargs):
        """注入 CSS + JS，使 tooltip 渲染為真正 HTML。"""
        style = """<style id="mlabbr-style">
.mlabbr {
  text-decoration: underline dotted;
  cursor: help;
}

.mlabbr-tooltip {
  display: none;
  position: fixed;
  z-index: 999;
  background: var(--md-default-bg-color, #fff);
  color: var(--md-typeset-color, #222);
  border: 1px solid var(--md-default-fg-color--lighter, #ddd);
  box-shadow: 0 4px 12px rgba(0, 0, 0, .15);
  padding: 0.75rem 1rem;
  border-radius: 6px;
  font-size: 1.3em;
  line-height: 1.65;
  pointer-events: auto;
  width: max-content;       /* 根據內容自動寬度 */
  max-width: 70ch;          /* 最長不超過約70個字 */
  max-height: 70vh;
  overflow: auto;
  white-space: normal;
  overflow-wrap: break-word;
}

/* 條項款目縮進 */
.mlabbr-line { display: block; }
/* 讓每條之間多一點間距，但第一條不加 */
.mlabbr-line + .mlabbr-line {
  margin-top: 0.5em;   /* 可自行調整，例如 0.4em、0.6em */
}
.mlabbr-l0 { margin-left: 0; }
.mlabbr-l1 { margin-left: 1.2em; }
.mlabbr-l2 { margin-left: 2.4em; }
.mlabbr-l3 { margin-left: 3.6em; }
.mlabbr-l4 { margin-left: 4.8em; }
</style>

<script id="mlabbr-script">
document.addEventListener("DOMContentLoaded", () => {
  const tip = document.createElement("div");
  tip.className = "mlabbr-tooltip";
  document.body.appendChild(tip);

  let pinned = false;
  let owner = null;
  let hideTimer = null;

  const place = (anchor) => {
    tip.style.width = "max-content";
    tip.style.height = "auto";
    tip.style.display = "block";

    const rect = anchor.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const m = 10;

    const naturalW = tip.offsetWidth;
    const naturalH = tip.offsetHeight;

    let left = rect.left + rect.width / 2 - naturalW / 2; // 儘量居中
    if (left + naturalW + m > vw) left = vw - naturalW - m;
    if (left < m) left = m;

    let top = rect.bottom + m;
    if (top + naturalH + m > vh) top = rect.top - naturalH - m;
    if (top < m) top = m;

    tip.style.left = `${left}px`;
    tip.style.top = `${top}px`;
  };

  const showFor = (span) => {
    owner = span;
    tip.innerHTML = span.getAttribute("data-mlabbr") || "";
    tip.style.display = "block";
    place(span);
  };

  const requestHide = () => {
    if (pinned) return;
    clearTimeout(hideTimer);
    hideTimer = setTimeout(() => {
      if (!pinned) {
        tip.style.display = "none";
        owner = null;
      }
    }, 120);
  };

  document.querySelectorAll(".mlabbr").forEach(span => {
    const html = span.getAttribute("data-mlabbr");
    if (!html) return;

    span.addEventListener("mouseenter", () => { if (!pinned) showFor(span); });
    span.addEventListener("mousemove", () => { if (!pinned && owner === span) place(span); });
    span.addEventListener("mouseleave", requestHide);
    span.addEventListener("click", e => {
      e.preventDefault();
      if (pinned && owner === span) { pinned = false; requestHide(); }
      else { pinned = true; showFor(span); }
    });
  });

  tip.addEventListener("mouseenter", () => clearTimeout(hideTimer));
  tip.addEventListener("mouseleave", requestHide);

  document.addEventListener("click", e => {
    if (!pinned) return;
    if (e.target === tip || (owner && owner.contains(e.target))) return;
    pinned = false;
    requestHide();
  });

  document.addEventListener("keydown", e => {
    if (e.key === "Escape") {
      pinned = false;
      requestHide();
    }
  });
});
</script>"""
        return output_content.replace("</body>", style + "</body>")