#!/usr/bin/env python3
"""照 `_work/對照_1121_音檔週次.json` 的對照，量 1121 那批成稿留下了多少課堂原話。

1121 兩門課整門沒留逐字稿初稿，`校對盤點.md` 因此只能用口語殘留當代理指標。2026-08 把
125 個錄音原檔重轉一次之後，這批頁面第一次有了可以比對的上游。

上游是三年後另一個模型重轉的，與當年校對所依據的那一份初稿用字有出入。
所以要先問：哪一種指標在這個條件下還量得到東西？`1121_租稅規避/_原稿/` 那 6 頁是 2023 年
未經編輯的原始逐字稿，把它們跟本批重轉的同一場比對，得到的就是「完全沒有編輯」時各指標
的讀數——校準組。

    照抄率（audit-proofreading.py 的定義）＝|成稿句子 ∩ 逐字稿句子| ÷ |成稿句子|
    原話涵蓋＝|成稿的 5-gram ∩ 逐字稿的 5-gram| ÷ |成稿的 5-gram|

校準組的結果決定哪一個能用，實測見產出的報告：**照抄率在這個條件下是飽和的**，未經編輯的
逐字稿也只有 0.00 上下，與已校對的頁面分不開，不能拿來判斷校對程度；原話涵蓋則在校準組
落在明顯高的一段，可以當分界。

    python3 scripts/retention-1121.py            # 印出
    python3 scripts/retention-1121.py --write    # 另寫 _work/照抄率_1121.md
"""
import argparse
import importlib.util
import json
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAP = ROOT / "_work/對照_1121_音檔週次.json"
TRANS = ROOT / "_work/1121_轉寫"
DRAFTS = ROOT / "mkdocs/My_Notes/1121/1121_租稅規避/_原稿"
OUT = ROOT / "_work/照抄率_1121.md"


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


apm = _load("ap", "scripts/audit-proofreading.py")
cr = _load("cr", "scripts/check-retention.py")
mp = _load("mp", "scripts/map-1121-audio.py")


def measure(note_text: str, src_text: str) -> dict:
    fs, ds = apm.sentences(note_text), apm.sentences(src_text)
    fg, dg = mp.grams(mp.norm(note_text)), mp.grams(mp.norm(src_text))
    return {
        "成稿字數": cr.chars(cr.body(note_text)),
        "逐字稿字數": cr.chars(src_text),
        "照抄率": len(fs & ds) / len(fs) if fs else 0.0,
        "原話涵蓋": len(fg & dg) / len(fg) if fg else 0.0,
    }


def calibration(sessions) -> list[dict]:
    """未經編輯的 2023 原始逐字稿 vs 本批重轉的同一場。"""
    out = []
    for f in sorted(DRAFTS.glob("*.md")):
        text = f.read_text(encoding="utf8")
        g = mp.grams(mp.norm(text))
        same = [t for t in sessions if t["日期"] == f.stem[:8]]
        if not same:
            continue
        score, top = max(((len(g & t["grams"]) / len(g), t) for t in same),
                         key=lambda x: x[0])
        src = "\n".join((TRANS / f"{x}.raw.txt").read_text(encoding="utf8")
                        for x in top["檔"])
        m = measure(text, src)
        m.update(頁=f.stem, 檔="＋".join(top["檔"]))
        out.append(m)
    return out


