#!/usr/bin/env python3
"""逐字稿的字形正規化：把辨識引擎吐出來的日式／港式字形收回台灣通用形。

    python3 scripts/normalize-glyphs.py            # 只檢查，命中就 exit 1 並列出檔案:行號
    python3 scripts/normalize-glyphs.py --fix      # 就地改寫 mkdocs/My_Notes 底下的 .md

whisper large-v3-turbo 經 opencc s2twp 之後仍會留下「説」「麽」「爲」這幾個字：它們在
opencc 眼裡已經是繁體，不會被轉。2026-09-13 在 tax.phenomcanvas.com 搜「通說」命中 16 筆、
搜「通説」命中 2 筆，兩組互不相見，成因就在這裡。判定收在母本這一層，
batch_transcribe.py 轉完 opencc 接著套同一張表，之後的稿不會再帶進來。

不改的東西：
- 引言行（`>` 開頭）照錄，不動。
- SKIP 清單裡的檔：PDF 抽出來的他人文章，字形是原檔的，照錄。
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "mkdocs" / "My_Notes"

# 左邊是引擎吐出來的形，右邊是通用形。只收在逐字稿裡實際出現過的組。
TABLE = {
    "説": "說",
    "麽": "麼",
    "爲": "為",
    "内": "內",
    "値": "值",
    "眞": "真",
    "産": "產",
}

# 相對 DOCS 的路徑。每一條寫明為什麼照錄。
SKIP = {
    # 謝哲勝那篇評釋由 PDF 抽出，字形隨原檔，屬引文。
    "_老師要的其他文件/借名登記/借名登記文章中提到判決的段落.md",
}

_TRANS = str.maketrans(TABLE)
_CHARS = set(TABLE)


def normalize_glyphs(text):
    """給 batch_transcribe.py 用：整段轉錄文字過一次表。"""
    return text.translate(_TRANS)


def _iter_files():
    for p in sorted(DOCS.rglob("*.md")):
        if p.relative_to(DOCS).as_posix() in SKIP:
            continue
        yield p


def _process(path, fix):
    lines = path.read_text(encoding="utf-8").split("\n")
    hits = []
    out = []
    for i, line in enumerate(lines, 1):
        if line.lstrip().startswith(">") or not (_CHARS & set(line)):
            out.append(line)
            continue
        hits.append((i, line))
        out.append(line.translate(_TRANS) if fix else line)
    if fix and hits:
        path.write_text("\n".join(out), encoding="utf-8")
    return hits


def main(argv):
    fix = "--fix" in argv
    total = 0
    files = 0
    for path in _iter_files():
        hits = _process(path, fix)
        if not hits:
            continue
        files += 1
        total += len(hits)
        rel = path.relative_to(REPO)
        for i, line in hits:
            found = "".join(sorted(_CHARS & set(line)))
            print(f"{rel}:{i}: {found}")
    if total == 0:
        print("字形檢查：mkdocs/My_Notes 沒有表上的字形")
        return 0
    if fix:
        print(f"字形改寫：{files} 檔 {total} 行已收回通用形")
        return 0
    print(f"字形檢查：{files} 檔 {total} 行帶引擎字形；跑 --fix 收回", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
