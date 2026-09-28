from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request

SEARCH_URL = "https://ru.wikipedia.org/w/api.php"
TIMEOUT_SECONDS = 20
USER_AGENT = "advent-mcp-compose/1.0"
MIN_LIMIT = 1
MAX_LIMIT = 10


class SearchError(Exception):
    """Ошибка обращения к поисковому API."""


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _get_json(url: str, params: dict) -> dict:
    query = urllib.parse.urlencode(params)
    full_url = f"{url}?{query}"
    request = urllib.request.Request(full_url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read()
    except urllib.error.URLError as exc:
        raise SearchError(f"Сеть недоступна: {exc}") from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise SearchError("Некорректный ответ API") from exc


def search(query: str, limit: int = 5) -> dict:
    limit = max(MIN_LIMIT, min(MAX_LIMIT, limit))
    data = _get_json(
        SEARCH_URL,
        {
            "action": "query",
            "list": "search",
            "format": "json",
            "formatversion": "2",
            "srsearch": query,
            "srlimit": str(limit),
            "srprop": "snippet",
        },
    )
    results = []
    for hit in data.get("query", {}).get("search", []):
        title = hit.get("title", "")
        results.append(
            {
                "title": title,
                "url": f"https://ru.wikipedia.org/wiki/{urllib.parse.quote(title)}",
                "snippet": _strip_html(hit.get("snippet", "")),
            }
        )
    if not results:
        raise SearchError(f"Ничего не найдено: {query}")
    return {"query": query, "results": results}
