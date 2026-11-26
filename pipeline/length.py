"""Reading time: fetch each picked article once and count the words in its main text.

A page that can't be fetched, isn't HTML, or has too little text to trust (a login wall, a
page drawn by JavaScript, a paywall) gets no reading time. The page then shows none rather
than a guess. Repos, papers, videos and discussions are never measured: word counts mean
nothing there.
"""
from __future__ import annotations

import asyncio
import re
from html.parser import HTMLParser

import httpx

from . import config, sources

MEASURED_KINDS = {"article"}

_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source",
         "track", "wbr"}
# Never part of the article.
_SKIP_TAGS = {"head", "script", "style", "noscript", "svg", "template", "nav", "header", "footer", "aside", "form",
              "button", "select", "iframe", "figcaption", "dialog"}
# Blocks inside the article that aren't the article: comments, share bars, related posts.
_SKIP_NAMES = re.compile(r"(^|[-_])(comments?|related|share|sharing|social|subscribe|newsletter|sidebar|cookies?"
                         r"|promo|advert|ads|breadcrumbs?|menu|toc)([-_]|$)", re.I)
_NEVER_SKIP = {"html", "body", "main", "article"}
_WORD = re.compile(r"\w+")


class _Words(HTMLParser):
    """Counts words in <article>, in <main> and in the whole body, leaving out page furniture."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool]] = []
        self.skipping = 0
        self.inside = {"article": 0, "main": 0}
        self.seen = {"article": False, "main": False}
        self.words = {"article": 0, "main": 0, "body": 0}

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in _VOID:
            return
        names = " ".join(v or "" for k, v in attrs if k in ("id", "class")).split()
        skip = tag in _SKIP_TAGS or (tag not in _NEVER_SKIP and any(_SKIP_NAMES.search(n) for n in names))
        self.stack.append((tag, skip))
        self.skipping += skip
        if tag in self.inside:
            self.inside[tag] += 1
            self.seen[tag] = True

    def handle_endtag(self, tag: str) -> None:
        # Close everything up to the matching open tag; a stray end tag is ignored.
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                for open_tag, skip in self.stack[i:]:
                    self.skipping -= skip
                    if open_tag in self.inside:
                        self.inside[open_tag] -= 1
                del self.stack[i:]
                return

    def handle_data(self, data: str) -> None:
        if self.skipping:
            return
        n = len(_WORD.findall(data))
        self.words["body"] += n
        for scope, depth in self.inside.items():
            if depth:
                self.words[scope] += n


def count_words(page: str) -> int:
    """Words in the article: <article> if it holds enough text, else <main>. Only a page with
    neither (a plain hand-written blog) is counted as a whole; a page that has them but keeps
    little text in them is a paywall or a teaser, and counting the rest would only add menus."""
    parser = _Words()
    parser.feed(page)
    parser.close()
    for scope in ("article", "main"):
        if parser.words[scope] >= config.MIN_ARTICLE_WORDS:
            return parser.words[scope]
    if parser.seen["article"] or parser.seen["main"]:
        return max(parser.words["article"], parser.words["main"])
    return parser.words["body"]


def reading_minutes(page: str) -> int | None:
    words = count_words(page)
    if words < config.MIN_ARTICLE_WORDS:
        return None
    return max(1, round(words / config.WORDS_PER_MINUTE))


async def _minutes_for(client: httpx.AsyncClient, url: str) -> int | None:
    async with client.stream("GET", url) as r:
        if r.status_code != 200 or "html" not in r.headers.get("content-type", ""):
            return None
        body = bytearray()
        async for chunk in r.aiter_bytes():
            body += chunk
            if len(body) >= config.LENGTH_MAX_BYTES:
                break
        page = body.decode(r.encoding or "utf-8", errors="replace")
    return reading_minutes(page)


async def measure(items: list[dict], transport: httpx.AsyncBaseTransport | None = None) -> dict[str, int]:
    """{url: minutes} for the items that are articles and could be measured."""
    urls = sorted({i["url"] for i in items if i.get("kind", "article") in MEASURED_KINDS})
    gate = asyncio.Semaphore(config.LENGTH_CONCURRENCY)

    async def one(client: httpx.AsyncClient, url: str) -> int | None:
        async with gate:
            try:
                return await asyncio.wait_for(_minutes_for(client, url), config.LENGTH_TIMEOUT)
            except (httpx.HTTPError, asyncio.TimeoutError, UnicodeError, LookupError):
                return None

    async with httpx.AsyncClient(headers={"User-Agent": sources.USER_AGENT}, follow_redirects=True,
                                 timeout=config.LENGTH_TIMEOUT, transport=transport) as client:
        found = await asyncio.gather(*(one(client, u) for u in urls))
    return {u: m for u, m in zip(urls, found) if m}
