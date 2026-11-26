"""Build today's reading list: collect, pick, write site/data/today.json.

Usage:
  python -m pipeline.build [--out site/data] [--history .cache/history.json] [--no-ai]

Environment:
  ANTHROPIC_API_KEY   enables the Claude picker (otherwise the free ranking is used)
  DP_MODEL            Claude model id, default claude-opus-5-5
  REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET   optional, adds Reddit
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import hashlib
import json
import logging
import os
import re
import sys
from pathlib import Path

from . import config, curate, rank, sources

log = logging.getLogger("dailypull")

URL_RE = re.compile(r"https?://\S+")
BOILERPLATE_RE = re.compile(r"continue reading on [^»]*»|read on the web|view on \S+", re.IGNORECASE)


def short_id(url: str) -> str:
    return hashlib.sha1(sources.normalize_url(url).encode()).hexdigest()[:10]


def excerpt(cand: dict, limit: int = 200) -> str:
    """Description for the free ranking: the feed text without links or boilerplate, cut at a word."""
    if cand.get("kind") == "newsletter":
        return ""  # issue intros are sponsor and table-of-contents text
    text = BOILERPLATE_RE.sub(" ", URL_RE.sub(" ", cand.get("text") or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) < 40:
        return ""
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return text


def next_refresh(now: dt.datetime) -> dt.datetime:
    hour, minute = config.REFRESH_UTC
    nxt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return nxt if nxt > now else nxt + dt.timedelta(days=1)


def load_history(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data.get("shown"), dict) else {"shown": {}}
    except (FileNotFoundError, json.JSONDecodeError, AttributeError):
        return {"shown": {}}


def save_history(path: Path, history: dict, picked_urls: list[str], today: dt.date) -> None:
    shown = history["shown"]
    for url in picked_urls:
        shown[sources.normalize_url(url)] = today.isoformat()
    cutoff = (today - dt.timedelta(days=config.HISTORY_DAYS)).isoformat()
    history["shown"] = {u: d for u, d in shown.items() if d >= cutoff}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, indent=0, sort_keys=True))


def prepare(cands: list[dict], history: dict) -> list[dict]:
    """Dedupe, drop recently shown links, trim to the best MAX_CANDIDATES, assign ids."""
    shown = history.get("shown", {})
    fresh = [c for c in sources.dedupe(cands) if sources.normalize_url(c["url"]) not in shown]
    trimmed = rank.trim(fresh)
    for c in trimmed:
        c["cid"] = short_id(c["url"])
    return trimmed


def pick(cands: list[dict], use_ai: bool, model: str) -> tuple[dict, str]:
    by_id = {c["cid"]: c for c in cands}
    if use_ai:
        try:
            result = curate.validate(curate.ask_claude(cands, model=model), by_id)
            if len(result["picks"]) >= 10:
                return result, model
            log.warning("claude returned only %d usable picks, using ranking", len(result["picks"]))
        except curate.CurationError as exc:
            log.warning("claude picker failed, using ranking: %s", exc)
    return rank.rank_fallback(cands), "ranking"


def assemble(result: dict, curated_by: str, cands: list[dict], status: dict, now: dt.datetime) -> dict:
    by_id = {c["cid"]: c for c in cands}
    picks = []
    for p in result["picks"]:
        c = by_id[p["id"]]
        item = {
            "id": p["id"],
            "title": p["title"],
            "url": c["url"],
            "source": c["source"],
            "why": p["why"] or (excerpt(c) if curated_by == "ranking" else ""),
            "topics": p["topics"],
            "minutes": p["minutes"],
            "kind": p["kind"],
            "score": p["score"],
        }
        if c.get("discussion") and c["discussion"] != c["url"]:
            item["discussion"] = c["discussion"]
        picks.append(item)
    picks.sort(key=lambda x: -x["score"])
    ok_sources = sorted(k for k, v in status.items() if v.startswith("ok"))
    return {
        "version": 1,
        "date": now.date().isoformat(),
        "generated_at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "next_refresh_at": next_refresh(now).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "curated_by": curated_by,
        "headline": result.get("headline", ""),
        "considered": len(cands),
        "source_count": len(ok_sources),
        "topics": config.TOPICS,
        "picks": picks,
    }


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="site/data", type=Path)
    ap.add_argument("--history", default=".cache/history.json", type=Path)
    ap.add_argument("--no-ai", action="store_true", help="skip Claude even if a key is set")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    now = dt.datetime.now(dt.timezone.utc)
    raw, status = asyncio.run(sources.gather_all())
    for name, s in sorted(status.items()):
        log.info("source %-28s %s", name, s)

    history = load_history(args.history)
    cands = prepare(raw, history)
    log.info("%d raw items, %d candidates after dedupe and history", len(raw), len(cands))
    if len(cands) < config.MIN_CANDIDATES:
        log.error("only %d candidates (need %d): sources look broken, not publishing", len(cands),
                  config.MIN_CANDIDATES)
        return 2

    use_ai = bool(os.environ.get("ANTHROPIC_API_KEY")) and not args.no_ai
    # CI passes unset variables as empty strings, so fall back on "" too.
    result, curated_by = pick(cands, use_ai, os.environ.get("DP_MODEL") or config.DEFAULT_MODEL)
    doc = assemble(result, curated_by, cands, status, now)

    write_json(args.out / "today.json", doc)
    save_history(args.history, history, [p["url"] for p in doc["picks"]], now.date())
    log.info("wrote %d picks (%s) to %s", len(doc["picks"]), curated_by, args.out / "today.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
