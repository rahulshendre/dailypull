import asyncio

import httpx

from pipeline import classics, config


def hit(oid, title, url, points, posted=1_600_000_000):
    return {"objectID": str(oid), "title": title, "url": url, "points": points, "created_at_i": posted}


def test_parse_hits_keeps_old_well_voted_articles():
    hits = [
        hit(1, "Let's Build a Simple Database (2017)", "https://cstack.github.io/db_tutorial/", 900),
        hit(2, "Too new (2025)", "https://example.com/new", 900),
        hit(3, "Few votes (2010)", "https://example.com/few", 20),
        hit(4, "No year tag at all", "https://example.com/none", 900),
        hit(5, "Show HN: My thing (2012)", "https://example.com/show", 900),
        hit(6, "Company X announces Y (2012)", "https://example.com/news", 900),
        hit(7, "Ask without a link (2012)", "", 900),
    ]
    out = classics.parse_hits(hits, this_year=2026)
    assert [c["title"] for c in out] == ["Let's Build a Simple Database"]
    c = out[0]
    assert c["year"] == 2017 and c["points"] == 900 and c["reposts"] == 1
    assert c["discussion"] == "https://news.ycombinator.com/item?id=1"


def test_reposts_add_up_and_the_best_post_is_kept():
    hits = [
        hit(1, "Virtual DOM is pure overhead (2018)", "https://svelte.dev/blog/virtual-dom", 400),
        hit(2, "Virtual DOM is pure overhead (2018)", "https://svelte.dev/blog/virtual-dom/", 900),
        hit(2, "Virtual DOM is pure overhead (2018)", "https://svelte.dev/blog/virtual-dom/", 900),  # same post twice
    ]
    [c] = classics.parse_hits(hits, this_year=2026)
    assert c["reposts"] == 2 and c["total"] == 1300 and c["points"] == 900
    assert c["discussion"].endswith("id=2")


def test_pick_gives_one_unseen_classic_per_topic():
    items = classics.parse_hits([
        hit(1, "Let's Build a Simple Database (2017)", "https://a.example/db", 900),
        hit(2, "What ORMs have taught me: just learn SQL (2014)", "https://b.example/orm", 800),
        hit(3, "Knightmare: A DevOps Cautionary Tale (2014)", "https://c.example/knight", 500),
    ], this_year=2026)
    picked = classics.pick(items, seen={"https://a.example/db": "2026-01-01"})
    by_topic = {c["topics"][0]: c["title"] for c in picked}
    assert by_topic == {"backend": "What ORMs have taught me: just learn SQL",
                        "devops": "Knightmare: A DevOps Cautionary Tale"}


def test_gather_searches_every_year_and_survives_failures():
    asked = []

    def handler(request: httpx.Request) -> httpx.Response:
        year = request.url.params["query"]
        asked.append(int(year))
        if year == "2015":
            return httpx.Response(200, json={"hits": [hit(9, "Choose Boring Technology (2015)",
                                                          "https://boringtechnology.club", 1500)]})
        if year == "2016":
            return httpx.Response(500)
        return httpx.Response(200, json={"hits": []})

    items, status = asyncio.run(classics.gather(transport=httpx.MockTransport(handler), this_year=2026))
    assert sorted(asked) == list(range(config.CLASSIC_FIRST_YEAR, 2026 - config.CLASSIC_MIN_AGE_YEARS + 1))
    assert [c["title"] for c in items] == ["Choose Boring Technology"]
    assert status["Hacker News classics"].startswith("ok 1 (1 of")
