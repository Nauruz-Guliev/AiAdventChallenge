from __future__ import annotations

import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

KMP_DOCS_REPO = "JetBrains/kotlin-multiplatform-dev-docs"
KMP_DOCS_REF = "master"
RU_DOCS_REPO = "phplego/kotlinlang.ru"
RU_DOCS_REF = "master"

RAW = "https://raw.githubusercontent.com/{repo}/{ref}/{path}"
TREE = "https://api.github.com/repos/{repo}/git/trees/{ref}?recursive=1"

LIB_READMES: list[tuple[str, str]] = [
    ("kotlinx-coroutines", "https://raw.githubusercontent.com/Kotlin/kotlinx.coroutines/master/README.md"),
    ("kotlinx-serialization", "https://raw.githubusercontent.com/Kotlin/kotlinx.serialization/master/README.md"),
    ("kotlinx-datetime", "https://raw.githubusercontent.com/Kotlin/kotlinx-datetime/master/README.md"),
    ("kotlinx-io", "https://raw.githubusercontent.com/Kotlin/kotlinx-io/master/README.md"),
    ("kotlinx-atomicfu", "https://raw.githubusercontent.com/Kotlin/kotlinx-atomicfu/master/README.md"),
    ("ktor", "https://raw.githubusercontent.com/ktorio/ktor/main/README.md"),
    ("compose-multiplatform", "https://raw.githubusercontent.com/JetBrains/compose-multiplatform/master/README.md"),
    ("sqldelight", "https://raw.githubusercontent.com/cashapp/sqldelight/master/README.md"),
    ("kermit", "https://raw.githubusercontent.com/touchlab/Kermit/main/README.md"),
    ("multiplatform-settings", "https://raw.githubusercontent.com/russhwolf/multiplatform-settings/main/README.md"),
    ("moko-mvvm", "https://raw.githubusercontent.com/icerockdev/moko-mvvm/master/README.md"),
    ("moko-resources", "https://raw.githubusercontent.com/icerockdev/moko-resources/master/README.md"),
    ("koin", "https://raw.githubusercontent.com/InsertKoinIO/koin/main/README.md"),
    ("store", "https://raw.githubusercontent.com/dropbox/Store/main/README.md"),
    ("kstate", "https://raw.githubusercontent.com/touchlab/KState/main/README.md"),
]

HTML_PAGES: list[tuple[str, str]] = [
    ("ktor-client-multiplatform", "https://ktor.io/docs/client-create-multiplatform-application.html"),
]

_WRITESIDE_TAGS = (
    "toc-element|procedure|step|note|warning|tip|code-block|tabs|tab|include|seealso|"
    "table|chapter|anchor|control|select|def|minitoc|snippet|video|img|files|file|"
    "panel|collapsible|tldr|footnote|task|question|answer|var|span|b|i|a|p|li|ul|ol"
)
_WRITESIDE = re.compile(rf"</?(?:{_WRITESIDE_TAGS})\b[^>]*>", re.IGNORECASE)
_ATTR = re.compile(r'\{[a-z][a-z0-9-]*="[^"]*"\}')
_MD_COMMENT = re.compile(r"^\[//\]:\s*#.*$", re.MULTILINE)
_MULTI_NL = re.compile(r"\n{3,}")
_TITLE_COMMENT = re.compile(r"\[//\]:\s*#\s*\(title:\s*(.*?)\)", re.MULTILINE)
_TITLE_ATTR = re.compile(r'\{title="([^"]+)"\}')


def extract_title(raw: str, fallback: str) -> str:
    for pattern in (_TITLE_COMMENT, _TITLE_ATTR):
        m = pattern.search(raw)
        if m:
            return m.group(1).strip()
    return first_heading(raw, fallback)


def strip_writeside(text: str) -> str:
    text = _MD_COMMENT.sub("", text)
    text = _WRITESIDE.sub("", text)
    text = _ATTR.sub("", text)
    text = _MULTI_NL.sub("\n\n", text)
    return text.strip()


def http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (day21-indexer)"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", "replace")


def github_tree(repo: str, ref: str) -> list[str]:
    data = json.loads(http_get(TREE.format(repo=repo, ref=ref)))
    return [t["path"] for t in data.get("tree", []) if t.get("type") == "blob"]


