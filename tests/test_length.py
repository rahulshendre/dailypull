import asyncio

import httpx

from pipeline import config, length


def words(n, word="word"):
    return " ".join([word] * n)


def page(article="", nav="", main=None, extra=""):
    body = f"<nav>{nav}</nav>"
    if main is not None:
        body += f"<main>{main}</main>"
    if article:
        body += f"<article>{article}</article>"
    return f"<!doctype html><html><head><title>t</title><style>p {{ color: red }}</style></head>" \
           f"<body class='single has-sidebar'>{body}{extra}<footer>{words(50)}</footer></body></html>"


def test_counts_the_article_not_the_page_furniture():
    html = page(article=f"<h1>Title</h1><p>{words(460)}</p><script>{words(900)}</script>",
                nav=words(300), extra=f"<aside>{words(300)}</aside>")
    assert length.count_words(html) == 461


def test_comments_and_share_bars_inside_the_article_are_left_out():
    html = page(article=f"<p>{words(460)}</p><div class='share-bar'>{words(40)}</div>"
                        f"<section id='comments'><p>{words(2000)}</p></section>"
                        f"<div class='post-content'>{words(10)}</div>")
    assert length.count_words(html) == 470


def test_falls_back_to_main_then_to_the_body():
    assert length.count_words(page(main=f"<p>{words(500)}</p>", nav=words(100))) == 500
    # A plain page with no <article> or <main>: the whole body, minus nav and footer.
    assert length.count_words(page(extra=f"<p>{words(690)}</p>", nav=words(100))) == 690


def test_a_thin_article_is_not_padded_with_the_rest_of_the_page():
    html = page(article=f"<p>{words(120)}</p><p>Subscribe to keep reading.</p>", extra=f"<div>{words(900)}</div>")
    assert length.reading_minutes(html) is None


def test_tolerates_broken_html():
    html = f"<body><article><p>{words(300)}<div><span>{words(160)}</article></p></body>"
    assert length.count_words(html) == 460


def test_reading_minutes_rounds_and_refuses_thin_pages():
    assert length.reading_minutes(page(article=words(config.WORDS_PER_MINUTE * 7))) == 7
    assert length.reading_minutes(page(article=words(config.MIN_ARTICLE_WORDS))) == 1
    # A login wall or a page drawn by JavaScript: no time rather than a wrong one.
    assert length.reading_minutes(page(article=words(config.MIN_ARTICLE_WORDS - 1))) is None


def test_measure_fetches_articles_only_and_skips_failures():
    long_page = page(article=words(config.WORDS_PER_MINUTE * 5))
    seen = []

    def handler(request):
        seen.append(str(request.url))
        path = request.url.path
        if path == "/good":
            return httpx.Response(200, html=long_page)
        if path == "/moved":
            return httpx.Response(301, headers={"Location": "https://example.com/good"})
        if path == "/pdf":
            return httpx.Response(200, content=b"%PDF", headers={"content-type": "application/pdf"})
        if path == "/thin":
            return httpx.Response(200, html=page(article="Please enable JavaScript."))
        if path == "/boom":
            raise httpx.ConnectError("refused")
        return httpx.Response(404)

    items = [{"url": "https://example.com/good", "kind": "article"},
             {"url": "https://example.com/moved", "kind": "article"},
             {"url": "https://example.com/pdf", "kind": "article"},
             {"url": "https://example.com/thin", "kind": "article"},
             {"url": "https://example.com/boom", "kind": "article"},
             {"url": "https://example.com/gone", "kind": "article"},
             {"url": "https://example.com/good", "kind": "article"},
             {"url": "https://github.com/a/b", "kind": "repo"},
             {"url": "https://arxiv.org/abs/1", "kind": "paper"}]
    got = asyncio.run(length.measure(items, transport=httpx.MockTransport(handler)))
    assert got == {"https://example.com/good": 5, "https://example.com/moved": 5}
    assert not any("github.com" in u or "arxiv.org" in u for u in seen)
    assert seen.count("https://example.com/good") == 2  # once itself, once through the redirect
