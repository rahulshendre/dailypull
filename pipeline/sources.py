"""Fetch reading candidates from free public sources.

Every fetcher is isolated: a broken source is reported in `status` and skipped,
it never stops the run.
"""

from __future__ import annotations

import asyncio
import calendar
import datetime as dt
import html
import re
import time
from urllib.parse import urlparse

import feedparser
import httpx

from . import config

USER_AGENT = "DailyPull/1.0 (+https://github.com/rahulshendre/dailypull)"


def clean_text(text: str, limit: int = 300) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def community(source: str) -> str:
    """The independent crowd behind a source: every subreddit is Reddit, every Mastodon server is Mastodon."""
    return "Reddit" if source.startswith("r/") else source


def candidate(source, title, url, *, text="", points=0, comments=0, published=None,
              discussion=None, hints=(), kind="article", prior=None, editors=()) -> dict:
    site = community(source)
    votes = {site: int(points or 0)} if site in config.VOTE_SCALE else {}
    return {
        "source": source,
        "title": clean_text(title, 200),
        "url": url,
        "text": clean_text(text),
        "points": int(points or 0),
        "comments": int(comments or 0),
        "published": published,
        "discussion": discussion,
        "hints": sorted({h for h in hints if h in config.TOPICS}),
        "kind": kind,
        "prior": prior,
        "votes": votes,                 # site -> points, only for voting sites
        "editors": list(editors),       # newsletters whose editors linked it
        "places": [site],               # independent places the link was seen (sites, editors, blogs)
    }


def feed_entry(spec) -> tuple[str, str, list, float, str]:
    """Unpack a FEEDS row, filling in the optional prior and kind."""
    name, url, hints, *rest = spec
    prior = rest[0] if len(rest) > 0 else 6.0
    kind = rest[1] if len(rest) > 1 else "article"
    return name, url, hints, prior, kind


def status_key(name: str, url: str) -> str:
    return f"{name} #{url.rstrip('/').rsplit('/', 1)[-1]}" if name == "Medium" else name


def tags_to_topics(tags) -> list[str]:
    return sorted({config.TAG_TOPICS[t.lower()] for t in tags if t.lower() in config.TAG_TOPICS})


