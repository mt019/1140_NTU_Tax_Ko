# readme

> **2026-08-02：這台 Mac 上的 Docker Desktop 已經移除**（硬碟清理，當時它佔 4.2G，
> 而唯一的 image 就是這裡的 `1140_ntu_tax_ko-docs`）。下面的指令現在會找不到 `docker`。
> 要用就先重裝 Docker Desktop，再 `docker compose build docs` 重建一次——
> `docker-compose.yml` 的掛載全是指向本機目錄的綁定掛載，沒有 Docker 管理的 volume，
> 所以文件內容一份都沒少，重建就回來了。

- Run:
  - `bash scripts/jupyter_url.sh`
  - docker compose restart docs


docker compose build docs
docker compose up -d docs

## 工程文件

- `docs/主題重編/` — 按主題重編章節這件事：方法、校對狀態盤點、分章計畫
- `scripts/` — 唯讀盤點腳本（抽標題、照抄率、口語殘留、缺陷掃描），輸出進 `_work/`
