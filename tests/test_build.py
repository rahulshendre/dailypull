import datetime as dt
import json
import re
import time
from pathlib import Path

import pytest

from pipeline import build, config, curate, sources

ROOT = Path(__file__).resolve().parent.parent
WORDS = ["Kubernetes upgrade", "Postgres vacuum", "LLM agents", "Linux kernel", "Rust compiler",
         "Ransomware gang", "CSS layout", "Incident postmortem", "Open source license", "Career growth"]


def fake_items(n=120):
    out = []
    for i in range(n):
        out.append(sources.candidate("Hacker News", f"{WORDS[i % len(WORDS)]} story {i}",
                                     f"https://example.com/story/{i}", points=10 + i,
                                     published=time.time() - 3600))
    return out


@pytest.fixture
def fake_sources(monkeypatch):
    items = fake_items()

    async def gather_all():
        return [dict(i) for i in items], {"Hacker News": f"ok {len(items)}", "Lobsters": "error HTTPStatusError"}

    monkeypatch.setattr(sources, "gather_all", gather_all)
    return items


def test_build_without_ai_writes_valid_page_data(tmp_path, fake_sources, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out, history = tmp_path / "data", tmp_path / "history.json"
    assert build.main(["--out", str(out), "--history", str(history)]) == 0

    doc = json.loads((out / "today.json").read_text())
    assert doc["version"] == 1
    assert doc["curated_by"] == "ranking"
    assert doc["source_count"] == 1
    assert doc["topics"] == config.TOPICS
    assert 10 <= len(doc["picks"]) <= 50
    scores = [p["score"] for p in doc["picks"]]
    assert scores == sorted(scores, reverse=True)
    for p in doc["picks"]:
        assert p["url"].startswith("https://example.com/story/")
        assert set(p["topics"]) <= set(config.TOPICS)
    assert dt.datetime.fromisoformat(doc["next_refresh_at"].replace("Z", "+00:00")) > \
        dt.datetime.fromisoformat(doc["generated_at"].replace("Z", "+00:00"))

    shown = json.loads(history.read_text())["shown"]
    assert len(shown) == len(doc["picks"])

    # The next day the same links are not picked again.
    assert build.main(["--out", str(out), "--history", str(history)]) == 0
    second = json.loads((out / "today.json").read_text())
    assert not {p["url"] for p in second["picks"]} & {p["url"] for p in doc["picks"]}


def test_build_refuses_to_publish_when_sources_are_broken(tmp_path, monkeypatch):
    async def gather_all():
        return fake_items(5), {"Hacker News": "ok 5"}

    monkeypatch.setattr(sources, "gather_all", gather_all)
    out = tmp_path / "data"
    assert build.main(["--out", str(out), "--history", str(tmp_path / "h.json"), "--no-ai"]) == 2
    assert not (out / "today.json").exists()


def test_build_falls_back_to_ranking_when_claude_fails(tmp_path, fake_sources, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    def broken(*args, **kwargs):
        raise curate.CurationError("down")

    monkeypatch.setattr(curate, "ask_claude", broken)
    out = tmp_path / "data"
    assert build.main(["--out", str(out), "--history", str(tmp_path / "h.json")]) == 0
    assert json.loads((out / "today.json").read_text())["curated_by"] == "ranking"


def test_build_uses_claude_picks_when_available(tmp_path, fake_sources, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("DD_MODEL", "claude-opus-5-5")

    def fake_claude(cands, model, client=None):
        return {"headline": "Big day", "picks": [
            {"id": c["cid"], "title": c["title"].upper(), "why": "Because.", "topics": ["ai"],
             "minutes": 5, "kind": "article", "score": 7} for c in cands[:12]]}

    monkeypatch.setattr(curate, "ask_claude", fake_claude)
    out = tmp_path / "data"
    assert build.main(["--out", str(out), "--history", str(tmp_path / "h.json")]) == 0
    doc = json.loads((out / "today.json").read_text())
    assert doc["curated_by"] == "claude-opus-5-5"
    assert doc["headline"] == "Big day"
    assert len(doc["picks"]) == 12
    assert all(p["why"] == "Because." for p in doc["picks"])


def test_next_refresh_is_next_0030_utc():
    utc = dt.timezone.utc
    assert build.next_refresh(dt.datetime(2026, 11, 25, 19, 0, tzinfo=utc)) == dt.datetime(2026, 11, 26, 0, 30, tzinfo=utc)
    assert build.next_refresh(dt.datetime(2026, 11, 26, 0, 10, tzinfo=utc)) == dt.datetime(2026, 11, 26, 0, 30, tzinfo=utc)


def test_history_drops_old_entries(tmp_path):
    path = tmp_path / "h.json"
    today = dt.date(2026, 11, 26)
    history = {"shown": {"https://old.example": "2026-10-01", "https://recent.example": "2026-11-20"}}
    build.save_history(path, history, ["https://new.example/"], today)
    shown = json.loads(path.read_text())["shown"]
    assert set(shown) == {"https://recent.example", "https://new.example"}


def test_frontend_topics_match_pipeline():
    js = (ROOT / "site" / "assets" / "app.js").read_text()
    block = re.search(r"const TOPICS = \{(.*?)\};", js, re.S).group(1)
    pairs = dict(re.findall(r'(\w+): "([^"]+)"', block))
    assert pairs == config.TOPICS


def test_empty_model_variable_uses_default(tmp_path, fake_sources, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("DD_MODEL", "")
    seen = {}

    def fake_claude(cands, model, client=None):
        seen["model"] = model
        raise curate.CurationError("stop here")

    monkeypatch.setattr(curate, "ask_claude", fake_claude)
    assert build.main(["--out", str(tmp_path / "d"), "--history", str(tmp_path / "h.json")]) == 0
    assert seen["model"] == config.DEFAULT_MODEL
