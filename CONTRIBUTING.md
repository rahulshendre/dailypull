# Contributing

Thanks for helping. Daily Pull stays useful only if its sources are good and its page stays small, so changes are judged by one question: does this make the daily list better or quieter?

## Suggest a source

Open an issue with:

- the name and the feed URL (RSS or Atom),
- which topics it covers (see `TOPICS` in `pipeline/config.py`),
- two or three recent posts that show why engineers should read it.

Good sources post rarely and well, or are curated by a person. Company marketing, SEO content and general news are usually turned down.

## Report a bad pick

If something on the page should not have been there (spam, an ad, politics, a dead link, the wrong topic), open an issue with the link and the date. Most fixes are a rule in `pipeline/config.py`.

## Code changes

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest
```

- Keep the page dependency-free: no frameworks, no build step, no third-party requests.
- Keep ranking free of AI models. Scores come from people: votes, editors and agreement.
- Add or update tests with every change. Source parsers are tested against saved fixtures in `tests/fixtures/`, never live sites.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/), for example `feat(sources): add the Lobsters RSS feed`.
