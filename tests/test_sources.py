import asyncio
import calendar
import json
import time
from pathlib import Path

import httpx

from pipeline import config, sources

FIX = Path(__file__).parent / "fixtures"
NOW = calendar.timegm((2026, 11, 25, 12, 0, 0))

RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>T</title>
<item><title>Fresh &amp; useful</title><link>https://example.com/fresh</link>
  <pubDate>Wed, 25 Nov 2026 10:00:00 GMT</pubDate><description>&lt;p&gt;Hello &lt;b&gt;world&lt;/b&gt;&lt;/p&gt;</description></item>
<item><title>Old post</title><link>https://example.com/old</link><pubDate>Mon, 01 Jan 2024 10:00:00 GMT</pubDate></item>
<item><title>No date</title><link>https://example.com/nodate</link></item>
<item><title>Relative link</title><link>/relative</link><pubDate>Wed, 25 Nov 2026 10:00:00 GMT</pubDate></item>
</channel></rss>"""


def load(name):
    return json.loads((FIX / name).read_text())


def test_parse_feed_keeps_only_fresh_absolute_links():
    items = sources.parse_feed("Blog", RSS, ["web"], now=NOW, prior=5.0, kind="newsletter")
    assert [i["url"] for i in items] == ["https://example.com/fresh"]
    item = items[0]
    assert item["title"] == "Fresh & useful"
    assert item["text"] == "Hello world"
    assert item["hints"] == ["web"]
    assert item["prior"] == 5.0
    assert item["kind"] == "newsletter"


def test_parse_feed_caps_items_per_feed():
    entries = "".join(
        f"<item><title>Post {n}</title><link>https://example.com/{n}</link>"
        f"<pubDate>Wed, 25 Nov 2026 10:00:00 GMT</pubDate></item>" for n in range(20)
    )
    body = f"<rss version='2.0'><channel><title>T</title>{entries}</channel></rss>"
    assert len(sources.parse_feed("Blog", body, [], now=NOW)) == config.PER_FEED


def test_parse_feed_ignores_unknown_topic_hints():
    assert sources.parse_feed("Blog", RSS, ["web", "nope"], now=NOW)[0]["hints"] == ["web"]


def test_parse_hn_real_fixture():
    items = sources.parse_hn(load("hn.json"))
    assert len(items) == 3
    for i in items:
        assert i["source"] == "Hacker News"
        assert i["url"].startswith("http")
        assert i["discussion"].startswith("https://news.ycombinator.com/item?id=")
        assert i["points"] > 0


def test_parse_lobsters_real_fixture():
    items = sources.parse_lobsters(load("lobsters.json"))
    assert len(items) == 3
    assert all(i["discussion"].startswith("https://lobste.rs/") for i in items)
    assert all(set(i["hints"]) <= set(config.TOPICS) for i in items)


def test_parse_devto_real_fixture():
    items = sources.parse_devto(load("devto.json"))
    assert items and all(i["url"].startswith("https://dev.to/") for i in items)


def test_parse_github_trending_real_fixture():
    items = sources.parse_github_trending((FIX / "trending.html").read_text())
    assert len(items) == 3
    for i in items:
        assert i["url"].startswith("https://github.com/") and i["url"].count("/") == 4
        assert i["kind"] == "repo"
        assert i["points"] > 0
        assert "language" in i


def test_parse_mastodon_real_fixture():
    data = load("mastodon.json")
    items = sources.parse_mastodon("hachyderm.io", data, now=time.time())
    assert items
    first = next(link for link in data if link["url"] == items[0]["url"])
    expected = sum(int(h["accounts"]) for h in first["history"][:2])
    assert items[0]["points"] == expected


def test_parse_reddit_skips_sticky_and_nsfw():
    def post(**kw):
        base = {"title": "T", "permalink": "/r/sre/comments/1/t/", "score": 10, "num_comments": 2,
                "created_utc": NOW, "selftext": ""}
        base.update(kw)
        return {"data": base}

    data = {"data": {"children": [
        post(title="Link post", url_overridden_by_dest="https://example.com/a"),
        post(title="Self post", selftext="How do you run on-call?"),
        post(title="Pinned", stickied=True),
        post(title="Spicy", over_18=True),
    ]}}
    items = sources.parse_reddit("sre", data)
    assert [i["title"] for i in items] == ["Link post", "Self post"]
    assert items[0]["url"] == "https://example.com/a"
    assert items[0]["discussion"] == "https://www.reddit.com/r/sre/comments/1/t/"
    assert items[1]["url"] == items[1]["discussion"]
    assert items[1]["kind"] == "discussion"
    assert items[0]["hints"] == ["devops"]


def test_normalize_url_strips_tracking_and_case():
    assert sources.normalize_url("https://Example.com/Post/?utm_source=x#top") == "https://example.com/post"
    assert sources.normalize_url("https://example.com/a?id=1&utm_medium=y") == "https://example.com/a?id=1"


def test_dedupe_merges_copies():
    a = sources.candidate("Hacker News", "Same", "https://example.com/x/", points=50,
                          discussion="https://news.ycombinator.com/item?id=1")
    b = sources.candidate("Lobsters", "Same", "https://example.com/x?utm_source=lobsters", points=20,
                          hints=["web"])
    out = sources.dedupe([a, b])
    assert len(out) == 1
    assert out[0]["points"] == 50
    assert out[0]["discussion"] == "https://news.ycombinator.com/item?id=1"
    assert out[0]["hints"] == ["web"]


def test_feed_entry_defaults_and_overrides():
    assert sources.feed_entry(("A", "u", ["ai"])) == ("A", "u", ["ai"], 6.0, "article")
    assert sources.feed_entry(("A", "u", [], 3.0, "video")) == ("A", "u", [], 3.0, "video")


def test_every_configured_feed_is_well_formed():
    for spec in config.FEEDS:
        name, url, hints, prior, kind = sources.feed_entry(spec)
        assert url.startswith("https://"), name
        assert set(hints) <= set(config.TOPICS), name
        assert 0 <= prior <= 10 and kind in config.KINDS, name


def test_status_keys_are_unique():
    keys = [sources.status_key(spec[0], spec[1]) for spec in config.FEEDS]
    assert len(keys) == len(set(keys))


def test_gather_all_survives_broken_sources():
    hn = load("hn.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "hn.algolia.com":
            return httpx.Response(200, json=hn)
        return httpx.Response(503)

    items, status = asyncio.run(sources.gather_all(env={}, transport=httpx.MockTransport(handler)))
    assert len(items) == 3
    assert status["Hacker News"] == "ok 3"
    assert status["Lobsters"].startswith("error")
    assert status["Reddit"].startswith("skipped")
