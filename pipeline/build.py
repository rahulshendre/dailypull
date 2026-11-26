"""Build today's reading list: collect, rank, write site/data/today.json.

Usage:
  python -m pipeline.build [--out site/data] [--history .cache/history.json]

No AI and no keys are needed. Optional environment:
  REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET   adds Reddit through its official API
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import hashlib
import json
import logging
import re
import sys
import time
from pathlib import Path

from . import classics, config, rank, sources

log = logging.getLogger("dailypull")

URL_RE = re.compile(r"https?://\S+")
BOILERPLATE_RE = re.compile(r"continue reading on [^»]*»|read on the web|view on \S+", re.IGNORECASE)


def short_id(url: str) -> str:
    return hashlib.sha1(sources.normalize_url(url).encode()).hexdigest()[:10]


def excerpt(cand: dict, limit: int = 200) -> str:
    """A short description: the feed text without links or boilerplate, cut at a word."""
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


# ---------- history: what was already shown ----------

def load_history(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    return {key: data[key] if isinstance(data.get(key), dict) else {} for key in ("shown", "classics")}


def save_history(path: Path, history: dict, picked_urls: list[str], classic_urls: list[str],
                 today: dt.date) -> None:
    for key, urls, days in (("shown", picked_urls, config.HISTORY_DAYS),
                            ("classics", classic_urls, config.CLASSIC_HISTORY_DAYS)):
        seen = history[key]
        for url in urls:
            seen[sources.normalize_url(url)] = today.isoformat()
        cutoff = (today - dt.timedelta(days=days)).isoformat()
        history[key] = {u: d for u, d in seen.items() if d >= cutoff}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, indent=0, sort_keys=True))


# ---------- steps ----------

def prepare(raw: list[dict], history: dict, now: float | None = None) -> list[dict]:
    """Score per site, merge copies of the same link, drop noise and recently shown links,
    keep the best MAX_CANDIDATES, assign ids."""
    rank.base_scores(raw)
    shown = history.get("shown", {})
    merged = [c for c in sources.dedupe(raw)
              if rank.keep(c) and sources.normalize_url(c["url"]) not in shown]
    for c in merged:
        c["score"] = rank.score(c, now)
    best = sorted(merged, key=lambda c: -c["score"])[:config.MAX_CANDIDATES]
    for c in best:
        c["cid"] = short_id(c["url"])
    return best


def pick_item(sel: dict) -> dict:
    c = sel["cand"]
    item = {
        "id": c["cid"],
        "title": c["title"],
        "url": c["url"],
        "domain": sources.host_of(c["url"]),
        "source": c["source"],
        "signals": rank.signals(c),
        "excerpt": excerpt(c),
        "topics": sel["topics"],
        "minutes": rank.estimate_minutes(c),
        "kind": c["kind"],
        "score": sel["score"],
    }
    if c.get("discussion") and c["discussion"] != c["url"]:
        item["discussion"] = c["discussion"]
    return item


def classic_item(c: dict) -> dict:
    if c.get("reposts", 1) > 1:
        signal = f"posted to Hacker News {c['reposts']} times, {c['total']:,} points in all"
    else:
        signal = f"{c['points']:,} points on Hacker News" + (f" in {c['posted']}" if c.get("posted") else "")
    return {
        "id": short_id(c["url"]),
        "title": c["title"],
        "url": c["url"],
        "domain": sources.host_of(c["url"]),
        "year": c["year"],
        "signals": [signal],
        "topics": c["topics"],
        "minutes": 10 if c["kind"] == "paper" else 8,
        "kind": c["kind"],
        "discussion": c["discussion"],
    }


def assemble(selected: list[dict], classic_picks: list[dict], considered: int, status: dict,
             now: dt.datetime) -> dict:
    ok_sources = sorted(k for k, v in status.items() if v.startswith("ok"))
    return {
        "version": 2,
        "date": now.date().isoformat(),
        "generated_at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "next_refresh_at": next_refresh(now).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "considered": considered,
        "source_count": len(ok_sources),
        "topics": config.TOPICS,
        "picks": [pick_item(s) for s in selected],
        "classics": [classic_item(c) for c in classic_picks],
    }


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    tmp.replace(path)


async def collect() -> tuple[list[dict], dict, list[dict]]:
    (raw, status), (old, classic_status) = await asyncio.gather(sources.gather_all(), classics.gather())
    return raw, {**status, **classic_status}, old


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="site/data", type=Path)
    ap.add_argument("--history", default=".cache/history.json", type=Path)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    now = dt.datetime.now(dt.timezone.utc)
    raw, status, old = asyncio.run(collect())
    for name, s in sorted(status.items()):
        log.info("source %-28s %s", name, s)

    history = load_history(args.history)
    cands = prepare(raw, history, time.time())
    log.info("%d raw items, %d candidates after dedupe, filters and history", len(raw), len(cands))
    if len(cands) < config.MIN_CANDIDATES:
        log.error("only %d candidates (need %d): sources look broken, not publishing", len(cands),
                  config.MIN_CANDIDATES)
        return 2

    selected = rank.select(cands)
    classic_picks = classics.pick(old, history["classics"])
    doc = assemble(selected, classic_picks, len(cands), status, now)

    write_json(args.out / "today.json", doc)
    save_history(args.history, history, [p["url"] for p in doc["picks"]], [c["url"] for c in doc["classics"]],
                 now.date())
    log.info("wrote %d picks and %d classics to %s", len(doc["picks"]), len(doc["classics"]),
             args.out / "today.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