def host_of(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def guess_kind(url: str) -> str:
    host, path = host_of(url), urlparse(url).path
    if host == "github.com" and re.fullmatch(r"/[^/]+/[^/]+/?", path):
        return "repo"
    if host in ("youtube.com", "youtu.be", "m.youtube.com", "vimeo.com"):
        return "video"
    if host == "arxiv.org" or path.lower().endswith(".pdf"):
        return "paper"
    return "article"


# ---------- parsers (pure functions, unit tested) ----------

def parse_feed(name: str, body: str, hints, now: float | None = None, prior: float = 6.0,
               kind: str = "article") -> list[dict]:
    now = now or time.time()
    out = []
    for entry in feedparser.parse(body).entries:
        stamp = entry.get("published_parsed") or entry.get("updated_parsed")
        published = calendar.timegm(stamp) if stamp else None
        if published is None or now - published > config.MAX_AGE_HOURS * 3600:
            continue
        link = entry.get("link", "")
        if not link.startswith("http"):
            continue
        summary = entry.get("summary", "")
        if not summary and entry.get("content"):
            summary = entry["content"][0].get("value", "")
        out.append(candidate(name, entry.get("title", ""), link, text=summary, published=published,
                             hints=hints, kind=kind, prior=prior))
        if len(out) >= config.PER_FEED:
            break
    return out


ANCHOR_RE = re.compile(r'<a\s[^>]*?href="(https?://[^"]+)"[^>]*>(.*?)</a>', re.S | re.I)
LINK_STOP_RE = re.compile(
    r"^(read|view)\b.*\b(web|browser|online|version|newsletter)\b|^view on |^read more|^click here|^permalink"
    r"|unsubscribe|^subscribe|advertis|sponsor|join the discussion|^@", re.I)
SPONSOR_AFTER_RE = re.compile(r"\bsponsor(ed)?\b", re.I)
SPONSOR_BEFORE_RE = re.compile(r"\bour sponsor|\bsponsored by\b|\bmessage from\b", re.I)
NOT_A_READ_RE = re.compile(r"github\.com/[^/]+/[^/]+/(pull|issues|commit|compare)/|\.(png|jpe?g|gif|webp)$", re.I)


def skip_link(url: str, own_host: str = "") -> bool:
    host = host_of(url)
    if any(host == h or host.endswith("." + h) for h in config.SKIP_LINK_HOSTS):
        return True
    if own_host and host == own_host and not re.search(r"/link/\d+", url):
        return True  # the newsletter's own pages (archive, issue page), not a read
    return bool(NOT_A_READ_RE.search(url))


def extract_links(body: str, own_host: str = "") -> list[tuple[str, str, str]]:
    """The links an editor picked in one newsletter issue: (url, title, the editor's blurb).

    Only anchors with a real title count. Sponsor blocks, navigation and social links are skipped.
    """
    anchors = [(m.start(), m.end(), html.unescape(m.group(1)), clean_text(m.group(2), 200))
               for m in ANCHOR_RE.finditer(body or "")]
    # A real headline: long enough, starts like a title. "separate downloads" mid-sentence is not one.
    titled = [a for a in anchors if len(a[3]) >= 15]
    picked, sponsored = [], set()
    for i, (start, end, url, title) in enumerate(titled):
        before = clean_text(body[titled[i - 1][1] if i else 0:start], 2000)
        after = clean_text(body[end:titled[i + 1][0] if i + 1 < len(titled) else len(body)], 2000)
        if SPONSOR_AFTER_RE.search(after) or SPONSOR_BEFORE_RE.search(before):
            sponsored.add(url)
        elif not LINK_STOP_RE.search(title) and (title[0].isupper() or title[0].isdigit()) \
                and len(title.split()) >= 3:
            picked.append((url, title, after[:300]))
    out, seen = [], set()
    for url, title, blurb in picked:
        if url in sponsored or url in seen or skip_link(url, own_host):
            continue
        seen.add(url)
        out.append((url, title, blurb))
    return out


def parse_editor(name: str, body: str, hints, style: str = "issue", now: float | None = None) -> list[dict]:
    """Links from a curated newsletter's recent issues, each counted as one editor's pick."""
    now = now or time.time()
    out = []
    for entry in feedparser.parse(body).entries:
        stamp = entry.get("published_parsed") or entry.get("updated_parsed")
        published = calendar.timegm(stamp) if stamp else None
        if published is None or now - published > config.EDITOR_MAX_AGE_DAYS * 86400:
            continue
        content = (entry.get("content") or [{}])[0].get("value") or entry.get("summary", "")
        links = extract_links(content, host_of(entry.get("link", "")))
        if style == "linkblog":
            links = links[:1]
        for url, title, blurb in links:
            out.append(candidate(name, title, url, text=blurb, published=published, hints=hints,
                                 kind=guess_kind(url), prior=config.EDITOR_PRIOR, editors=[name]))
    return out[:config.EDITOR_MAX_LINKS]


def parse_mastodon(instance: str, data: list, now: float | None = None) -> list[dict]:
    """Trending links: `accounts` is how many people shared the link per day (newest day first)."""
    now = now or time.time()
    out = []
    for link in data:
        url = link.get("url", "")
        if not url.startswith("http") or link.get("type") not in (None, "link", "video"):
            continue
        history = link.get("history") or []
        accounts = sum(int(h.get("accounts", 0)) for h in history[:2])
        published = None
        if link.get("published_at"):
            published = dt.datetime.fromisoformat(link["published_at"].replace("Z", "+00:00")).timestamp()
        if published and now - published > config.MAX_AGE_HOURS * 3600:
            continue
        text = link.get("description", "")
        if link.get("provider_name"):
            text = f"{text} ({link['provider_name']})".strip()
        out.append(candidate(
            "Mastodon", link.get("title", ""), url, text=text, points=accounts, published=published,
            kind="video" if link.get("type") == "video" else "article",
        ))
    return out


def parse_reddit(sub: str, data: dict) -> list[dict]:
    out = []
    for child in data.get("data", {}).get("children", []):
        post = child.get("data", {})
        if post.get("stickied") or post.get("over_18") or post.get("removed_by_category"):
            continue
        permalink = "https://www.reddit.com" + post.get("permalink", "")
        external = post.get("url_overridden_by_dest") or ""
        is_link = external.startswith("http") and "reddit.com" not in external and "redd.it" not in external
        out.append(candidate(
            f"r/{sub}", post.get("title", ""), external if is_link else permalink,
            text=post.get("selftext", ""), points=post.get("score"), comments=post.get("num_comments"),
            published=post.get("created_utc"), discussion=permalink,
            hints=config.SUBREDDIT_TOPICS.get(sub, []), kind="article" if is_link else "discussion",
        ))
    return out


def parse_hn(data: dict) -> list[dict]:
    out = []
    for hit in data.get("hits", []):
        hn_url = f"https://news.ycombinator.com/item?id={hit['objectID']}"
        url = hit.get("url") or hn_url
        title = hit.get("title") or ""
        kind = "discussion" if (not hit.get("url") or title.startswith(("Ask HN", "Tell HN"))) else "article"
        out.append(candidate(
            "Hacker News", title, url, text=hit.get("story_text") or "",
            points=hit.get("points"), comments=hit.get("num_comments"),
            published=hit.get("created_at_i"), discussion=hn_url, kind=kind,
        ))
    return out


def parse_lobsters(data: list) -> list[dict]:
    out = []
    for story in data:
        published = dt.datetime.fromisoformat(story["created_at"]).timestamp()
        out.append(candidate(
            "Lobsters", story["title"], story.get("url") or story["short_id_url"],
            text=story.get("description_plain", ""), points=story.get("score"),
            comments=story.get("comment_count"), published=published,
            discussion=story["short_id_url"], hints=tags_to_topics(story.get("tags", [])),
            kind="article" if story.get("url") else "discussion",
        ))
    return out


def parse_devto(data: list) -> list[dict]:
    out = []
    for art in data:
        published = None
        if art.get("published_at"):
            published = dt.datetime.fromisoformat(art["published_at"].replace("Z", "+00:00")).timestamp()
        out.append(candidate(
            "DEV", art.get("title", ""), art.get("url", ""), text=art.get("description", ""),
            points=art.get("positive_reactions_count"), comments=art.get("comments_count"),
            published=published, hints=tags_to_topics(art.get("tag_list", [])),
        ))
    return [c for c in out if c["url"].startswith("http")]


def parse_github_trending(page: str) -> list[dict]:
    out = []
    for block in re.findall(r'<article class="Box-row">(.*?)</article>', page, re.S):
        repo = re.search(r'<h2[^>]*>\s*<a[^>]*href="/([^"/]+/[^"/]+)"', block, re.S)
        if not repo:
            continue
        desc = re.search(r'<p class="col-9[^"]*">(.*?)</p>', block, re.S)
        lang = re.search(r'itemprop="programmingLanguage">([^<]+)<', block)
        stars = re.search(r"([\d,]+) stars today", block)
        item = candidate(
            "GitHub Trending", repo.group(1), f"https://github.com/{repo.group(1)}",
            text=desc.group(1) if desc else "",
            points=int(stars.group(1).replace(",", "")) if stars else 0, hints=["oss"], kind="repo",
        )
        item["language"] = lang.group(1).strip() if lang else ""
        out.append(item)
    return out


# ---------- fetchers ----------

async def _get(client: httpx.AsyncClient, url: str) -> httpx.Response:
    resp = await client.get(url)
    resp.raise_for_status()
    return resp


async def _run(name: str, status: dict, coro) -> list[dict]:
    try:
        items = await coro
        status[name] = f"ok {len(items)}"
        return items
    except Exception as exc:  # one bad source must not stop the run
        status[name] = f"error {type(exc).__name__}"
        return []


async def resolve_redirects(client: httpx.AsyncClient, items: list[dict]) -> list[dict]:
    """Newsletters wrap links in click trackers (/link/123). Swap each for where it really goes."""
    async def one(c):
        if not re.search(r"/link/\d+", urlparse(c["url"]).path):
            return c
        try:
            resp = await client.get(c["url"], follow_redirects=False)
        except httpx.HTTPError:
            return None
        target = resp.headers.get("location", "")
        if resp.status_code not in (301, 302, 303, 307, 308) or not target.startswith("http") or skip_link(target):
            return None
        c["url"], c["kind"] = target, guess_kind(target)
        return c

    resolved = await asyncio.gather(*(one(c) for c in items))
    return [c for c in resolved if c]


async def fetch_reddit(client: httpx.AsyncClient, client_id: str, secret: str) -> list[dict]:
    """Reddit's official API, app-only OAuth (free for low volume). Anonymous access is blocked."""
    token = await client.post(
        "https://www.reddit.com/api/v1/access_token",
        data={"grant_type": "client_credentials"},
        auth=(client_id, secret),
    )
    token.raise_for_status()
    headers = {"Authorization": f"bearer {token.json()['access_token']}"}
    out = []
    for sub in config.SUBREDDITS:
        resp = await client.get(f"https://oauth.reddit.com/r/{sub}/top", params={"t": "day", "limit": 10},
                                headers=headers)
        if resp.status_code == 200:
            out += parse_reddit(sub, resp.json())
        await asyncio.sleep(1)  # stay well under the rate limit
    return out


async def gather_all(timeout: float = 40.0, env: dict | None = None,
                     transport: httpx.AsyncBaseTransport | None = None) -> tuple[list[dict], dict]:
    """Fetch every source concurrently. Returns (candidates, status per source)."""
    import os

    env = os.environ if env is None else env
    status: dict = {}
    limits = httpx.Limits(max_connections=16)
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, follow_redirects=True,
                                 timeout=timeout, limits=limits, transport=transport) as client:
        async def feed(spec):
            name, url, hints, prior, kind = feed_entry(spec)
            return parse_feed(name, (await _get(client, url)).text, hints, prior=prior, kind=kind)

        async def mastodon(instance):
            resp = await _get(client, f"https://{instance}/api/v1/trends/links?limit=20")
            return parse_mastodon(instance, resp.json())

        async def editor(spec):
            name, url, hints, style = spec
            items = parse_editor(name, (await _get(client, url)).text, hints, style)
            return await resolve_redirects(client, items)

        async def hn():
            # Stories from the last two days that people kept voting for, not just what is on top right now.
            since = int(time.time()) - config.HN_WINDOW_HOURS * 3600
            url = ("https://hn.algolia.com/api/v1/search?tags=story&hitsPerPage=100"
                   f"&numericFilters=created_at_i>{since},points>={config.HN_MIN_POINTS}")
            return parse_hn((await _get(client, url)).json())

        async def lobsters():
            return parse_lobsters((await _get(client, "https://lobste.rs/hottest.json")).json()[:25])

        async def devto():
            return parse_devto((await _get(client, "https://dev.to/api/articles?top=1&per_page=25")).json())

        async def trending():
            return parse_github_trending((await _get(client, "https://github.com/trending?since=daily")).text)[:20]

        jobs = [_run(status_key(spec[0], spec[1]), status, feed(spec)) for spec in config.FEEDS]
        jobs += [_run(spec[0], status, editor(spec)) for spec in config.EDITORS]
        jobs += [_run(f"Mastodon {i}", status, mastodon(i)) for i in config.MASTODON_INSTANCES]
        jobs += [
            _run("Hacker News", status, hn()),
            _run("Lobsters", status, lobsters()),
            _run("DEV", status, devto()),
            _run("GitHub Trending", status, trending()),
        ]
        reddit_id, reddit_secret = env.get("REDDIT_CLIENT_ID"), env.get("REDDIT_CLIENT_SECRET")
        if reddit_id and reddit_secret:
            jobs.append(_run("Reddit", status, fetch_reddit(client, reddit_id, reddit_secret)))
        else:
            status["Reddit"] = "skipped (set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET to enable)"
        results = await asyncio.gather(*jobs)
    return [c for group in results for c in group], status


