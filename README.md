# Daily Pull

A web page that refreshes once a day and shows engineers a few things worth reading in the topics they pick. Ranked by people, not AI. No login, no email, no newsletter, no app, no feed to scroll.

## How it works

```
 public sources                     once a day (GitHub Actions, 00:30 UTC)           any static host
 ──────────────                     ──────────────────────────────────────           ───────────────
 Hacker News, Lobsters,             pipeline/build.py                                site/
 GitHub Trending, DEV, Mastodon     1. fetch everything (sources.py)        ──▶      index.html + app.js
 10 newsletter editors      ──▶     2. score: votes per site, agreement,             data/today.json
 70+ blogs and news feeds              noise rules (rank.py)
 Reddit (optional)                  3. pick a varied list, 6 per topic at most
 Hacker News reposts (classics)     4. one classic per topic (classics.py)
                                    5. write site/data/today.json
```

**How a link earns its place.** No model decides anything; every score comes from people:

- **Votes, compared within each site.** A story is ranked against the other stories on its own site that day, so the top of Lobsters ties with the top of Hacker News. Hacker News stories come from the last 48 hours with at least 60 points: reads that held up, not what is on top this minute.
- **Agreement.** The same link on Hacker News and Lobsters, or in two newsletters, or on an expert's blog and Hacker News, gets a bonus for every extra independent place.
- **Editors' picks.** Every link in the latest issue of hand-curated newsletters (SRE Weekly, Golang Weekly, This Week in Rust, PyCoder's Weekly, Import AI and others) counts as a vote from a human editor. Sponsor blocks and click trackers are stripped.
- **Expert blogs** (Julia Evans, Dan Luu, Brendan Gregg, Charity Majors and others) start high because they post rarely and well. Company marketing and firehoses (Medium tags, general news) start low.
- **Noise rules.** Politics, hiring threads and non-English posts are dropped. Clickbait titles and flame wars (far more comments than votes) are pushed down. Old blog posts slowly sink. Each extra pick from the same source costs a little, so no single site floods the list.

**Each read says why it is there** in plain facts: "1,285 points on Hacker News, 38 votes on Lobsters, picked by SRE Weekly".

**One classic a day.** On Hacker News, a repost of an old article gets its year in the title, like "Choose Boring Technology (2015)". If people still upvote it years later, it held up. The build collects those (about 6,000) and offers one per topic each day, each only once. Readers who take 3 or 5 reads a day get one classic among them.

**The page** (`site/`) is plain HTML, CSS and JavaScript with no build step and no third-party requests. On first visit it asks for topics and how many reads a day (1, 3 or 5). Topics and read state live in `localStorage`; nothing leaves the browser. The look is 1-bit: ink and paper only, dithered shading, one pixel font ([Departure Mono](https://departuremono.com), SIL Open Font License, see `site/assets/fonts/`).

**Safe to fail.** One broken source never stops the run. If fewer than 40 candidates come back, the build exits with an error and nothing is published, so yesterday's page stays up.

## Run it locally

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt

python -m pipeline.build                  # writes site/data/today.json (about a minute)
python -m http.server -d site 8000        # open http://localhost:8000
```

## Configuration

Nothing is required: no API keys. Optional repo secrets (Settings > Secrets and variables > Actions):

| Name | What it does |
|---|---|
| `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` | Adds 16 subreddits through Reddit's official API. Create a "script" app at reddit.com/prefs/apps. Reddit blocks anonymous access. |
| `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` | Turns on the deploy step in the daily workflow. |

## Deploy

Nothing is deployed yet. The daily workflow builds the site and uploads it as an artifact named `site`. To go live, pick one:

- **Vercel:** create a project, then add the three `VERCEL_*` secrets. Security headers come from `site/vercel.json`.
- **Netlify or Cloudflare Pages:** publish the `site/` folder from the workflow. Headers come from `site/_headers`.
- **GitHub Pages:** needs a public repo or a paid plan for private ones.

Run the workflow by hand from the Actions tab (Daily build > Run workflow) to get the first list.

## Sources and tuning

All in `pipeline/config.py`:

- `FEEDS`: blogs and news. Add `(name, feed_url, [topics], prior, kind)`. `prior` (0 to 10) is where its posts start: 7 for experts who post rarely, 3 to 4 for firehoses.
- `EDITORS`: curated newsletters whose links count as editors' picks.
- `VOTE_SCALE`, `AGREEMENT_BONUS`, penalties and the noise word lists: the whole ranking, in one place.

`tests/test_sources.py` checks every feed and editor entry is well formed.

## Tests

```bash
python -m pytest                     # unit and browser tests
PW_CHANNEL=chrome python -m pytest   # use installed Chrome instead of a downloaded Chromium
```

The unit tests cover parsing every source, editor-link extraction (sponsors, trackers, navigation), scoring, agreement, noise rules, topic tagging, selection, classics and the build. The browser tests cover first-visit setup, topic filtering, the classic slot, read state across reloads, show more, changing topics, the empty, error and late states, keyboard shortcuts, blocked storage, unsafe links and mobile overflow.
