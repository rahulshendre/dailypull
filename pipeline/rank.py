"""Rank candidates without AI.

A link's score comes from people, not a model:
- votes, compared within each site (top of Lobsters ties with top of Hacker News),
- agreement: every extra independent place that has the same link (another site, a newsletter
  editor, an expert's blog) adds a bonus,
- a few plain rules against noise: politics, hiring threads and non-English posts are dropped,
  clickbait titles and flame wars are pushed down, old blog posts slowly sink.
"""

from __future__ import annotations

import bisect
import re
import time
from collections import defaultdict
from urllib.parse import urlparse

from . import config


def _words(words) -> re.Pattern:
    alts = "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))
    return re.compile(r"(?<![\w-])(?:" + alts + r")(?![\w-])", re.I)


_TOPIC_PATTERNS = {topic: _words(words) for topic, words in config.KEYWORDS.items()}
_CRAFT = _words(config.CLASSIC_CRAFT_WORDS)
_POLITICS = _words(config.POLITICS)
_NOISE = re.compile("|".join(config.NOISE_TITLES), re.I)
_CLICKBAIT = re.compile("|".join(config.CLICKBAIT), re.I)

_EN = {"the", "and", "of", "to", "a", "in", "is", "for", "on", "with", "how", "why", "what", "your", "you",
       "it", "this", "that", "from", "are", "we", "i", "an", "be", "not", "my", "at", "as", "by", "new"}
_OTHER = {"de", "la", "el", "los", "las", "que", "y", "un", "una", "para", "como", "em", "um", "uma", "do",
          "da", "dos", "das", "não", "und", "der", "die", "ist", "mit", "für", "le", "les", "des", "et", "est",
          "pour", "une", "du", "il", "di", "che", "per", "het", "een", "van", "och"}

VOTE_LABELS = [  # in the order they are shown
    ("Hacker News", "{n} points on Hacker News"),
    ("Lobsters", "{n} votes on Lobsters"),
    ("Reddit", "{n} upvotes on Reddit"),
    ("Mastodon", "shared by {n} people on Mastodon"),
    ("GitHub Trending", "{n} stars today on GitHub"),
    ("DEV", "{n} reactions on DEV"),
]


# ---------- topics ----------

def keyword_hits(text: str) -> dict[str, int]:
    hits = {}
    for topic, pattern in _TOPIC_PATTERNS.items():
        n = len(pattern.findall(text or ""))
        if n:
            hits[topic] = n
    return hits


_PRIORITY = {t: i for i, t in enumerate(config.TOPIC_PRIORITY)}


def _order(weights: dict[str, int]) -> list[str]:
    return sorted(weights, key=lambda t: (-weights[t], _PRIORITY.get(t, 99)))


def keyword_topics(text: str) -> list[str]:
    return _order(keyword_hits(text))


def topics_for(c: dict) -> list[str]:
    """Up to three topics: title keywords first, then the human tags of the source, then the body.

    The body only counts with two or more hits, so one stray word ("deployment of satellites")
    does not put a story under DevOps.
    """
    title, body = keyword_hits(c["title"]), keyword_hits(c.get("text", ""))
    weight = {t: 2 * n + body.get(t, 0) for t, n in title.items()}
    from_title = _order(weight)
    from_body = _order({t: n for t, n in body.items() if n >= 2 and t not in weight})
    return list(dict.fromkeys(from_title + list(c.get("hints", [])) + from_body))[:3]


def classic_topics(title: str) -> list[str]:
    topics = keyword_topics(title)
    if _CRAFT.search(title) and "career" not in topics:
        topics.append("career")
    return topics


# ---------- filters ----------

def is_english(c: dict) -> bool:
    text = f"{c['title']} {c.get('text', '')[:200]}".lower()
    letters = re.findall(r"[^\W\d_]", text)
    if letters and sum(ch.isascii() for ch in letters) / len(letters) < 0.85:
        return False
    words = re.findall(r"[^\W\d_]+", text)
    en = sum(w in _EN for w in words)
    other = sum(w in _OTHER for w in words)
    return not (other >= 2 and other > en)