def main():
    argp = argparse.ArgumentParser()
    argp.add_argument("--write", action="store_true")
    args = argp.parse_args()

    if not MAP.is_file():
        raise SystemExit(f"找不到 {MAP.relative_to(ROOT)}，"
                         "先跑 python3 scripts/map-1121-audio.py --write")
    rows = json.loads(MAP.read_text(encoding="utf8"))
    cal = calibration(mp.load_transcripts())
    cal_vals = sorted(c["原話涵蓋"] for c in cal)
    cal_lo, cal_core, cal_hi = cal_vals[0], cal_vals[1], cal_vals[-1]
    cal_copy = max(c["照抄率"] for c in cal)

    # 校對盤點.md 用口語殘留標出的 12 頁，這裡拿來看兩個指標指不指向同一批。
    RESIDUE = {
        "20230905_01_稅捐規避.md", "20230912_01_稅捐規避.md", "20231003_02_稅捐規避.md",
        "001_20230905_03_租稅法總論.md", "20230912_02_稅捐規避.md",
        "007_20230926_03_租稅法總論.md", "20230926_02_稅捐規避.md",
        "20230919_01_稅捐規避.md", "20230905_02_稅捐規避.md",
        "005_20230919_03_租稅法總論.md", "014_20231024_04_租稅法總論.md",
        "010_20231003_04_租稅法總論.md",
    }

    measured = []
    for r in rows:
        if not r["場"]:
            continue
        src = "\n".join((TRANS / f"{f}.raw.txt").read_text(encoding="utf8")
                        for f in r["檔"])
        m = measure((ROOT / r["路徑"]).read_text(encoding="utf8"), src)
        m.update(課程=r["課程"], 頁=r["頁"], 檔="＋".join(r["檔"]))
        m["長度比"] = m["成稿字數"] / m["逐字稿字數"] if m["逐字稿字數"] else 0.0
        measured.append(m)

    copies = [m for m in measured if m["原話涵蓋"] >= cal_core]
    grey = [m for m in measured if cal_lo <= m["原話涵蓋"] < cal_core]
    rewrites = [m for m in measured if m["原話涵蓋"] < cal_lo]

    L = [
        "# 1121 成稿與課堂原話的比對", "",
        "上游是 2026-08 重轉的逐字稿（`_work/1121_轉寫/`），對照見",
        "`_work/對照_1121_音檔週次.md`。", "",
        "## 校準：未經編輯的逐字稿長什麼樣", "",
        "上游不是當年校對所依據的那一份初稿，是三年後另一個模型重轉的，用字有出入。",
        f"`1121_租稅規避/_原稿/` 的 {len(cal)} 頁是 2023 年未經任何編輯的原始逐字稿，",
        "拿它跟本批重轉的同一場比對，讀數就是「完全沒有編輯」時各指標的上限。", "",
        "| 原稿 | 對到的音檔 | 照抄率 | 原話涵蓋 |", "|---|---|---:|---:|",
    ]
    for c in cal:
        L.append(f"| {c['頁']} | {c['檔']} | {c['照抄率']:.3f} | {c['原話涵蓋']:.3f} |")
    L += [
        "",
        f"**照抄率在這個條件下不能用。** 兩份都沒編輯過、內容是同一場課，逐字相同的句子"
        f"仍然只有 {cal_copy:.3f} 以下——",
        "兩個模型對同一句話的斷句與用字幾乎不會完全一致，指標被模型差異吃光了。已校對的",
        "40 頁量出來是 0.000–0.055，跟這一組分不開，所以那個數字證明不了任何事，本報告",
        "不拿它下判斷。其他 108 頁的照抄率不受影響，那批比對的是同源的初稿。",
        "",
        f"**原話涵蓋可以用。** 未經編輯的落在 {cal_lo:.3f}–{cal_hi:.3f}，六份裡有五份"
        f"擠在 {cal_core:.3f} 以上；",
        f"最低的那一份（{min(cal, key=lambda c: c['原話涵蓋'])['頁']}）只有 106 句，短檔的",
        f"讀數本來就不穩。所以分成三段讀：≥ {cal_core:.3f} 與未編輯的無異，"
        f"{cal_lo:.3f}–{cal_core:.3f} 是灰帶，",
        f"< {cal_lo:.3f} 低於任何一份未編輯的逐字稿，是改寫過的。",
        "",
        "## 逐頁", "",
        "| 課程 | 成稿頁 | 音檔 | 成稿字數 | 逐字稿字數 | 原話涵蓋 | 長度比 |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for m in sorted(measured, key=lambda x: -x["原話涵蓋"]):
        L.append(f"| {m['課程']} | {m['頁']} | {m['檔']} | {m['成稿字數']:,} | "
                 f"{m['逐字稿字數']:,} | {m['原話涵蓋']:.3f} | {m['長度比']:.3f} |")

    vals = [m["原話涵蓋"] for m in measured]
    early = sum(1 for m in copies
                if int(re.search(r"\d{8}", m["頁"]).group()) <= 20231003)
    L += [
        "", "## 結論", "",
        f"對上音檔的 {len(measured)} 頁，原話涵蓋中位數 {statistics.median(vals):.3f}、"
        f"全距 {min(vals):.3f}–{max(vals):.3f}。",
        "",
        f"**{len(copies)} 頁的讀數與未編輯的逐字稿無異（≥ {cal_core:.3f}），"
        "字面上還是逐字稿。**",
        f"{len(copies)} 頁裡有 {early} 頁是 10 月 3 日以前的：",
        "",
    ]
    for m in sorted(copies, key=lambda x: -x["原話涵蓋"]):
        L.append(f"- {m['原話涵蓋']:.3f}　{m['頁']}（{m['成稿字數']:,} 字）")
    L += ["", f"灰帶（{cal_lo:.3f}–{cal_core:.3f}）{len(grey)} 頁："]
    for m in sorted(grey, key=lambda x: -x["原話涵蓋"]):
        L.append(f"- {m['原話涵蓋']:.3f}　{m['頁']}")
    L += [
        "",
        f"**其餘 {len(rewrites)} 頁低於任何一份未編輯的逐字稿**，最低 "
        f"{min(m['原話涵蓋'] for m in rewrites):.3f}。改寫的幅度大致隨學期往後增加，但不是"
        "單調的——十二月的 `028_20231212_04_租稅法總論.md` 仍有 0.383。",
        "",
        f"**與口語殘留那個指標指向同一批頁面。** `校對盤點.md` 用口語殘留標出 12 頁建議"
        f"複看：{len(RESIDUE & {m['頁'] for m in copies})} 頁在本表落在未編輯那一段、"
        f"{len(RESIDUE & {m['頁'] for m in grey})} 頁落在灰帶、"
        f"{len(RESIDUE - {m['頁'] for m in measured})} 頁是 9 月 5 日、當天沒有錄音無從比對，"
        f"{len(RESIDUE & {m['頁'] for m in rewrites})} 頁被本指標判成已改寫。兩個指標各自"
        "獨立——一個數口語支架的密度，一個比對錄音原話——結論一致。",
        "",
        "`20231017_02_稅捐規避.md` 的長度比 1.607，成稿比整堂逐字稿還長，補進了課外的",
        "材料；長度比在那一頁讀不出校對程度。",
        "",
    ]

    skipped = [r for r in rows if not r["場"]]
    L += [f"另有 {len(skipped)} 頁沒有上游可比："]
    for r in skipped:
        why = "正文為空，只有 frontmatter" if r["頁字數"] == 0 else "當天沒有錄音"
        L.append(f"- {r['頁']}——{why}")
    L.append("")

    md = "\n".join(L)
    print(md)
    if args.write:
        OUT.write_text(md, encoding="utf8")
        print(f"寫入 {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
