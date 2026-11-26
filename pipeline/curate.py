"""Ask Claude to pick and explain today's reads.

Claude only returns candidate ids, never URLs, so every link on the page comes from
the collected data and cannot be invented.
"""

from __future__ import annotations

import json
import logging

import anthropic

from . import config

log = logging.getLogger(__name__)

# Models that accept server-side refusal fallbacks (`fallbacks: "default"`).
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-2", "claude-fable-5-1"}

SYSTEM = f"""You are the editor of Daily Pull, a free web page that shows software engineers a few things worth reading each day. Readers choose topics and get only the best few items in those topics, so your job is to cut noise.

Topics (use these ids): {json.dumps(config.TOPICS)}

From the candidates, choose 30 to 50 items that are genuinely worth a busy engineer's time today. Good picks teach something, explain how a system really works, change how people should work, or are important to know about (major releases, security issues in widely used software, notable outages and postmortems, big shifts in tools). Prefer primary sources and deep technical write-ups. Skip hype, marketing, funding news, drama, listicles, vague opinion pieces, and near-duplicates of the same story (keep the best version). Aim for at least 4 picks per topic when the material allows, but never pad a topic with weak items.

For each pick:
- id: the candidate id, exactly as given.
- title: a clear, plain title. Remove clickbait. Keep it close to the original meaning.
- why: one or two sentences, max 220 characters, on what the reader will learn or why it matters. Be concrete. Do not start with "This article".
- topics: 1 to 3 topic ids, most relevant first.
- minutes: honest reading time estimate in whole minutes.
- kind: one of {", ".join(config.KINDS)}.
- score: 1 to 10, how strongly you recommend it today. Reserve 9 and 10 for things most engineers in that topic should read.

Also write a headline: one plain sentence, max 120 characters, naming the most important thing in today's material.

Write in plain English. Never use em dashes or en dashes."""

SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "picks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "why": {"type": "string"},
                    "topics": {"type": "array", "items": {"type": "string", "enum": list(config.TOPICS)}},
                    "minutes": {"type": "integer"},
                    "kind": {"type": "string", "enum": config.KINDS},
                    "score": {"type": "integer"},
                },
                "required": ["id", "title", "why", "topics", "minutes", "kind", "score"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["headline", "picks"],
    "additionalProperties": False,
}


class CurationError(RuntimeError):
    pass


def prompt_payload(cands: list[dict]) -> str:
    rows = []
    for c in cands:
        row = {"id": c["cid"], "source": c["source"], "title": c["title"]}
        if c["text"]:
            row["text"] = c["text"][:280]
        if c["points"]:
            row["points"] = c["points"]
        if c["comments"]:
            row["comments"] = c["comments"]
        if c["hints"]:
            row["source_topics"] = c["hints"]
        if c.get("language"):
            row["language"] = c["language"]
        rows.append(json.dumps(row, ensure_ascii=False))
    return "Candidates, one JSON object per line:\n" + "\n".join(rows)


def _request(client: anthropic.Anthropic, model: str, payload: str, use_fallbacks: bool):
    kwargs = dict(
        model=model,
        max_tokens=16000,
        system=SYSTEM,
        messages=[{"role": "user", "content": payload}],
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
    )
    if use_fallbacks:
        return client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
    return client.messages.create(**kwargs)


def ask_claude(cands: list[dict], model: str = config.DEFAULT_MODEL, client: anthropic.Anthropic | None = None) -> dict:
    client = client or anthropic.Anthropic(max_retries=3, timeout=600)
    payload = prompt_payload(cands)
    use_fallbacks = model in FALLBACK_MODELS
    try:
        resp = _request(client, model, payload, use_fallbacks)
    except anthropic.BadRequestError as exc:
        if not use_fallbacks:
            raise CurationError(f"bad request: {exc.message}") from exc
        log.warning("request with fallbacks rejected (%s), retrying without", exc.message)
        resp = _request(client, model, payload, False)
    except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
        raise CurationError(f"{type(exc).__name__}: {exc}") from exc

    if resp.stop_reason != "end_turn":
        raise CurationError(f"unexpected stop_reason {resp.stop_reason}")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CurationError("model output was not valid JSON") from exc
    log.info("claude picked %d items (model %s, request %s)", len(result.get("picks", [])), resp.model,
             getattr(resp, "_request_id", "?"))
    return result


def validate(result: dict, by_id: dict[str, dict]) -> dict:
    """Drop anything that does not point at a real candidate, clamp numbers, normalize fields."""
    picks, seen = [], set()
    for p in result.get("picks", []):
        cid = str(p.get("id", ""))
        if cid not in by_id or cid in seen:
            continue
        topics = [t for t in dict.fromkeys(p.get("topics") or []) if t in config.TOPICS][:3]
        if not topics:
            continue
        seen.add(cid)
        picks.append({
            "id": cid,
            "title": (p.get("title") or by_id[cid]["title"]).strip()[:200],
            "why": (p.get("why") or "").strip()[:300],
            "topics": topics,
            "minutes": max(1, min(60, int(p.get("minutes") or 5))),
            "kind": p.get("kind") if p.get("kind") in config.KINDS else by_id[cid]["kind"],
            "score": max(1, min(10, int(p.get("score") or 5))),
        })
    return {"headline": (result.get("headline") or "").strip()[:160], "picks": picks}
