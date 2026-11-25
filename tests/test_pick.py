import json
import time
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from pipeline import config, curate, rank, sources


def cand(cid, title="Title", text="", source="Blog", points=0, hints=(), kind="article", prior=None):
    c = sources.candidate(source, title, f"https://example.com/{cid}", text=text, points=points,
                          hints=hints, kind=kind, prior=prior, published=time.time())
    c["cid"] = cid
    return c


def test_keyword_topics_match_whole_words_only():
    assert rank.keyword_topics("Running Kubernetes operators in production") == ["cloud"]
    assert "ai" in rank.keyword_topics("How AI agents write code")
    assert rank.keyword_topics("She said it was fine") == []


def test_popularity_prefers_curated_blogs_over_firehose():
    blog = cand("a", source="Julia Evans")
    medium = cand("b", source="Medium", prior=3.0)
    assert rank.popularity(blog) > rank.popularity(medium)


def test_popularity_scales_with_votes():
    assert rank.popularity(cand("a", source="Hacker News", points=500)) > \
        rank.popularity(cand("b", source="Hacker News", points=20))


def test_rank_fallback_balances_topics():
    cands = [cand(f"ai{n}", title=f"LLM agents part {n}", source="Hacker News", points=500) for n in range(20)]
    cands += [cand(f"sec{n}", title=f"Ransomware report {n}", source="Hacker News", points=10) for n in range(2)]
    result = rank.rank_fallback(cands, per_topic=3)
    firsts = [p["topics"][0] for p in result["picks"]]
    assert firsts.count("ai") == 3
    assert firsts.count("security") == 2


def test_prompt_payload_sends_ids_not_urls():
    payload = curate.prompt_payload([cand("abc", title="Postgres internals", points=5, hints=["backend"])])
    row = json.loads(payload.splitlines()[1])
    assert row["id"] == "abc"
    assert "url" not in row


def test_validate_drops_unknown_duplicate_and_bad_values():
    by_id = {"a": cand("a"), "b": cand("b")}
    result = {"headline": "  Big day  ", "picks": [
        {"id": "a", "title": "A", "why": "w", "topics": ["ai", "nope", "ai"], "minutes": 500, "kind": "weird", "score": 99},
        {"id": "a", "title": "dup", "why": "", "topics": ["ai"], "minutes": 3, "kind": "article", "score": 5},
        {"id": "zzz", "title": "invented", "why": "", "topics": ["ai"], "minutes": 3, "kind": "article", "score": 5},
        {"id": "b", "title": "B", "why": "", "topics": [], "minutes": 3, "kind": "article", "score": 5},
    ]}
    out = curate.validate(result, by_id)
    assert out["headline"] == "Big day"
    assert len(out["picks"]) == 1
    pick = out["picks"][0]
    assert pick["topics"] == ["ai"]
    assert pick["minutes"] == 60
    assert pick["score"] == 10
    assert pick["kind"] == "article"


class FakeMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def fake_client(beta_responses=(), plain_responses=()):
    beta, plain = FakeMessages(beta_responses), FakeMessages(plain_responses)
    return SimpleNamespace(beta=SimpleNamespace(messages=beta), messages=plain), beta, plain


def response(text, stop_reason="end_turn"):
    return SimpleNamespace(stop_reason=stop_reason, model="claude-opus-5-5",
                           content=[SimpleNamespace(type="text", text=text)])


GOOD = json.dumps({"headline": "h", "picks": [
    {"id": "a", "title": "A", "why": "w", "topics": ["ai"], "minutes": 4, "kind": "article", "score": 8}]})


def test_ask_claude_uses_structured_output_and_fallbacks():
    client, beta, plain = fake_client(beta_responses=[response(GOOD)])
    result = curate.ask_claude([cand("a")], model="claude-opus-5-5", client=client)
    assert result["picks"][0]["id"] == "a"
    call = beta.calls[0]
    assert call["fallbacks"] == "default"
    assert call["betas"] == ["server-side-fallback-2026-07-01"]
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert call["output_config"]["effort"] == "medium"
    assert not plain.calls


def test_ask_claude_skips_fallbacks_for_models_without_them():
    client, beta, plain = fake_client(plain_responses=[response(GOOD)])
    curate.ask_claude([cand("a")], model="claude-haiku-5-5", client=client)
    assert plain.calls and not beta.calls
    assert "fallbacks" not in plain.calls[0]


def test_ask_claude_retries_without_fallbacks_when_rejected():
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    err = anthropic.BadRequestError("fallbacks not allowed", response=httpx.Response(400, request=req), body=None)
    client, beta, plain = fake_client(beta_responses=[err], plain_responses=[response(GOOD)])
    assert curate.ask_claude([cand("a")], client=client)["picks"]
    assert len(beta.calls) == 1 and len(plain.calls) == 1


@pytest.mark.parametrize("stop", ["refusal", "max_tokens"])
def test_ask_claude_raises_on_bad_stop_reason(stop):
    client, _, _ = fake_client(beta_responses=[response(GOOD, stop_reason=stop)])
    with pytest.raises(curate.CurationError):
        curate.ask_claude([cand("a")], client=client)


def test_ask_claude_wraps_api_errors():
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    err = anthropic.InternalServerError("boom", response=httpx.Response(500, request=req), body=None)
    client, _, _ = fake_client(beta_responses=[err])
    with pytest.raises(curate.CurationError):
        curate.ask_claude([cand("a")], client=client)


def test_schema_topics_and_kinds_match_config():
    item = curate.SCHEMA["properties"]["picks"]["items"]["properties"]
    assert item["topics"]["items"]["enum"] == list(config.TOPICS)
    assert item["kind"]["enum"] == config.KINDS
