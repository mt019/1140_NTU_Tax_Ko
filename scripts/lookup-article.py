#!/usr/bin/env python3
"""查條文，以及把一份成稿裡引到的所有法條抓出來一次核對。

依據是 `_Material/法源/個別法源文字/`（`build-statute-text.py` 從法源 PDF 抽的）。
筆記是逐字稿改寫來的，條號聽錯、記錯是這種材料的常態缺陷，而且錯的條號讀起來
完全正常——只有把條文調出來擺在旁邊才看得出來。

    python3 scripts/lookup-article.py 民法 761              # 印出該條全文
    python3 scripts/lookup-article.py 憲法 143 --項 3
    python3 scripts/lookup-article.py --scan <成稿.md>      # 抓出全部引用，逐條列首句
    python3 scripts/lookup-article.py --list                # 有哪些法源可查
    python3 scripts/lookup-article.py --names               # 掃登記在案的錯法名

`--scan` 每個引用印一行：法名、條號、條文開頭。條文開頭跟上下文對不起來的，就是
要回去查的地方。查無此條會標 ✗。
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "_Material/法源/個別法源文字"

CN = {"○": 0, "零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
      "六": 6, "七": 7, "八": 8, "九": 9}
NUM = r"[0-9０-９一二三四五六七八九十百千零○]"

# 筆記裡的簡稱。老師口語常用簡稱，法源檔名用全名。
ALIAS = {
    "憲法": "中華民國憲法",
    "納保法": "納稅者權利保護法",
    "稅稽法": "稅捐稽徵法",
    "遺贈稅法": "遺產及贈與稅法",
    "遺產稅法": "遺產及贈與稅法",
    "贈與稅法": "遺產及贈與稅法",
    "營業稅法": "加值型及非加值型營業稅法",
    "商會法": "商業會計法",
}

# 寫錯的法名／規費名稱。條號核得再仔細也抓不到這一類——法名寫錯時條號往往是對的，
# `--scan` 只會拿錯的法名去找檔案，找不到就當成「沒有這份法源」放過去。
#
# 不做通則（例如把「防治」一律當成「防制」）：水污染防治法、傳染病防治法本來就是
# 「防治」，通則會把對的改壞。發現一個加一條，每條都要寫依據。
MISNOMER = {
    "空氣污染防治法": ("空氣污染防制法", "全國法規資料庫 PCODE O0020001"),
    "空氣污染防治費": ("空氣污染防制費", "釋字426號解釋理由書"),
    "納稅人權利保護法": ("納稅者權利保護法", "全國法規資料庫 PCODE G0340142"),
    "稅捐徵收法": ("稅捐稽徵法", "全國法規資料庫 PCODE G0340001"),
}

# 校訂註解本來就要照抄錯的那個寫法（記原話），掃描時整段跳過。
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)

# 外國法的法名結尾常常跟我國的一樣：「威瑪憲法第134條」「德國所得稅法第23條」會被
# 法名樣式從中間切開，拿我國的條文去對，一定對不上又報不出原因。這些前綴一出現就跳過。
FOREIGN = ("德國", "威瑪", "日本", "美國", "法國", "韓國", "奧地利", "瑞士", "英國", "中國")


def cn2int(s: str) -> int:
    s = s.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    if s.isdigit():
        return int(s)
    total, section, digit = 0, 0, 0
    for ch in s:
        if ch in CN:
            digit = CN[ch]
        elif ch == "十":
            section += (digit or 1) * 10
            digit = 0
        elif ch == "百":
            section += (digit or 1) * 100
            digit = 0
        elif ch == "千":
            section += (digit or 1) * 1000
            digit = 0
    return total + section + digit


def corpus():
    if not CORPUS.is_dir():
        sys.exit(f"找不到 {CORPUS}，先跑 python3 scripts/build-statute-text.py")
    return sorted(CORPUS.rglob("*.txt"))


def cite_re():
    """法名用「已知法源」的窮舉來配，不用泛用的『……法』樣式。

    泛用樣式會把前面的字一起吃進去（『各位都學過民法』整串被當成法名），長的先排
    才不會讓『所得稅法』被『得稅法』之類的短名切掉。
    """
    names = sorted({p.stem for p in corpus()} | set(ALIAS), key=len, reverse=True)
    alt = "|".join(re.escape(n) for n in names)
    # 法名與條號之間只容半形／全形空格，不容換行。`\s*` 會跨行，於是小標
    # 「### 執行期間如何接到行政執行法」與下一段開頭的「第23條第1項」被接成
    # 一個引用，而那個 23 條講的是稅捐稽徵法。法名在段末、條號在下一段，
    # 兩者本來就不是同一個引用。
    return re.compile(
        rf"(?P<law>{alt})"
        rf"[ 　]*第\s*(?P<art>{NUM}+)\s*(?:條之(?P<sub>{NUM}+)|條)"
        rf"(?:\s*第\s*(?P<para>{NUM}+)\s*項)?"
        rf"(?:\s*第\s*(?P<item>{NUM}+)\s*款)?"
        rf"(?:\s*第?\s*(?P<sub_item>{NUM}+)\s*目)?"
    )


def find_law(name: str):
    """法名可以只給一部分：『憲法』要對到『中華民國憲法』，不是『憲法訴訟法』。

    中文法名的修飾語在前面，所以「結尾相符」優先於「含有」——否則『憲法』會配到
    『憲法訴訟法』，而它比『中華民國憲法』短，取最短就取錯。
    """
    name = ALIAS.get(name, name)
    files = corpus()
    for pick in (lambda p: p.stem == name,
                 lambda p: p.stem.endswith(name),
                 lambda p: name in p.stem,
                 lambda p: p.stem in name):
        hits = [p for p in files if pick(p)]
        if hits:
            return min(hits, key=lambda p: len(p.stem))
    return None


def article(path: Path, art: int, sub=None):
    """回傳該條的行；條號用 `第 N 條` / `第 N-M 條` 這種標頭定位。

    帶「之M」時只找 `第 N-M 條`。原本寫成 `(?:-{sub})?`，那個問號讓「所得稅法第4條之1」
    配到「第 4 條」，於是九十幾個條之N的引用全部拿本條的條文來對，看起來都對得上，
    實際上一個都沒有驗到。
    """
    want = rf"^\s*第\s*{art}-{sub}\s*條\s*$" if sub else rf"^\s*第\s*{art}\s*條\s*$"
    head = re.compile(want)
    nxt = re.compile(r"^\s*第\s*[0-9]+(?:-[0-9]+)?\s*條\s*$")
    lines = path.read_text(encoding="utf8").splitlines()
    for i, ln in enumerate(lines):
        if head.match(ln):
            body = []
            for ln2 in lines[i + 1:]:
                if nxt.match(ln2):
                    break
                body.append(ln2.rstrip())
            while body and not body[-1].strip():
                body.pop()
            return body
    return None


def coverage(path: Path) -> int:
    """該檔收到第幾條。

    查不到條文時一律把這個數字印出來，因為個別法源 PDF 有些只是節錄——行政訴訟法
    那份只收到第 32 條，全法有 308 條。看到「查無第 256 條（該檔收到第 32 條）」，
    就知道要先去補來源，不會誤以為是筆記的條號寫錯而把對的內容改壞。

    這裡不猜「是節錄還是全文」。試過用「最後一條是不是施行條文」判斷，兩個方向都會
    錯：民法結尾是特留分（施行另有民法施行法）會被誤判成節錄，而行政訴訟法那份節錄
    的結尾剛好提到施行、會被誤判成全文。與其給一個會錯的判斷，不如給準確的事實。
    """
    nums = re.findall(r"^\s*第\s*(\d+)(?:-\d+)?\s*條\s*$",
                      path.read_text(encoding="utf8"), re.M)
    return max(map(int, nums)) if nums else 0


def paragraph(body, para: int):
    """項在 pdftotext -layout 底下是行首那個數字。單項條文沒有編號。"""
    out, on = [], False
    for ln in body:
        m = re.match(r"^\s*(\d+)\s{2,}(.*)$", ln)
        if m:
            on = int(m.group(1)) == para
            if on:
                out.append(m.group(2).rstrip())
            continue
        if on:
            out.append(ln.strip())
    return out


def item(body, n: int, marker="款"):
    """款是行首的『一、二、三』，目是『（一）（二）』；取到下一個同級標記為止。"""
    if marker == "款":
        head = re.compile(rf"^\s*({NUM}+)、")
        same = re.compile(rf"^\s*{NUM}+、")
    else:
        head = re.compile(rf"^\s*[（(]\s*({NUM}+)\s*[)）]")
        same = re.compile(rf"^\s*[（(]\s*{NUM}+\s*[)）]")
    out, on = [], False
    for ln in body:
        m = head.match(ln)
        if m:
            if on:
                break
            on = cn2int(m.group(1)) == n
            if on:
                out.append(ln.strip())
            continue
        if on:
            if same.match(ln):
                break
            out.append(ln.strip())
    return out


def flatten(body, limit=48):
    s = "".join(re.sub(r"^\s*\d+\s{2,}", "", ln).strip() for ln in body)
    return s[:limit] + ("…" if len(s) > limit else "")


def cites(text: str):
    """回傳去重後的引用：(法名, 條, 條之N, 項, 款, 目, 原文)。"""
    seen, rows = set(), []
    for m in cite_re().finditer(text):
        if any(text[:m.start()].endswith(f) for f in FOREIGN):
            continue
        g = m.groupdict()
        key = (g["law"],) + tuple(
            cn2int(g[k]) if g[k] else None
            for k in ("art", "sub", "para", "item", "sub_item"))
        if key in seen:
            continue
        seen.add(key)
        rows.append(key + (m.group(0).strip(),))
    return rows


def resolve(law, art, sub, para, item_no, sub_item):
    """(條文行, 錯在哪) — 對得上時第二個是 None。"""
    path = find_law(law)
    if path is None:
        return None, "沒有這部法的文字檔（跑 --list 看有哪些）"
    body = article(path, art, sub)
    if body is None:
        # 個別法源 PDF 有些只是節錄（行政訴訟法那份只收到第 32 條，全法有 308 條）。
        # 查不到卻報「條號錯」，會害人把對的內容改壞——來源不全要跟內容有錯分開講。
        return None, f"{path.stem} 裡查無此條（該檔收到第 {coverage(path)} 條）"
    shown = body
    if para:
        shown = paragraph(body, para)
        if not shown:
            return None, f"該條沒有第 {para} 項（可能是單項條文）"
    if item_no:
        shown = item(shown, item_no, "款") or shown
    if sub_item:
        shown = item(shown, sub_item, "目") or shown
    return shown, None


def do_scan(target: Path):
    # 校訂註解要照抄改掉前的錯寫法（記原話），掃它等於每次都命中已經修好的東西。
    rows = cites(COMMENT_RE.sub("", target.read_text(encoding="utf8")))
    print(f"{target.name} 引到 {len(rows)} 個相異法條\n")
    bad = 0
    for law, art, sub, para, item_no, sub_item, raw in rows:
        shown, err = resolve(law, art, sub, para, item_no, sub_item)
        if err:
            print(f"  ✗ {raw:<28} {err}")
            bad += 1
        else:
            print(f"  · {raw:<28} {flatten(shown)}")
    print(f"\n對得上 {len(rows) - bad}，要回去查 {bad}")
    return 1 if bad else 0


def do_scan_all():
    """掃全站正文，把對不上的引用集中列出來。

    對得上的不印——183 頁上千個引用，全印出來沒有人會讀。這裡要的是例外清單。
    """
    docs = ROOT / "mkdocs/My_Notes"
    skip = ("逐字稿初稿", "不用的廢稿", "_原稿")
    pages = [p for p in sorted(docs.rglob("*.md"))
             if not any(s in str(p) for s in skip) and p.name != "index.md"]

    total, bad_rows, laws = 0, [], {}
    for p in pages:
        text = COMMENT_RE.sub("", p.read_text(encoding="utf8"))
        for law, art, sub, para, item_no, sub_item, raw in cites(text):
            total += 1
            laws[law] = laws.get(law, 0) + 1
            shown, err = resolve(law, art, sub, para, item_no, sub_item)
            if err:
                bad_rows.append((str(p.relative_to(docs)), raw, err))

    print(f"掃 {len(pages)} 頁，共 {total} 個相異法條引用，對不上 {len(bad_rows)} 個\n")
    print("引用最多的法源：")
    for k, v in sorted(laws.items(), key=lambda kv: -kv[1])[:12]:
        print(f"　{v:>4}　{k}")

    if not bad_rows:
        print("\n沒有對不上的引用。")
        return 0

    print(f"\n── 對不上的 {len(bad_rows)} 個 ──")
    by_err = {}
    for page, raw, err in bad_rows:
        by_err.setdefault(err.split("（")[0], []).append((page, raw))
    for err, rows in sorted(by_err.items(), key=lambda kv: -len(kv[1])):
        print(f"\n{err}（{len(rows)}）")
        for page, raw in rows[:25]:
            print(f"　{raw:<26} {page}")
        if len(rows) > 25:
            print(f"　…另 {len(rows) - 25} 個")
    return 1


def do_names():
    """掃成稿與工程文件，找 MISNOMER 裡登記過的錯法名。

    只掃成稿（`老師要按主題分章節/`）、週次筆記與 `docs/`。逐字稿初稿與 1121 的舊稿
    是原始材料，本倉的慣例是不動它們、只在成稿留校訂註解，所以掃了只會一直紅。
    """
    targets = [ROOT / "mkdocs/My_Notes/1141/課_二89_租稅法總論", ROOT / "docs"]
    # 法源核對.md 是記錄本表的地方，它必須寫出錯的那個寫法（已校訂表、負向測試說明），
    # 掃它等於永遠 4 命中。整份跳過，代價是那一份檔的法名沒有機器把關。
    skip_files = {"法源核對.md"}
    pages = [p for t in targets for p in sorted(t.rglob("*.md"))
             if "逐字稿初稿" not in str(p) and "不用的廢稿" not in str(p)
             and p.name not in skip_files]

    hits = []
    for p in pages:
        text = COMMENT_RE.sub("", p.read_text(encoding="utf8"))
        for i, line in enumerate(text.splitlines(), start=1):
            for wrong, (right, src) in MISNOMER.items():
                if wrong in line:
                    hits.append((p.relative_to(ROOT), i, wrong, right, src))

    print(f"掃 {len(pages)} 頁（跳過逐字稿初稿與校訂註解），登記在案的錯法名 {len(MISNOMER)} 種")
    if not hits:
        print("沒有命中。")
        return 0
    print(f"\n── 命中 {len(hits)} 處 ──")
    for path, line, wrong, right, src in hits:
        print(f"  {path}:{line}\n    「{wrong}」應為「{right}」（依據：{src}）")
    return 1


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("law", nargs="?", help="法名，可以只給一部分")
    ap.add_argument("art", nargs="?", help="條號，阿拉伯或國字都行")
    ap.add_argument("--項", dest="para", help="只印某一項")
    ap.add_argument("--scan", help="掃一份 .md，列出裡面所有法條引用")
    ap.add_argument("--list", action="store_true", help="列出可查的法源")
    ap.add_argument("--scan-all", action="store_true", dest="scan_all",
                    help="掃全站正文，只列對不上的引用")
    ap.add_argument("--names", action="store_true",
                    help="掃成稿與 docs，找登記在案的錯法名（MISNOMER）")
    args = ap.parse_args()

    if args.names:
        sys.exit(do_names())
    if args.list:
        for p in corpus():
            print(f"  {p.parent.name:<8} {p.stem}")
        return
    if args.scan_all:
        sys.exit(do_scan_all())
    if args.scan:
        t = Path(args.scan)
        for cand in (t, ROOT / "mkdocs/My_Notes" / args.scan, ROOT / args.scan):
            if cand.is_file():
                sys.exit(do_scan(cand))
        sys.exit(f"找不到 {args.scan}")
    if not (args.law and args.art):
        ap.error("要麼給 法名＋條號，要麼給 --scan 或 --list")

    path = find_law(args.law)
    if path is None:
        sys.exit(f"沒有「{args.law}」的文字檔，跑 --list 看有哪些")
    m = re.match(rf"({NUM}+)(?:-({NUM}+))?$", args.art)
    art = cn2int(m.group(1))
    sub = cn2int(m.group(2)) if m and m.group(2) else None
    out, err = resolve(args.law, art, sub,
                       cn2int(args.para) if args.para else None, None, None)
    if err:
        sys.exit(err)
    print(f"── {path.stem}　第 {args.art} 條 ──")
    for ln in out:
        print(ln)


if __name__ == "__main__":
    main()
