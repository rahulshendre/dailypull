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
    assert out[0]["votes"] == {"Hacker News": 50, "Lobsters": 20}
    assert out[0]["places"] == ["Hacker News", "Lobsters"]
    assert a["votes"] == {"Hacker News": 50}  # inputs are not changed


def test_feed_entry_defaults_and_overrides():
    assert sources.feed_entry(("A", "u", ["ai"])) == ("A", "u", ["ai"], 6.0, "article")
    assert sources.feed_entry(("A", "u", [], 3.0, "video")) == ("A", "u", [], 3.0, "video")


def test_every_configured_feed_is_well_formed():
    for spec in config.FEEDS:
        name, url, hints, prior, kind = sources.feed_entry(spec)
        assert url.startswith("https://"), name
        assert set(hints) <= set(config.TOPICS), name
        assert 0 <= prior <= 10 and kind in config.KINDS, name


def test_every_configured_editor_is_well_formed():
    for name, url, hints, style in config.EDITORS:
        assert url.startswith("https://"), name
        assert set(hints) <= set(config.TOPICS), name
        assert style in ("issue", "linkblog"), name


def test_status_keys_are_unique():
    keys = [sources.status_key(spec[0], spec[1]) for spec in config.FEEDS] + [e[0] for e in config.EDITORS]
    assert len(keys) == len(set(keys))


def test_reddit_subs_and_mastodon_servers_count_as_one_place():
    assert sources.community("r/devops") == "Reddit"
    assert sources.candidate("r/sre", "T", "https://e.com", points=5)["votes"] == {"Reddit": 5}
    assert sources.candidate("Julia Evans", "T", "https://e.com")["votes"] == {}


def test_guess_kind():
    assert sources.guess_kind("https://github.com/owner/repo") == "repo"
    assert sources.guess_kind("https://github.com/owner/repo/blob/main/x.md") == "article"
    assert sources.guess_kind("https://www.youtube.com/watch?v=1") == "video"
    assert sources.guess_kind("https://arxiv.org/abs/2611.1") == "paper"
    assert sources.guess_kind("https://example.com/paper.PDF") == "paper"


ISSUE = """
<p><a href="https://golangweekly.com/link/1/rss">Read the Web Version</a></p>
<table><tr><td><p><a href="https://golangweekly.com/link/2/rss">Probabilistic Data Structures in Go</a>
  A tour of Bloom filters and HyperLogLog. <span>Anton Zhiyanov</span></p></td></tr></table>
<table><tr><td><p><a href="https://golangweekly.com/link/3/rss">Webhooks You Can Trust in Production</a>
  Signed callbacks and retries.</p><p>Svix <span>sponsor</span></p></td></tr></table>
<table><tr><td><p><a href="https://golangweekly.com/link/4/rss">Go 1.30 Release Candidate Is Out</a>
  Try it now, see <a href="https://golangweekly.com/link/5/rss">separate downloads</a>.</p></td></tr></table>
<p><a href="https://twitter.com/golangweekly">Follow Golang Weekly on Twitter</a></p>
<p><a href="https://github.com/golang/go/pull/123">runtime: fix a race in the scheduler</a></p>
<p><a href="https://golangweekly.com/issues/625">Browse the whole archive here</a></p>
"""

SRE = """<a href="https://sreweekly.com/sre-weekly-issue-544/">View on sreweekly.com</a>
<div><h2>A message from our sponsor, <a href="https://sreweekly.com/link/544">JAMS Software</a>:</h2>
<p>Moved on-call fast.</p><p><a href="https://sreweekly.com/link/544">Run the PagerDuty conversion, free for 14 days</a></p></div>
<p><a href="https://greatcircle.com/blog/2026/11/10/fix-forward-trap/">The fix-forward trap</a></p>
<p>Rolling forward is tempting.</p>"""


def test_extract_links_keeps_editors_picks_only():
    links = sources.extract_links(ISSUE, "golangweekly.com")
    assert [(u, t) for u, t, _ in links] == [
        ("https://golangweekly.com/link/2/rss", "Probabilistic Data Structures in Go"),
        ("https://golangweekly.com/link/4/rss", "Go 1.30 Release Candidate Is Out"),
    ]
    assert links[0][2].startswith("A tour of Bloom filters")


def test_extract_links_skips_sponsor_blocks_before_the_link():
    assert sources.extract_links(SRE, "sreweekly.com") == [
        ("https://greatcircle.com/blog/2026/11/10/fix-forward-trap/", "The fix-forward trap",
         "Rolling forward is tempting.")]


def _rss(body, date="Wed, 25 Nov 2026 10:00:00 GMT", link="https://golangweekly.com/issues/625"):
    from xml.sax.saxutils import escape
    return (f"<rss version='2.0'><channel><title>T</title><item><title>Issue</title><link>{link}</link>"
            f"<pubDate>{date}</pubDate><description>{escape(body)}</description></item></channel></rss>")


def test_parse_editor_marks_each_link_as_an_editors_pick():
    items = sources.parse_editor("Golang Weekly", _rss(ISSUE), ["languages"], now=NOW)
    assert len(items) == 2
    assert items[0]["editors"] == ["Golang Weekly"] and items[0]["places"] == ["Golang Weekly"]
    assert items[0]["prior"] == config.EDITOR_PRIOR and items[0]["hints"] == ["languages"]
    assert sources.parse_editor("Golang Weekly", _rss(ISSUE, date="Mon, 02 Nov 2026 10:00:00 GMT"), [], now=NOW) == []
    assert len(sources.parse_editor("Simon", _rss(ISSUE), [], style="linkblog", now=NOW)) == 1


def test_resolve_redirects_follows_click_trackers():
    def handler(request: httpx.Request) -> httpx.Response:
        targets = {"/link/2/rss": "https://antonz.org/probabilistic/", "/link/9/rss": "https://twitter.com/x"}
        if request.url.path in targets:
            return httpx.Response(301, headers={"location": targets[request.url.path]})
        return httpx.Response(404)

    items = [sources.candidate("Golang Weekly", "Probabilistic Data Structures", "https://golangweekly.com/link/2/rss"),
             sources.candidate("Golang Weekly", "Broken tracker link here", "https://golangweekly.com/link/4/rss"),
             sources.candidate("Golang Weekly", "Social link we never want", "https://golangweekly.com/link/9/rss"),
             sources.candidate("Import AI", "A direct link to a paper", "https://arxiv.org/abs/1")]

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await sources.resolve_redirects(client, items)

    out = asyncio.run(run())
    assert [c["url"] for c in out] == ["https://antonz.org/probabilistic/", "https://arxiv.org/abs/1"]
    assert out[1]["kind"] == "article" or out[1]["kind"] == "paper"


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
    assert status["SRE Weekly"].startswith("error")
    assert status["Reddit"].startswith("skipped")
