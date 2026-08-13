#!/usr/bin/env python3
"""whisper.cpp 批次轉寫＋後製，含斷點續跑。

流程：m4a → 16k mono wav → whisper-cli（VAD＋large-v3-turbo）→ 套用
1140_NTU_Tax_Ko 那份 domain_defaults.json 的錯字表 → 存成逐字稿（.txt）。

斷點續跑的判準是**內容量**，不是檔案存不存在。中途被中斷（usage limit、
砍進程、關機）會留下半個 wav 或空的 srt，而那些檔案存在、看起來也正常，
只用 exists() 判斷會把它們當成已完成，於是產出一份被截短的逐字稿，從
檔案大小完全看不出來。所有中間產物因此都先寫成 .part 再改名，改名是
原子操作，中斷只會留下 .part，下一輪自動重做。

完成判準：逐字稿的字元數 ≥ 音檔秒數 × MIN_CHARS_PER_SEC。實測 36 份
（2026-08-09）的密度落在 3.44–5.82 字/秒，門檻取 1.5 離最低值有 2.3 倍
距離，同時抓得到低於約 44% 完整度的截短稿。時長不足 SHORT_CLIP_SEC 的
音檔豁免此項——來源本身就有 0 秒與 1 秒的空錄音，空輸出是正確結果，
不豁免就會無限重轉。

用法：
    batch_transcribe.py <work_dir> <prompt> <audio1> [audio2 ...]
    batch_transcribe.py --list <work_dir> <prompt> <audio1> [audio2 ...]

--list 只列出每份的狀態與待辦數量，不轉任何東西。查進度用它，不要重跑
整個批次——那會啟動一次數十小時的工作。
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

try:
    import opencc
    _S2T = opencc.OpenCC("s2twp")
except ImportError:
    _S2T = None
    print(
        "警告：opencc 未安裝，輸出會留有簡體殘留。"
        "先 source whisper-realtime 的 .venv311 再跑這支腳本。",
        file=sys.stderr,
    )

WHISPER_CLI = Path.home() / "Documents/whisper.cpp/build/bin/whisper-cli"
MODEL = Path.home() / "Documents/whisper.cpp/models/ggml-large-v3-turbo-q5_0.bin"
VAD_MODEL = Path.home() / "Documents/whisper.cpp/models/ggml-silero-v5.1.2.bin"
DOMAIN_DEFAULTS = Path.home() / "Documents/NTU/1141/whisper/whisper-rt-full/whisper-realtime/config/domain_defaults.json"

# 完成判準的兩個常數，來歷見模組 docstring。
MIN_CHARS_PER_SEC = 1.5
SHORT_CLIP_SEC = 5.0

# 確認過沒有語音的音檔，空輸出是正確結果。不放寬 MIN_CHARS_PER_SEC 來容納它們——
# 那會讓真正的截短稿一起蒙混過關。每一筆都要寫出憑據。
# 2026-08-09 逐一驗過，憑據是 Silero VAD 自己的判定，不是模型的轉寫輸出——
# `build/bin/whisper-vad-speech-segments -vm models/ggml-silero-v5.1.2.bin -f X.wav`
# 三支都回報 0 段語音。**不要拿轉寫結果當「有沒有語音」的證據**：模型對非語音會輸出
# 重複的填充短語（這三支分別轉出「我可以做的」「谢谢」），那只說明模型壞掉，
# 說明不了音檔裡有什麼。0 秒與 1 秒那兩支本來就落在 SHORT_CLIP_SEC 的豁免內，
# 列在這裡是為了留下判斷紀錄。
KNOWN_NO_SPEECH = {
    "230911_1322",      # 0 秒，空檔
    "230918_1422_11",   # 1 秒，空檔
    "240212_0836",      # 14 秒，mean -44.0 dB，無語音
}

SRT_BLOCK_RE = re.compile(
    r"\d+\n\d\d:\d\d:\d\d,\d+ --> \d\d:\d\d:\d\d,\d+\n(.+?)\n\n", re.S
)


def log(work_dir: Path, message: str):
    """逐份追加一行到 batch.log，並同時印到 stdout。

    先前這個檔只在開跑時寫一行總數，跑到一半看它判斷不了進度。
    """
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"{stamp}  {message}"
    print(line, flush=True)
    with (work_dir / "batch.log").open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def audio_duration(path: Path) -> float:
    """音檔秒數；ffprobe 失敗回 0.0（該檔會被當成短片段豁免密度檢查）。"""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return float(out)
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
        return 0.0


def transcript_status(txt_path: Path, duration: float):
    """回傳 (是否已完成, 說明)。判準是內容量，不是檔案存不存在。"""
    if not txt_path.exists():
        return False, "尚未轉寫"
    chars = len(txt_path.read_text(encoding="utf-8", errors="replace"))
    stem = txt_path.name[: -len(".raw.txt")] if txt_path.name.endswith(".raw.txt") else txt_path.stem
    if stem in KNOWN_NO_SPEECH:
        return True, f"確認無語音（{duration:.0f}s），{chars} 字"
    if duration < SHORT_CLIP_SEC:
        return True, f"短片段（{duration:.0f}s），{chars} 字"
    need = duration * MIN_CHARS_PER_SEC
    if chars < need:
        return False, (
            f"疑似截短：{chars} 字，{duration:.0f}s 的音檔至少該有 {need:.0f} 字"
        )
    return True, f"{chars} 字，{chars / duration:.2f} 字/秒"


def load_corrections():
    cfg = json.loads(DOMAIN_DEFAULTS.read_text(encoding="utf-8"))
    plain = []
    for correct, wrongs in cfg.get("correction_map", {}).items():
        for w in wrongs:
            plain.append((w, correct))
    plain.sort(key=lambda p: -len(p[0]))
    regex_rules = []
    for correct, patterns in cfg.get("regex_correction_map", {}).items():
        for p in patterns:
            regex_rules.append((re.compile(p), correct))
    return plain, regex_rules


def apply_corrections(text, plain, regex_rules):
    for wrong, correct in plain:
        if wrong in text:
            text = text.replace(wrong, correct)
    for pattern, correct in regex_rules:
        text = pattern.sub(correct, text)
    return text


def to_wav(src_path: Path, wav_path: Path):
    """轉成 16k 單聲道 wav。先寫 .part 再改名，中斷不留半個可用的 wav。"""
    if wav_path.exists():
        return
    part = Path(str(wav_path) + ".part")
    part.unlink(missing_ok=True)
    # -f wav 不能省：輸出檔名是 .wav.part，ffmpeg 從副檔名推不出格式，
    # 會以 exit 234 收場。
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src_path), "-ar", "16000", "-ac", "1",
         "-c:a", "pcm_s16le", "-f", "wav", str(part)],
        check=True, capture_output=True,
    )
    part.rename(wav_path)


def transcribe(wav_path: Path, out_prefix: Path, prompt: str) -> Path:
    """跑 whisper-cli 產出 srt。同樣先寫 .part 前綴再改名。"""
    # 一律用字串串接組路徑。Path.with_suffix() 對「已經有副檔名」的名字是
    # 替換而不是附加，out_prefix 若含小數點（或加上 .part 之後）算出來的
    # 會是另一個檔，而它不會報錯，只會在 rename 時才炸。
    srt_path = Path(str(out_prefix) + ".srt")
    if srt_path.exists() and srt_path.stat().st_size > 0:
        return srt_path
    part_prefix = Path(str(out_prefix) + ".part")
    part_srt = Path(str(part_prefix) + ".srt")
    part_srt.unlink(missing_ok=True)
    cmd = [
        str(WHISPER_CLI),
        "-m", str(MODEL),
        "--vad", "--vad-model", str(VAD_MODEL),
        "-l", "zh", "-bs", "1", "-fa", "-t", "6",
        "--prompt", prompt,
        "-osrt",
        "-of", str(part_prefix),
        "-f", str(wav_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    part_srt.rename(srt_path)
    return srt_path


def srt_to_raw_transcript(srt_path: Path, plain, regex_rules) -> str:
    raw = srt_path.read_text(encoding="utf-8", errors="replace")
    blocks = SRT_BLOCK_RE.findall(raw)
    lines = []
    for block in blocks:
        line = " ".join(block.split("\n")).strip()
        if not line:
            continue
        line = apply_corrections(line, plain, regex_rules)
        if not line.endswith(("。", "？", "！")):
            line += "。"
        lines.append(line)
    return " ".join(lines)


def process(src_path: Path, work_dir: Path, prompt: str) -> Path:
    stem = src_path.stem
    wav_path = work_dir / f"{stem}.wav"
    out_prefix = work_dir / stem
    txt_path = work_dir / f"{stem}.raw.txt"

    duration = audio_duration(src_path)
    done, why = transcript_status(txt_path, duration)
    if done:
        log(work_dir, f"skip  {stem}：{why}")
        return txt_path
    if txt_path.exists():
        # 前一輪留下的截短稿；連同它的 srt 一起丟掉重做。
        log(work_dir, f"redo  {stem}：{why}")
        txt_path.unlink()
        Path(str(out_prefix) + ".srt").unlink(missing_ok=True)

    started = time.time()
    to_wav(src_path, wav_path)
    srt_path = transcribe(wav_path, out_prefix, prompt)
    plain, regex_rules = load_corrections()
    text = srt_to_raw_transcript(srt_path, plain, regex_rules)
    if _S2T is not None:
        text = _S2T.convert(text)
    part_txt = Path(str(txt_path) + ".part")
    part_txt.write_text(text, encoding="utf-8")
    part_txt.rename(txt_path)
    # 逐字稿寫成之後就刪掉中間的 wav，只留 .srt 與 .raw.txt。
    # 16k 單聲道每小時約 115 MB，85 小時的課會塞爆本機剩下的空間。
    wav_path.unlink(missing_ok=True)

    elapsed = time.time() - started
    rate = duration / elapsed if elapsed else 0
    log(work_dir, (
        f"done  {stem}：{len(text)} 字，音檔 {duration:.0f}s，"
        f"耗時 {elapsed:.0f}s（{rate:.1f}x 實時）"
    ))
    return txt_path


def list_status(work_dir: Path, sources) -> int:
    """只列狀態不轉寫，回傳待辦份數。"""
    pending_sec = 0.0
    pending = 0
    for src in sources:
        src = Path(src)
        duration = audio_duration(src)
        txt_path = work_dir / f"{src.stem}.raw.txt"
        done, why = transcript_status(txt_path, duration)
        mark = "✓" if done else "·"
        print(f"{mark} {src.stem:<22} {why}")
        if not done:
            pending += 1
            pending_sec += duration
    print(
        f"\n共 {len(sources)} 份，待辦 {pending} 份"
        f"（音檔 {pending_sec / 3600:.1f} 小時）"
    )
    return pending


if __name__ == "__main__":
    argv = sys.argv[1:]
    list_only = False
    if "--list" in argv:
        list_only = True
        argv.remove("--list")
    if len(argv) < 3:
        print("用法：batch_transcribe.py [--list] <work_dir> <prompt> <audio1> [audio2 ...]")
        sys.exit(1)

    work_dir = Path(argv[0])
    prompt = argv[1]
    sources = argv[2:]

    if list_only:
        list_status(work_dir, sources)
        sys.exit(0)

    log(work_dir, f"批次開始：音檔 {len(sources)} 份")
    for src in sources:
        process(Path(src), work_dir, prompt)
    log(work_dir, "批次結束")
