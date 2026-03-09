import json
import re
from pathlib import Path

from markdown import Markdown
from mkdocs.plugins import BasePlugin


H2_RE = re.compile(r"<h2\b[^>]*\bid=[\"']([^\"']+)[\"'][^>]*>(.*?)</h2>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")


class HeadingIndexPlugin(BasePlugin):
    def on_files(self, files, config):
        docs_dir = Path(config["docs_dir"])
        md = Markdown(
            extensions=config.get("markdown_extensions", []),
            extension_configs=config.get("mdx_configs", {}),
        )
        heading_index = {}

        for file in files.documentation_pages():
            src_path = Path(file.abs_src_path)
            if src_path.suffix.lower() != ".md":
                continue

            raw = src_path.read_text(encoding="utf-8")
            html = md.convert(self._strip_front_matter(raw))
            md.reset()

            headings = []
            for heading_id, inner_html in H2_RE.findall(html):
                text = TAG_RE.sub("", inner_html).strip()
                if text:
                    headings.append({"id": heading_id, "text": text})

            if headings:
                for key in self._url_keys(file.url):
                    heading_index[key] = headings

        output_path = docs_dir / "assets" / "all-headings.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(heading_index, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        print(f">>> heading_index plugin wrote {output_path} ({len(heading_index)} pages)")
        return files

    @staticmethod
    def _strip_front_matter(text):
        if not text.startswith("---"):
            return text
        lines = text.splitlines()
        if not lines:
            return text
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1 :])
        return text

    @staticmethod
    def _url_keys(url):
        normalized = "/" + str(url or "").lstrip("/")
        if normalized == "/":
            return ["/", "/index.html"]
        if normalized.endswith("/"):
            return [normalized, normalized + "index.html"]
        return [normalized]
