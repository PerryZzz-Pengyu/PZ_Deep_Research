from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


def normalize_string_list(arguments: dict[str, Any], *keys: str) -> list[str]:
    values: list[Any] = []
    for key in keys:
        raw = arguments.get(key)
        if raw is None:
            continue
        if isinstance(raw, str):
            values.append(raw)
        elif isinstance(raw, list):
            values.extend(raw)

    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        item = " ".join(value.strip().split())
        if not item or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized


def is_supported_web_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def add_unique_source(
    sources: list[dict[str, str]],
    seen_urls: set[str],
    *,
    title: str,
    url: str,
    snippet: str = "",
    query: str = "",
    **metadata: str,
) -> None:
    if not url or url in seen_urls:
        return
    seen_urls.add(url)
    source = {"title": title or url, "url": url}
    if snippet:
        source["snippet"] = snippet
    if query:
        source["query"] = query
    for key, value in metadata.items():
        if value:
            source[key] = value
    sources.append(source)
