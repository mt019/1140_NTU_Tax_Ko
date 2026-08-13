#!/bin/bash
# 1121 舊稿重轉的批次啟動器。斷點續跑由 batch_transcribe.py 內建，判準是逐字稿的內容量
# 而不是檔案存不存在，所以這支重跑幾次都安全，中斷留下的半成品也會自動重做。
#
# 用法：
#   bash scripts/run-1121-batch.sh            # 背景啟動整批
#   bash scripts/run-1121-batch.sh --list     # 只列每份的狀態與待辦，不轉任何東西
#
# 兩件跑之前要知道的事：
#
# 1. 這支會自己用 nohup 脫離終端機。整批要十幾小時，而 Claude Code 的 session 結束時會把
#    它啟動的進程一起帶走——2026-08-09 第一次跑就是這樣停在第 9 檔。
# 2. **請從 Terminal.app 起，不要從 Claude Code 起。** 背景執行的環境會把 nice 值帶到 5，
#    whisper 於是搶不贏其他背景程序；2026-08-09 實測那樣只有 4.9 倍實時，正常起動是
#    11 倍上下。nice 值只有 root 調得回來，所以要在起動的時候就對。

set -euo pipefail

REPO="$HOME/Documents/NTU/1141/1140_NTU_Tax_Ko"
AUDIO="$HOME/Documents/NTU/柯老師2023秋學期錄音原檔/錄音"
WORK="$REPO/_work/1121_轉寫"
VENV="$HOME/Documents/NTU/1141/whisper/whisper-rt-full/whisper-realtime/.venv311/bin/activate"

PROMPT="租稅法總論、租稅規避、稅捐規避、實質課稅原則、量能課稅原則、租稅法律主義、稅捐主體、稅捐客體、納稅義務人、扣繳義務人、稅捐稽徵法、所得稅法、遺產及贈與稅法、恣意禁止、稅捐中立性、經濟觀察法、脫法行為、稅捐規避否認"

mkdir -p "$WORK"

# shellcheck disable=SC1090
source "$VENV"

cd "$REPO"

# 音檔 125 個：FOLDER01 的 mp3 加 weekend 的 m4a。
# 不用 mapfile，macOS 內建的是 bash 3.2。
FILES=()
while IFS= read -r f; do
  FILES+=("$f")
done < <(ls "$AUDIO"/FOLDER01/*.mp3 "$AUDIO"/weekend/*.m4a 2>/dev/null | sort)

# --list 直接在前景跑完就走，它只讀不寫，秒級結束。
if [ "${1:-}" = "--list" ]; then
  exec python3 scripts/batch_transcribe.py --list "$WORK" "$PROMPT" "${FILES[@]}"
fi

# 自己脫離終端機。macOS 沒有 setsid，用 nohup 加 disown。
# BATCH_DETACHED 是遞迴的煞車：重進來的那一次才真的開始轉。
if [ "${BATCH_DETACHED:-}" != "1" ]; then
  # 進度由 batch_transcribe.py 的 log() 自己寫進 batch.log，這裡只收它印到
  # stdout／stderr 的東西（Python 例外之類），分開一個檔。兩邊都導到 batch.log
  # 會讓每一行寫兩次。
  BATCH_DETACHED=1 nohup bash "$0" >> "$WORK/batch.stderr.log" 2>&1 &
  pid=$!
  disown "$pid" 2>/dev/null || true
  # 變數一律寫成 ${pid}。macOS 內建的是 bash 3.2，$pid 後面緊接著全形括號時，
  # 它會把那個多位元組字元的位元組也當成變數名，於是報 unbound variable。
  echo "已在背景啟動，PID ${pid}"
  echo "看進度：bash scripts/run-1121-batch.sh --list"
  echo "看日誌：tail -f ${WORK}/batch.log"
  echo "要停下：kill ${pid}（再用 --list 確認狀態，中斷的那一份下次會自動重做）"
  exit 0
fi

exec python3 scripts/batch_transcribe.py "$WORK" "$PROMPT" "${FILES[@]}"
