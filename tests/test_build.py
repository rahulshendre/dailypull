import datetime as dt
import json
import re
import time
from pathlib import Path

import pytest

from pipeline import build, classics, config, length, sources

ROOT = Path(__file__).resolve().parent.parent
WORDS = ["Kubernetes upgrade", "Postgres vacuum", "LLM agents", "Linux kernel", "Rust compiler",
         "Ransomware gang", "CSS layout", "Incident postmortem", "Open source license", "Career growth"]
SOURCES = ["Hacker News", "Lobsters"]


def fake_items(n=120):
    out = []
    for i in range(n):
        out.append(sources.candidate(SOURCES[i % 2], f"{WORDS[i % len(WORDS)]} story {i}",
                                     f"https://example.com/story/{i}", points=10 + i,
                                     published=time.time() - 3600))
    return out


def fake_classics():
    hits = [{"objectID": str(n), "title": f"{w} classic essay ({2000 + n})", "url": f"https://old.example/{n}",
             "points": 1000 - n, "created_at_i": 1_600_000_000} for n, w in enumerate(WORDS)]
    return classics.parse_hits(hits, this_year=2026)


@pytest.fixture
def fake_sources(monkeypatch):
    items = fake_items()

    async def gather_all():
        return [dict(i, votes=dict(i["votes"]), places=list(i["places"])) for i in items], \
            {"Hacker News": f"ok {len(items)}", "Lobsters": "error HTTPStatusError"}

    async def gather_classics():
        return fake_classics(), {"Hacker News classics": "ok 10"}

    async def measure(links):
        # Pretend only the first link could be measured.
        return {links[0]["url"]: 4} if links else {}

    monkeypatch.setattr(sources, "gather_all", gather_all)
    monkeypatch.setattr(classics, "gather", gather_classics)
    monkeypatch.setattr(length, "measure", measure)
    return items


def test_build_writes_valid_page_data(tmp_path, fake_sources):
    out, history = tmp_path / "data", tmp_path / "history.json"
    assert build.main(["--out", str(out), "--history", str(history)]) == 0

    doc = json.loads((out / "today.json").read_text())
    assert doc["version"] == 2
    assert doc["source_count"] == 2
    assert doc["topics"] == config.TOPICS
    assert 10 <= len(doc["picks"]) <= config.MAX_PICKS
    scores = [p["score"] for p in doc["picks"]]
    assert scores == sorted(scores, reverse=True)
    # Reading time only where it was measured, never a default.
    assert doc["picks"][0]["minutes"] == 4
    assert all(p["minutes"] is None for p in doc["picks"][1:])
    assert all(c["minutes"] is None for c in doc["classics"])
    for p in doc["picks"]:
        assert p["url"].startswith("https://example.com/story/")
        assert p["domain"] == "example.com"
        assert set(p["topics"]) <= set(config.TOPICS)
        assert p["signals"] and p["signals"][0].endswith(("on Hacker News", "on Lobsters"))
    assert dt.datetime.fromisoformat(doc["next_refresh_at"].replace("Z", "+00:00")) > \
        dt.datetime.fromisoformat(doc["generated_at"].replace("Z", "+00:00"))

    assert 1 <= len(doc["classics"]) <= len(config.TOPICS)
    for c in doc["classics"]:
        assert c["url"].startswith("https://old.example/") and c["year"] < 2026 and len(c["topics"]) == 1
        assert "classic essay" in c["title"] and "(" not in c["title"]

    saved = json.loads(history.read_text())
    assert len(saved["shown"]) == len(doc["picks"])
    assert len(saved["classics"]) == len(doc["classics"])

    # A rerun on the same day gives the same list.
    assert build.main(["--out", str(out), "--history", str(history)]) == 0
    rerun = json.loads((out / "today.json").read_text())
    assert [p["url"] for p in rerun["picks"]] == [p["url"] for p in doc["picks"]]

    # The next day the same links and classics are not picked again.
    yesterday = (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)).isoformat()
    history.write_text(json.dumps({key: {u: yesterday for u in seen} for key, seen in saved.items()}))
    assert build.main(["--out", str(out), "--history", str(history)]) == 0
    second = json.loads((out / "today.json").read_text())
    assert not {p["url"] for p in second["picks"]} & {p["url"] for p in doc["picks"]}
    assert not {c["url"] for c in second["classics"]} & {c["url"] for c in doc["classics"]}


