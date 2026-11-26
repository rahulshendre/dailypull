import time

from pipeline import config, rank, sources


def cand(title="Some title here", source="Blog", points=0, comments=0, text="", hints=(), prior=None,
         editors=(), url=None, published=None):
    return sources.candidate(source, title, url or f"https://example.com/{abs(hash(title + source))}",
                             text=text, points=points, comments=comments, hints=hints, prior=prior,
                             editors=editors, published=published or time.time())


# ---------- topics ----------

def test_keyword_topics_match_whole_words_only():
    assert rank.keyword_topics("Running Kubernetes operators in production") == ["cloud"]
    assert "ai" in rank.keyword_topics("How AI agents write code")
    assert rank.keyword_topics("She said it was fine") == []


def test_a_single_body_word_does_not_set_a_topic():
    c = cand("Datacenters in space approved", text="with the deployment of 100,000 satellites")
    assert rank.topics_for(c) == []
    c = cand("Datacenters in space approved", text="deployment, incident, outage and on-call")
    assert rank.topics_for(c)[0] == "devops"


def test_title_beats_hints_and_ties_go_to_the_narrower_topic():
    assert rank.topics_for(cand("1Password security incident"))[0] == "security"
    assert rank.topics_for(cand("Rust compiler internals", hints=["web"])) == ["languages", "web"]


def test_hints_more_places_agree_on_come_first():
    a = cand("Ladybird first alpha", source="Simon", hints=["ai"], url="https://ladybird.org/a")
    b = cand("Ladybird first alpha", source="JS Weekly", hints=["web"], url="https://ladybird.org/a")
    c = cand("Ladybird first alpha", source="Frontend Focus", hints=["web"], url="https://ladybird.org/a")
    merged = sources.dedupe([a, b, c])[0]
    assert rank.topics_for(merged)[0] == "web"


def test_classic_topics_include_craft_essays():
    assert "career" in rank.classic_topics("Things every programmer should know about time")
    assert rank.classic_topics("Let's build a simple database") == ["backend"]


# ---------- filters ----------

def test_keep_drops_politics_hiring_and_non_english():
    assert rank.keep(cand("Postgres vacuum explained"))
    assert not rank.keep(cand("Trump signs order on AI"))
    assert not rank.keep(cand("Ask HN: Who is hiring? (December 2026)"))
    assert not rank.keep(cand("Como utilizar o DevOps Guidance para avaliar a maturidade das equipes"))
    assert not rank.keep(cand("Kubernetes 入門 ガイド のための 完全な チュートリアル"))
    assert rank.keep(cand("Leader election in Raft, step by step"))


# ---------- scores ----------

def test_votes_are_compared_within_each_site():
    hn = [cand(f"HN story {n}", source="Hacker News", points=p) for n, p in enumerate([100, 300, 900])]
    lob = [cand(f"Lobsters story {n}", source="Lobsters", points=p) for n, p in enumerate([5, 20, 60])]
    blog = cand("A blog post", prior=7.0)
    rank.base_scores(hn + lob + [blog])
    assert hn[2]["base"] == lob[2]["base"] == 9.0      # top of each site ties
    assert hn[0]["base"] == lob[0]["base"] == 4.0
    assert blog["base"] == 7.0


def test_agreement_between_places_adds_up():
    url = "https://example.com/same"
    copies = [cand("Same story", source="Hacker News", points=200, url=url),
              cand("Same story", source="Lobsters", points=30, url=url),
              cand("Same story", source="SRE Weekly", editors=["SRE Weekly"], prior=5.5, url=url)]
    rank.base_scores(copies)
    merged = sources.dedupe(copies)[0]
    assert merged["places"] == ["Hacker News", "Lobsters", "SRE Weekly"]
    alone = cand("Other story", source="Hacker News", points=200)
    rank.base_scores([alone])
    assert rank.score(merged) - rank.score(alone) >= 2 * config.AGREEMENT_BONUS - 0.01


def test_clickbait_and_flamewars_are_pushed_down():
    plain = cand("How we cut Postgres latency", source="Hacker News", points=300, comments=80)
    bait = cand("10 things every developer should know", source="Hacker News", points=300, comments=80)
    war = cand("Tabs are better than spaces", source="Hacker News", points=100, comments=400)
    rank.base_scores([plain, bait, war])
    assert rank.score(bait) < rank.score(plain)
    assert rank.score(war) < rank.score(plain)


def test_old_blog_posts_sink():
    now = time.time()
    fresh = cand("Fresh post", prior=7.0, published=now)
    old = cand("Old post", prior=7.0, published=now - 3 * 86400)
    rank.base_scores([fresh, old])
    assert rank.score(old, now) < rank.score(fresh, now)


def test_signals_say_why_in_plain_facts():
    url = "https://example.com/x"
    copies = [cand("X", source="Lobsters", points=88, url=url), cand("X", source="Hacker News", points=1412, url=url),
              cand("X", source="Golang Weekly", editors=["Golang Weekly"], url=url),
              cand("X", source="Postgres Weekly", editors=["Postgres Weekly"], url=url)]
    merged = sources.dedupe(copies)[0]
    assert rank.signals(merged) == ["1,412 points on Hacker News", "88 votes on Lobsters",
                                    "picked by Golang Weekly and Postgres Weekly"]
    assert rank.signals(cand("A blog post")) == []


# ---------- selection ----------

def test_select_caps_topics_and_varies_sources():
    cands = [cand(f"LLM agents part {n}", source="Hacker News", points=500 - n) for n in range(10)]
    cands += [cand(f"Ransomware report {n}", source="Krebs", prior=6.0) for n in range(2)]
    cands += [cand(f"Rust compiler notes {n}", source="Lobsters", points=40) for n in range(3)]
    rank.base_scores(cands)
    for c in cands:
        c["score"] = rank.score(c)
    picks = rank.select(cands, per_topic=3)
    firsts = [p["topics"][0] for p in picks]
    assert firsts.count("ai") == 3 and firsts.count("security") == 2 and firsts.count("languages") == 3
    scores = [p["score"] for p in picks]
    assert scores == sorted(scores, reverse=True)
    assert [p["cand"]["source"] for p in picks[:3]] != ["Hacker News"] * 3


def test_select_skips_items_without_a_topic():
    c = cand("Cornwall market news")
    c["base"], c["score"] = 9.0, 9.0
    assert rank.select([c]) == []
