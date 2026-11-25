# Daily Diff

A web page that refreshes once a day and shows engineers a few things worth reading in the topics they pick. No login, no email, no newsletter, no app, no feed to scroll.

```
+3 -278
3 reads for you today. 278 other posts skipped.
```

## How it works

```
 85 public sources                  once a day (GitHub Actions, 00:30 UTC)              any static host
 ───────────────────                ───────────────────────────────────────              ───────────────
 Hacker News, Lobsters,             pipeline/build.py                                    site/
 GitHub Trending, DEV,      ──▶     1. fetch everything (sources.py)          ──▶        index.html + app.js
 Mastodon trending links,           2. dedupe, drop links shown in 14 days               data/today.json
 Medium, Substack, YouTube,         3. Claude picks 30 to 50 and says why (curate.py)
 Reddit (optional),                    or free ranking if no key / on failure (rank.py)
 78 blog, newsletter and            4. write site/data/today.json
 news feeds
```

- **The page** (`site/`) is plain HTML, CSS and JavaScript with no build step and no third-party requests. On first visit it asks which topics you want and how many reads a day (1, 3 or 5). It then shows the best picks in those topics, sorted by score. Topics and read state live in `localStorage`, nothing leaves the browser.
- **The picker** sends Claude only candidate ids, titles and short excerpts, never URLs, and keeps only answers that point at real candidates. So every link on the page comes from the collected data.
- **Quality first:** noisy sources (Medium tag feeds, general tech news) start with a lower score, curated blogs higher, aggregators by votes. Claude is told to cut hype, marketing and duplicates, and never to pad a topic.
- **Safe to fail:** if fewer than 40 candidates come back, the build exits with an error and nothing is published, so yesterday's page stays up. If Claude fails, the free ranking is used.

## Run it locally

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt

python -m pipeline.build --no-ai          # free ranking
ANTHROPIC_API_KEY=... python -m pipeline.build   # Claude picks

python -m http.server -d site 8000        # open http://localhost:8000
```

## Configuration

Set these on the repo (Settings > Secrets and variables > Actions). All are optional.

| Name | Type | What it does |
|---|---|---|
| `ANTHROPIC_API_KEY` | secret | Turns on the Claude picker. Without it the free ranking is used. |
| `DD_MODEL` | variable | Claude model id. Default `claude-opus-5-5` (about $0.30 a day). |
| `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` | secrets | Adds 16 subreddits through Reddit's official API. Create a "script" app at reddit.com/prefs/apps. Reddit blocks anonymous access. |
| `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` | secrets | Turns on the deploy step in the daily workflow. |

From a terminal: `gh secret set ANTHROPIC_API_KEY` (it prompts for the value, so it never lands in shell history).

## Deploy

Nothing is deployed yet. The daily workflow builds the site and uploads it as an artifact named `site`. To go live, pick one:

- **Vercel:** create a project, then add the three `VERCEL_*` secrets. Security headers come from `site/vercel.json`.
- **Netlify or Cloudflare Pages:** publish the `site/` folder from the workflow. Headers come from `site/_headers`.
- **GitHub Pages:** needs a public repo or a paid plan for private ones.

Run the workflow by hand from the Actions tab (Daily build > Run workflow) to get the first list.

## Sources

All in `pipeline/config.py`. To add a blog: add `(name, feed_url, [topics], prior, kind)` to `FEEDS`. `prior` (0 to 10, default 6) is where its posts start before Claude judges them. Use 3 to 4 for firehoses. `tests/test_sources.py` checks every entry is well formed.

## Tests

```bash
python -m pytest                     # unit and browser tests
PW_CHANNEL=chrome python -m pytest   # use installed Chrome instead of a downloaded Chromium
```

The browser tests cover first-visit setup, topic filtering, read state across reloads, show more, changing topics, the empty, error and late states, keyboard shortcuts, blocked storage, unsafe links, and mobile overflow.
