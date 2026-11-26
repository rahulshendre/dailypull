"""Classics: old posts that Hacker News readers keep posting again, years later.

On Hacker News, a repost of an old article gets its year in the title, like
"Choose Boring Technology (2015)". If people still upvote it years later, it held up.
We collect those for every year and show one per topic, each only once.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import re

import httpx

from . import config, rank, sources

ALGOLIA = "https://hn.algolia.com/api/v1/search"
YEAR_TAG = re.compile(r"\s*\((19[5-9]\d|20\d\d)\)\s*$")
NOT_ARTICLES = ("Show HN", "Ask HN", "Tell HN", "Launch HN")
# News ages badly: a classic should still be worth reading for its own sake.
NEWSY = re.compile(r"\b(announc|launch|releas|acquir|died|dies\b|dead at|raises \$|lawsuit|sues\b|hacker news)",
                   re.I)


def parse_hits(hits: list[dict], this_year: int) -> list[dict]:
    """Keep year-tagged, well-voted reposts of articles at least CLASSIC_MIN_AGE_YEARS old."""
    best: dict[str, dict] = {}
    for h in hits:
        title, url = h.get("title") or "", h.get("url") or ""
        tag = YEAR_TAG.search(title)
        if not tag or not url.startswith("http") or title.startswith(NOT_ARTICLES) or NEWSY.search(title):
            continue
        year, points = int(tag.group(1)), int(h.get("points") or 0)
        if year > this_year - config.CLASSIC_MIN_AGE_YEARS or points < config.CLASSIC_MIN_POINTS:
            continue
        posted = dt.datetime.fromtimestamp(h["created_at_i"], dt.timezone.utc).year if h.get("created_at_i") else None
        item = {
            "title": YEAR_TAG.sub("", title).strip(),
            "url": url,
            "year": year,
            "points": points,
            "posted": posted,
            "reposts": 1,
            "total": points,
            "discussion": f"https://news.ycombinator.com/item?id={h['objectID']}",
            "kind": sources.guess_kind(url),
        }
        key = sources.normalize_url(url)
        if key in best:
            # Posted again and voted up again: the strongest sign that it held up.
            prev = best[key]
            if h["objectID"] in prev["ids"]:
                continue
            item["reposts"] = prev["reposts"] + 1
            item["total"] = prev["total"] + points
            item["ids"] = prev["ids"] | {h["objectID"]}
            if points < prev["points"]:
                item.update({k: prev[k] for k in ("title", "points", "posted", "discussion")})
        else:
            item["ids"] = {h["objectID"]}
        best[key] = item
    for item in best.values():
        item.pop("ids")
    return list(best.values())


async def gather(timeout: float = 40.0, transport: httpx.AsyncBaseTransport | None = None,
                 this_year: int | None = None) -> tuple[list[dict], dict]:
    """Search Hacker News once per year for reposts tagged with that year. Returns (classics, status)."""
    this_year = this_year or dt.datetime.now(dt.timezone.utc).year
    years = range(config.CLASSIC_FIRST_YEAR, this_year - config.CLASSIC_MIN_AGE_YEARS + 1)
    limit = asyncio.Semaphore(6)
    async with httpx.AsyncClient(headers={"User-Agent": sources.USER_AGENT}, timeout=timeout,
                                 transport=transport) as client:
        async def search(year):
            async with limit:
                resp = await client.get(ALGOLIA, params={
                    "query": str(year), "tags": "story", "hitsPerPage": 1000,
                    "numericFilters": f"points>={config.CLASSIC_MIN_POINTS}",
                    "restrictSearchableAttributes": "title",
                })
                resp.raise_for_status()
                return resp.json().get("hits", [])

        results = await asyncio.gather(*(search(y) for y in years), return_exceptions=True)
    hits = [h for r in results if isinstance(r, list) for h in r]
    failed = sum(not isinstance(r, list) for r in results)
    items = parse_hits(hits, this_year)
    status = f"ok {len(items)}" + (f" ({failed} of {len(results)} searches failed)" if failed else "")
    if not hits:
        status = "error no results"
    return items, {"Hacker News classics": status}


def pick(classics: list[dict], seen: dict) -> list[dict]:
    """One classic per topic: the one with the most votes across all its reposts, not shown before.
    A classic is used for one topic only."""
    ranked = sorted(classics, key=lambda c: (-c["total"], -c["points"]))
    topics_of = {id(c): rank.classic_topics(c["title"]) for c in ranked}
    chosen, used = [], set()
    for topic in config.TOPICS:
        for c in ranked:
            key = sources.normalize_url(c["url"])
            if key in seen or key in used or topic not in topics_of[id(c)]:
                continue
            chosen.append({**c, "topics": [topic]})
            used.add(key)
            break
    return chosen