def slugify(path: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-")


def first_heading(text: str, fallback: str) -> str:
    m = re.search(r"^#\s+(.*)$", text, re.MULTILINE)
    return m.group(1).strip() if m else fallback


def save(out_dir: Path, name: str, title: str, text: str, counter: list[int]) -> int:
    counter[0] += 1
    safe = f"{counter[0]:03d}-{name}.md"
    (out_dir / safe).write_text(f"# {title}\n\n{text}\n", encoding="utf-8")
    return len(text)


class _Extractor(HTMLParser):
    _BLOCK = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "br", "tr", "pre", "section", "article"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self._skip += 1
        if tag in self._BLOCK:
            self.parts.append("\n")
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.parts.append("#" * int(tag[1]) + " ")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg"):
            self._skip = max(0, self._skip - 1)
        if tag in self._BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._skip == 0:
            self.parts.append(data)

    def text(self) -> str:
        raw = "".join(self.parts)
        raw = re.sub(r"[ \t]+", " ", raw)
        return _MULTI_NL.sub("\n\n", raw).strip()


def fetch_html(url: str) -> str:
    parser = _Extractor()
    parser.feed(http_get(url))
    return parser.text()


def main() -> int:
    base = Path(__file__).parent / "corpus"
    docs_dir = base / "kmp-docs"
    libs_dir = base / "libs"
    ru_dir = base / "ru"
    for d in (docs_dir, libs_dir, ru_dir):
        d.mkdir(parents=True, exist_ok=True)

    counter = [0]
    total_chars = 0
    ok = 0

    print(f"== Официальные доки KMP ({KMP_DOCS_REPO}) ==")
    try:
        paths = [
            p for p in github_tree(KMP_DOCS_REPO, KMP_DOCS_REF)
            if p.startswith("topics/") and p.endswith(".md") and not p.startswith("topics/temp/")
        ]
        for path in paths:
            try:
                raw = http_get(RAW.format(repo=KMP_DOCS_REPO, ref=KMP_DOCS_REF, path=path))
                text = strip_writeside(raw)
                if len(text) < 400:
                    continue
                name = slugify(path[len("topics/"):-3])
                total_chars += save(docs_dir, name, extract_title(raw, name), text, counter)
                ok += 1
            except Exception as exc:  # noqa: BLE001
                print(f"  FAIL {path}: {exc}")
        print(f"  сохранено {ok} файлов")
    except Exception as exc:  # noqa: BLE001
        print(f"  FAIL tree: {exc}")

    print("== README библиотек ==")
    for name, url in LIB_READMES:
        try:
            text = strip_writeside(http_get(url))
            if len(text) < 300:
                print(f"  SKIP {name} ({len(text)})")
                continue
            total_chars += save(libs_dir, slugify(name), first_heading(text, name), text, counter)
            ok += 1
            print(f"  OK {name} ({len(text)})")
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL {name}: {exc}")

    print(f"== Русские доки ({RU_DOCS_REPO}) ==")
    try:
        ru_paths = [
            p for p in github_tree(RU_DOCS_REPO, RU_DOCS_REF)
            if p.endswith(".md") and re.search(r"multiplatform|coroutines-overview", p)
        ]
        for path in ru_paths:
            try:
                text = http_get(RAW.format(repo=RU_DOCS_REPO, ref=RU_DOCS_REF, path=path))
                if len(text) < 400:
                    continue
                name = slugify(path[:-3])
                total_chars += save(ru_dir, f"ru-{name}", first_heading(text, name), text, counter)
                ok += 1
            except Exception as exc:  # noqa: BLE001
                print(f"  FAIL {path}: {exc}")
        print(f"  сохранено {len(ru_paths)} кандидатов")
    except Exception as exc:  # noqa: BLE001
        print(f"  FAIL tree: {exc}")

    print("== HTML-страницы ==")
    for name, url in HTML_PAGES:
        try:
            text = fetch_html(url)
            if len(text) < 300:
                print(f"  SKIP {name} ({len(text)})")
                continue
            total_chars += save(libs_dir, slugify(name), first_heading(text, name), text, counter)
            ok += 1
            print(f"  OK {name} ({len(text)})")
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL {name}: {exc}")

    print(f"\nИтого: {ok} документов, ~{total_chars} символов (~{round(total_chars/1800)} страниц)")
    return 0 if ok >= 20 else 1


if __name__ == "__main__":
    raise SystemExit(main())