def test_build_refuses_to_publish_when_sources_are_broken(tmp_path, fake_sources, monkeypatch):
    async def gather_all():
        return fake_items(5), {"Hacker News": "ok 5"}

    monkeypatch.setattr(sources, "gather_all", gather_all)
    out = tmp_path / "data"
    assert build.main(["--out", str(out), "--history", str(tmp_path / "h.json")]) == 2
    assert not (out / "today.json").exists()


def test_build_works_when_classics_fail(tmp_path, fake_sources, monkeypatch):
    async def broken():
        return [], {"Hacker News classics": "error no results"}

    monkeypatch.setattr(classics, "gather", broken)
    out = tmp_path / "data"
    assert build.main(["--out", str(out), "--history", str(tmp_path / "h.json")]) == 0
    assert json.loads((out / "today.json").read_text())["classics"] == []


def test_old_history_files_still_load(tmp_path):
    path = tmp_path / "h.json"
    path.write_text(json.dumps({"shown": {"https://a.example": "2026-11-20"}}))
    assert build.load_history(path) == {"shown": {"https://a.example": "2026-11-20"}, "classics": {}}
    path.write_text("[1, 2]")
    assert build.load_history(path) == {"shown": {}, "classics": {}}


def test_rerun_on_the_same_day_replaces_that_days_list(tmp_path):
    path = tmp_path / "h.json"
    path.write_text(json.dumps({"shown": {"https://a.example": "2026-11-25", "https://b.example": "2026-11-26"},
                                "classics": {"https://c.example": "2026-11-26"}}))
    assert build.load_history(path, dt.date(2026, 11, 26)) == {"shown": {"https://a.example": "2026-11-25"},
                                                                "classics": {}}


def test_next_refresh_is_next_0030_utc():
    utc = dt.timezone.utc
    assert build.next_refresh(dt.datetime(2026, 11, 25, 19, 0, tzinfo=utc)) == dt.datetime(2026, 11, 26, 0, 30, tzinfo=utc)
    assert build.next_refresh(dt.datetime(2026, 11, 26, 0, 10, tzinfo=utc)) == dt.datetime(2026, 11, 26, 0, 30, tzinfo=utc)


def test_history_drops_old_entries(tmp_path):
    path = tmp_path / "h.json"
    today = dt.date(2026, 11, 26)
    history = {"shown": {"https://old.example": "2026-10-01", "https://recent.example": "2026-11-20"},
               "classics": {"https://classic.example": "2024-01-01"}}
    build.save_history(path, history, ["https://new.example/"], ["https://another.example/"], today)
    saved = json.loads(path.read_text())
    assert set(saved["shown"]) == {"https://recent.example", "https://new.example"}
    assert set(saved["classics"]) == {"https://classic.example", "https://another.example"}


def test_frontend_topics_match_pipeline():
    js = (ROOT / "site" / "assets" / "app.js").read_text()
    block = re.search(r"const TOPICS = \{(.*?)\};", js, re.S).group(1)
    pairs = dict(re.findall(r'(\w+): "([^"]+)"', block))
    assert pairs == config.TOPICS


def test_excerpt_drops_links_boilerplate_and_newsletter_intros():
    art = lambda text: {"text": text, "kind": "article"}
    assert build.excerpt(art("https://archive.ph/pcUgy")) == ""
    assert build.excerpt(art("Too short to help.")) == ""
    assert build.excerpt(art("Why the liveness probe killed every pod at once. Continue reading on Stackademic »")) \
        == "Why the liveness probe killed every pod at once."
    out = build.excerpt(art("word " * 100))
    assert out.endswith("…") and len(out) <= 201 and not out.endswith(" …")
    assert build.excerpt({"text": "#812 November 24 Read on the Web JavaScript Weekly news and more", "kind": "newsletter"}) == ""
