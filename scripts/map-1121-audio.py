#!/usr/bin/env python3
"""把 1121 重轉的逐字稿對回 1121 的 57 頁成稿。

檔名帶日期，排得出候選；但同一天可能有六到八個錄音檔（週二早上另有一門沒寫筆記的課），
而成稿一天只有四頁，光靠順序會對錯。所以候選先按日期篩，再用字元 5-gram 的涵蓋度決定
哪一份音檔對哪一頁：

    涵蓋度 = |成稿的 5-gram ∩ 逐字稿的 5-gram| ÷ |成稿的 5-gram|

**判準是相對的不是絕對的。** 涵蓋度的絕對值隨那一頁被改寫的程度浮動，實測 0.049 到 0.687
都有（改寫得多的頁自然低）；但同一天之內，對的那一份與第二名一律差一個數量級以上
（0.208 對 0.010、0.049 對 0.006）。所以取最高分，且要求它至少是第二名的三倍、絕對值
至少 0.03；不滿足就不判，列進「待確認」。用絕對門檻會把改寫過的頁全部判成沒有音檔。

錄音中斷續錄的檔（`230919_1320_01` … `_06`）在比對前先按起始時間併成一場，否則一頁的
內容散在六份裡，每一份單看都不夠。

用 5-gram 而不用整句比對，是因為這批逐字稿是 2026-08 重轉的，與當年校對所依據的那一版
用字不同，整句比對會全部落空（那也是 check-retention.py 的句子涵蓋率在這 56 頁不可用的
原因，見 docs/主題重編/1121重轉.md）。

週末那四個檔名不帶日期（`國立臺灣大學 21`–`24`），日期取自 m4a 的 creation_time（UTC，
換算台北時間要加八小時）。

    python3 scripts/map-1121-audio.py                    # 印出對照表
    python3 scripts/map-1121-audio.py --write            # 另寫 _work/ 兩份產物
"""
import argparse
import json
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "mkdocs/My_Notes"
TRANS = ROOT / "_work/1121_轉寫"
AUDIO = Path.home() / "Documents/NTU/柯老師2023秋學期錄音原檔/錄音"
OUT_MD = ROOT / "_work/對照_1121_音檔週次.md"
OUT_JSON = ROOT / "_work/對照_1121_音檔週次.json"

NGRAM = 5
LEAD = 3.0              # 最高分至少要是第二名的幾倍
FLOOR = 0.03            # 最高分的絕對下限
NORMALISE = re.compile(r"[\s*_`>#\-–—「」『』（）()【】\[\]|,，、。：:；;！？!?~〜]+")
FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.S)
COMMENT = re.compile(r"<!--.*?-->", re.S)
DATED = re.compile(r"^(\d{6})_(\d{4})")
PART = re.compile(r"_\d\d$")            # 中斷續錄的分段編號
WEEKDAY = "一二三四五六日"

COURSES = [
    ("租稅法總論", DOCS / "1121/1121_租稅法總論", re.compile(r"^\d{3}_(\d{8})_(\d{2})_")),
    ("稅捐規避", DOCS / "1121/1121_租稅規避", re.compile(r"^(\d{8})_(\d{2})_")),
]


def norm(text: str) -> str:
    return NORMALISE.sub("", COMMENT.sub("", FRONTMATTER.sub("", text)))


def grams(text: str) -> set:
    return {text[i:i + NGRAM] for i in range(len(text) - NGRAM + 1)}


def srt_secs(path: Path) -> int:
    """.srt 最後一個時間碼＝該檔的實際長度，省一次 ffprobe。"""
    stamps = re.findall(r"--> (\d\d):(\d\d):(\d\d)", path.read_text(encoding="utf8"))
    if not stamps:
        return 0
    h, m, s = (int(x) for x in stamps[-1])
    return h * 3600 + m * 60 + s


def hms(secs: int) -> str:
    return f"{secs // 60}:{secs % 60:02d}"


def creation_date(stem: str) -> tuple[str, str]:
    """週末那批不帶日期的檔，日期時間取自 m4a metadata（UTC → 台北）。"""
    src = AUDIO / "weekend" / f"{stem}.m4a"
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format_tags=creation_time",
         "-of", "default=nw=1:nk=1", str(src)],
        capture_output=True, text=True).stdout.strip()
    t = datetime.strptime(out[:19], "%Y-%m-%dT%H:%M:%S") + timedelta(hours=8)
    return t.strftime("%Y%m%d"), t.strftime("%H:%M")


def load_transcripts() -> list[dict]:
    """一場課一筆；中斷續錄的 `_01`…`_06` 併回同一場。"""
    sessions: dict[str, dict] = {}
    for raw in sorted(TRANS.glob("*.raw.txt")):
        stem = raw.name[:-len(".raw.txt")]
        base = PART.sub("", stem)
        text = norm(raw.read_text(encoding="utf8"))
        m = DATED.match(base)
        if m:
            date, hhmm = "20" + m.group(1), f"{m.group(2)[:2]}:{m.group(2)[2:]}"
        else:
            date, hhmm = creation_date(stem)
        srt = TRANS / f"{stem}.srt"
        s = sessions.setdefault(base, {
            "場": base, "日期": date, "起": hhmm, "檔": [], "秒": 0,
            "字數": 0, "grams": set(),
        })
        s["檔"].append(stem)
        s["秒"] += srt_secs(srt) if srt.is_file() else 0
        s["字數"] += len(text)
        s["grams"] |= grams(text)
    return sorted(sessions.values(), key=lambda x: (x["日期"], x["起"]))


