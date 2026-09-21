import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://en.wikipedia.org/w/api.php"
UA = "jagged-eval/0.1 (jaggedness study; https://github.com/zkousama/jagged)"
PREFIX = "Wikipedia:Articles for deletion/"


class HttpTransport:
    def get(self, params: dict) -> dict:
        url = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)


class WikiClient:
    def __init__(self, cache_dir: Path, transport=None):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.transport = transport or HttpTransport()

    def log_titles(self, date: str) -> list[str]:
        data = self.transport.get({
            "action": "parse",
            "page": f"{PREFIX}Log/{date}",
            "prop": "links",
        })
        links = data.get("parse", {}).get("links", [])
        return [l["*"] for l in links if l["*"].startswith(PREFIX)]

    def wikitext(self, title: str) -> str:
        key = hashlib.sha256(title.encode()).hexdigest()[:24]
        path = self.cache_dir / f"{key}.txt"
        if path.exists():
            return path.read_text(encoding="utf-8")
        data = self.transport.get({
            "action": "query",
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
            "titles": title,
        })
        pages = data.get("query", {}).get("pages", {})
        page = next(iter(pages.values()), {})
        revs = page.get("revisions")
        text = revs[0]["slots"]["main"]["*"] if revs else ""
        path.write_text(text, encoding="utf-8")
        return text