def normalize_url(url: str) -> str:
    url = url.split("#")[0]
    url = re.sub(r"[?&](utm_[^=&]+|ref|source)=[^&]*", "", url)
    return url.rstrip("/?&").lower()


def dedupe(cands: list[dict]) -> list[dict]:
    """One entry per link. Copies add their votes, editors and places: that is the agreement signal."""
    seen: dict[str, dict] = {}
    for c in cands:
        key = normalize_url(c["url"])
        if not c["title"] or not key:
            continue
        if key in seen:
            kept = seen[key]
            kept["points"] = max(kept["points"], c["points"])
            kept["comments"] = max(kept["comments"], c["comments"])
            kept["discussion"] = kept["discussion"] or c["discussion"]
            # Topic hints: the ones more places agree on come first.
            counts = kept.setdefault("hint_counts", {h: 1 for h in kept["hints"]})
            for h in c["hints"]:
                counts[h] = counts.get(h, 0) + 1
            kept["hints"] = sorted(counts, key=lambda h: -counts[h])
            for site, n in c["votes"].items():
                kept["votes"][site] = max(kept["votes"].get(site, 0), n)
            kept["editors"] += [e for e in c["editors"] if e not in kept["editors"]]
            kept["places"] += [p for p in c["places"] if p not in kept["places"]]
            kept["base"] = max(kept.get("base", 0.0), c.get("base", 0.0))
            if not kept["text"] and c["text"]:
                kept["text"] = c["text"]
            continue
        seen[key] = {**c, "votes": dict(c["votes"]), "editors": list(c["editors"]), "places": list(c["places"])}
    return list(seen.values())