def load_pages() -> list[dict]:
    items = []
    for course, folder, pat in COURSES:
        for md in sorted(folder.glob("*.md")):
            m = pat.match(md.name)
            if not m:
                continue                     # index.md、合併檔、分主題檔
            text = norm(md.read_text(encoding="utf8"))
            items.append({
                "課程": course, "頁": md.name, "路徑": str(md.relative_to(ROOT)),
                "日期": m.group(1), "節": m.group(2),
                "字數": len(text), "grams": grams(text),
            })
    return sorted(items, key=lambda x: (x["日期"], x["課程"], x["節"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="另寫 _work/ 的 .md 與 .json")
    args = ap.parse_args()

    trans = load_transcripts()
    pages = load_pages()
    by_date = defaultdict(list)
    for t in trans:
        by_date[t["日期"]].append(t)

    rows, used = [], set()
    for p in pages:
        g = p["grams"]
        scored = sorted(((len(g & t["grams"]) / len(g) if g else 0.0, t)
                         for t in by_date.get(p["日期"], [])), key=lambda x: -x[0])
        top = scored[0] if scored else None
        second = scored[1][0] if len(scored) > 1 else 0.0
        ok = bool(top) and top[0] >= FLOOR and top[0] >= LEAD * max(second, 1e-9)
        if ok:
            used.add(top[1]["場"])
        rows.append({
            "課程": p["課程"], "頁": p["頁"], "路徑": p["路徑"], "日期": p["日期"],
            "節": p["節"], "頁字數": p["字數"],
            "場": top[1]["場"] if ok else None,
            "檔": top[1]["檔"] if ok else [],
            "起": top[1]["起"] if ok else "",
            "長度": hms(top[1]["秒"]) if ok else "",
            "逐字稿字數": top[1]["字數"] if ok else 0,
            "涵蓋": round(top[0], 3) if top else 0.0,
            "次高": round(second, 3),
        })

    orphan = [t for t in trans if t["場"] not in used]
    nomatch = [r for r in rows if not r["場"]]
    empty = [r for r in nomatch if r["頁字數"] == 0]

    lines = ["# 1121 音檔↔週次對照表", "",
             f"逐字稿 {sum(len(t['檔']) for t in trans)} 份併成 {len(trans)} 場，"
             f"成稿 {len(pages)} 頁。",
             f"對上 {len(pages) - len(nomatch)} 頁；沒有對應音檔的 {len(nomatch)} 頁，"
             f"其中 {len(empty)} 頁只有 frontmatter、正文是空的。",
             f"沒有成稿的音檔 {len(orphan)} 場。",
             f"判準：同日最高分且至少為第二名的 {LEAD:.0f} 倍、絕對值 ≥ {FLOOR}"
             f"（字元 {NGRAM}-gram 涵蓋度）。", ""]
    for course, _, _ in COURSES:
        lines += [f"## {course}", "",
                  "| 成稿頁 | 頁字數 | 音檔 | 起 | 長度 | 逐字稿字數 | 涵蓋度 | 次高 |",
                  "|---|---:|---|---|---:|---:|---:|---:|"]
        for r in rows:
            if r["課程"] != course:
                continue
            if not r["場"]:
                note = "正文為空" if r["頁字數"] == 0 else "無"
                lines.append(f"| {r['頁']} | {r['頁字數']:,} | {note} | | | | "
                             f"{r['涵蓋']} | {r['次高']} |")
                continue
            lines.append(
                f"| {r['頁']} | {r['頁字數']:,} | {'＋'.join(r['檔'])} | {r['起']} | "
                f"{r['長度']} | {r['逐字稿字數']:,} | {r['涵蓋']} | {r['次高']} |")
        lines.append("")

    lines += ["## 沒有成稿的音檔", "",
              "| 音檔 | 日期 | 星期 | 起 | 長度 | 字數 |", "|---|---|---|---|---:|---:|"]
    for t in orphan:
        d = datetime.strptime(t["日期"], "%Y%m%d")
        lines.append(f"| {'＋'.join(t['檔'])} | {d:%Y-%m-%d} | {WEEKDAY[d.weekday()]} | "
                     f"{t['起']} | {hms(t['秒'])} | {t['字數']:,} |")
    lines.append("")

    md = "\n".join(lines)
    print(md)
    if args.write:
        OUT_MD.write_text(md, encoding="utf8")
        for r in rows:
            r.pop("次高", None)
        OUT_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf8")
        print(f"寫入 {OUT_MD.relative_to(ROOT)} 與 {OUT_JSON.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
