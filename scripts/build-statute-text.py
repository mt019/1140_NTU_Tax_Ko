#!/usr/bin/env python3
"""把 `_Material/法源/個別法源PDF/` 的法源 PDF 轉成純文字，供 grep 與查條號用。

為什麼要這個：核對筆記裡的條號時，唯一夠格的依據是條文本身。PDF 沒辦法 grep，
每次都重新抽一遍又慢又留不下來。這支把 53 份 PDF 一次抽成 .txt 放進
`_Material/法源/個別法源文字/`，跟 PDF 同名同分類，之後 `lookup-article.py`
直接吃它。

抽取用 pdftotext -layout（poppler）。`-layout` 是必要的：法條 PDF 的項號（1、2、3）
排在左欄，不保留版面就會跟內文黏在一起，項次會判斷錯。

    python3 scripts/build-statute-text.py           # 只補新的或 PDF 較新的
    python3 scripts/build-statute-text.py --force   # 全部重抽
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "_Material/法源/個別法源PDF"
OUT = ROOT / "_Material/法源/個別法源文字"
SKIP_DIRS = {"索引"}


TITLE_RE = re.compile(r"法規名稱[：:]\s*(?:\(廢\)|（廢）)?\s*(\S+)")


def check_names():
    """比對每份文字檔開頭的「法規名稱」與檔名。

    2026-08-09 抓到 `法律/行政訴訟法.pdf` 整份放的是已廢止的國家總動員法。條號查不到
    的訊息只報得出「該檔收到第 N 條」，報不出「這份根本是別部法」，於是那筆對不上被
    當成條號寫錯查了兩輪。檔名是誰放的、內容是誰決定的，要各自核。

    有些來源（作業要點、財政部主管法規共用系統的列印頁）開頭沒有這一行，跳過不判。
    """
    bad = []
    for txt in sorted(OUT.rglob("*.txt")):
        head = txt.read_text(encoding="utf-8", errors="replace")[:400]
        m = TITLE_RE.search(head)
        if not m:
            continue
        title = m.group(1)
        if title != txt.stem and txt.stem not in title and title not in txt.stem:
            bad.append((txt.relative_to(OUT), title))
    if bad:
        print(f"\n以下 {len(bad)} 份的內容與檔名不是同一部法：")
        for rel, title in bad:
            print(f"　{rel}　內容其實是「{title}」")
    return bad


def main():
    force = "--force" in sys.argv
    if not SRC.is_dir():
        sys.exit(f"找不到來源目錄：{SRC}")
    if subprocess.run(["which", "pdftotext"], capture_output=True).returncode:
        sys.exit("需要 pdftotext（poppler）：brew install poppler")

    made, skipped, failed = 0, 0, []
    for pdf in sorted(SRC.rglob("*.pdf")):
        rel = pdf.relative_to(SRC)
        if rel.parts[0] in SKIP_DIRS:
            continue
        txt = OUT / rel.with_suffix(".txt")
        if txt.exists() and not force and txt.stat().st_mtime >= pdf.stat().st_mtime:
            skipped += 1
            continue
        txt.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(["pdftotext", "-layout", str(pdf), str(txt)],
                           capture_output=True, text=True)
        if r.returncode or not txt.exists() or txt.stat().st_size == 0:
            failed.append(f"{rel}：{r.stderr.strip() or '抽出來是空的'}")
            continue
        made += 1

    print(f"抽出 {made} 份，略過 {skipped} 份（已是最新）")
    if failed:
        print(f"失敗 {len(failed)} 份：")
        for f in failed:
            print(f"　{f}")

    # 抽到空白檔是這類工作最典型的沉默失敗：命令回 0、檔案也在，就是沒有字。
    # 所以收尾一律驗內容，不驗命令有沒有成功。
    empties = [p for p in OUT.rglob("*.txt") if p.stat().st_size < 200]
    if empties:
        print(f"\n以下 {len(empties)} 份幾乎沒有字，可能是掃描檔、需要 OCR：")
        for p in empties:
            print(f"　{p.relative_to(OUT)}　{p.stat().st_size} bytes")

    mismatched = check_names()

    total = len(list(OUT.rglob("*.txt")))
    size = sum(p.stat().st_size for p in OUT.rglob("*.txt"))
    print(f"\n{OUT.relative_to(ROOT)} 現有 {total} 份，共 {size / 1024:.0f} KB")
    if failed or mismatched:
        sys.exit(1)


if __name__ == "__main__":
    main()
