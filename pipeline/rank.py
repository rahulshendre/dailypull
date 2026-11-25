"""Free ranking: topic keywords plus popularity. Used when Claude is not available,
and to trim the candidate list before it is sent to Claude."""

from __future__ import annotations

import math
import re
import time

from . import config

_PATTERNS = {
    topic: re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(k) for k in sorted(words, key=len, reverse=True)) + r")(?![\w-])", re.I)
    for topic, words in config.KEYWORDS.items()
}


def keyword_topics(text: str) -> list[str]:
    hits = []
    for topic, pattern in _PATTERNS.items():
        n = len(pattern.findall(text))
        if n:
            hits.append((n, topic))
    return [t for _, t in sorted(hits, key=lambda x: (-x[0], x[1]))]


def topics_for(c: dict) -> list[str]:
    found = keyword_topics(f"{c['title']} {c['text']}")
    ordered = list(dict.fromkeys(found + c.get("hints", [])))
    return ordered[:3]


def popularity(c: dict) -> float:
    """Roughly 0 to 10. Hand-picked blogs start high because they are already filtered by a human."""
    p = c.get("points", 0)
    src = c["source"]
    if src == "Hacker News":
        score = 2 + 2.2 * math.log10(1 + p)
    elif src == "Lobsters":
        score = 2 + 3.0 * math.log10(1 + p)
    elif src == "DEV":
        score = 1 + 2.0 * math.log10(1 + p)
    elif src == "GitHub Trending":
        score = 1 + 1.6 * math.log10(1 + p)
    elif src == "Mastodon":
        score = 2 + 2.5 * math.log10(1 + p)
    elif src.startswith("r/"):
        score = 1.5 + 1.8 * math.log10(1 + p)
    else:
        score = c.get("prior") if c.get("prior") is not None else 6.0
    if c.get("published"):
        age_days = max(0.0, (time.time() - c["published"]) / 86400)
        score -= 0.5 * age_days
    return round(max(0.0, min(10.0, score)), 2)


def trim(cands: list[dict], limit: int = config.MAX_CANDIDATES) -> list[dict]:
    return sorted(cands, key=popularity, reverse=True)[:limit]


def estimate_minutes(c: dict) -> int:
    if c["kind"] == "repo":
        return 3
    if c["kind"] == "discussion":
        return 8
    return 6


def rank_fallback(cands: list[dict], per_topic: int = 6, max_total: int = 50) -> dict:
    """Pick a balanced set without AI: the most popular items per topic."""
    scored = sorted(cands, key=popularity, reverse=True)
    picks, used, per = [], set(), {t: 0 for t in config.TOPICS}
    for c in scored:
        topics = topics_for(c)
        if not topics or c["cid"] in used or per[topics[0]] >= per_topic:
            continue
        per[topics[0]] += 1
        used.add(c["cid"])
        picks.append({
            "id": c["cid"],
            "title": c["title"],
            "why": "",
            "topics": topics,
            "minutes": estimate_minutes(c),
            "kind": c["kind"],
            "score": max(1, min(10, round(popularity(c)))),
        })
        if len(picks) >= max_total:
            break
    return {"headline": "", "picks": picks}
