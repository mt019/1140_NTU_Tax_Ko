"""上線清單：只建 mkdocs/上線清單.txt 列出的頁，清單外的 .md 一律不建。

2026-11-09 起設。起因：2026-10-26 一個 session 把未經站主審定的 1151 W07 頁
自行移出 proofread_gate，10-29 另一個 session 推送時一併上線。proofread_gate
是「清單內的頁擋下」，漏列或被刪一行就上線；本外掛反過來，「清單外的頁不建」，
新頁要上線必須在清單加一行，而那一行只由站主本人加。

清單讀不到或是空的，建置直接失敗，不退回「全部照建」。
"""
from pathlib import Path

from mkdocs.config import config_options
from mkdocs.exceptions import PluginError
from mkdocs.plugins import BasePlugin, get_plugin_logger

log = get_plugin_logger(__name__)


def load_publish_list(config, name="上線清單.txt"):
    path = Path(config["config_file_path"]).parent / name
    if not path.is_file():
        raise PluginError(f"publish_lock：找不到上線清單 {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    allowed = {l.strip() for l in lines if l.strip() and not l.lstrip().startswith("#")}
    if len(allowed) < 50:
        raise PluginError(f"publish_lock：上線清單只有 {len(allowed)} 行，疑似讀錯檔")
    return allowed


class PublishLockPlugin(BasePlugin):
    config_scheme = (("list", config_options.Type(str, default="上線清單.txt")),)

    def on_config(self, config):
        self.allowed = load_publish_list(config, self.config["list"])
        return config

    def on_files(self, files, config):
        dropped = []
        for f in list(files):
            if not f.src_uri.endswith(".md"):
                continue
            if f.src_uri not in self.allowed:
                files.remove(f)
                dropped.append(f.src_uri)
        if dropped:
            log.info("publish_lock：清單外 %d 頁不建，例：%s", len(dropped), "、".join(sorted(dropped)[:5]))
        built = {f.src_uri for f in files if f.src_uri.endswith(".md")}
        log.info("publish_lock：建 %d 頁（清單 %d 行）", len(built), len(self.allowed))
        return files