def is_general_news(url: str) -> bool:
    host = urlparse(url).netloc.lower().split(":")[0]
    return any(host == d or host.endswith("." + d) for d in config.GENERAL_NEWS)


def engineers_vouched(c: dict) -> bool:
    """Engineers voted for it on Hacker News or Lobsters, or a newsletter editor picked it."""
    return bool(c["editors"]) or any(c["votes"].get(site, 0) > 0 for site in config.ENGINEER_VOTES)


def keep(c: dict) -> bool:
    title = c["title"]
    if is_general_news(c["url"]) and not engineers_vouched(c):
        return False
    return (len(title) >= 8 and not _POLITICS.search(title) and not _NOISE.search(title)
            and is_english(c))


# ---------- scores ----------

def base_scores(cands: list[dict]) -> None:
    """Set c["base"] before dedupe: a voting site's stories are ranked against each other,
    everything else starts at its source's prior."""
    by_site = defaultdict(list)
    for c in cands:
        if c["votes"]:
            by_site[next(iter(c["votes"]))].append(c)
    for site, items in by_site.items():
        lo, span = config.VOTE_SCALE[site]
        points = sorted(c["points"] for c in items)
        n = len(points)
        for c in items:
            # Ties share the middle of their ranks, so equal votes never all sink to the bottom.
            mid = (bisect.bisect_left(points, c["points"]) + bisect.bisect_right(points, c["points"]) - 1) / 2
            pct = mid / (n - 1) if n > 1 else 0.5
            c["base"] = lo + span * pct
    for c in cands:
        c.setdefault("base", c["prior"] if c["prior"] is not None else 6.0)


def score(c: dict, now: float | None = None) -> float:
    now = now or time.time()
    s = c.get("base", 6.0)
    s += min(config.AGREEMENT_MAX, config.AGREEMENT_BONUS * (len(c["places"]) - 1))
    if _CLICKBAIT.search(c["title"]):
        s -= config.CLICKBAIT_PENALTY
    top_votes = max(c["votes"].values(), default=0)
    if c["comments"] >= 40 and c["comments"] > 1.5 * top_votes:
        s -= config.FLAMEWAR_PENALTY
    if not c["votes"] and c.get("published"):
        s -= config.AGE_PENALTY_PER_DAY * max(0.0, (now - c["published"]) / 86400)
    if is_general_news(c["url"]):
        s -= config.GENERAL_NEWS_PENALTY
    return round(max(0.0, min(10.0, s)), 2)


def signals(c: dict) -> list[str]:
    """Why a link is here, in plain facts: '412 points on Hacker News', 'picked by SRE Weekly'."""
    out = [label.format(n=f"{c['votes'][site]:,}") for site, label in VOTE_LABELS if c["votes"].get(site, 0) > 0]
    if c["editors"]:
        names = c["editors"]
        out.append("picked by " + (names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]))
    return out


# ---------- selection ----------

def select(cands: list[dict], per_topic: int = config.PICKS_PER_TOPIC,
           max_total: int = config.MAX_PICKS) -> list[dict]:
    """Best first, but each extra pick from the same source costs a little, and no topic gets more
    than `per_topic` picks as its main topic. Returns [{"cand", "topics", "score"}], best first."""
    pool = [(c, t) for c in cands if (t := topics_for(c))]
    picks, per_topic_n, per_source = [], defaultdict(int), defaultdict(int)

    def effective(item):
        return item[0]["score"] - config.SOURCE_PENALTY * per_source[item[0]["source"]]

    while pool and len(picks) < max_total:
        best = max(range(len(pool)), key=lambda k: effective(pool[k]))
        c, topics = pool.pop(best)
        if per_topic_n[topics[0]] >= per_topic:
            continue
        picks.append({"cand": c, "topics": topics, "score": round(effective((c, topics)), 2)})
        per_topic_n[topics[0]] += 1
        per_source[c["source"]] += 1
    return picks
