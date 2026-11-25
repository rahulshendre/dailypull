"""Browser tests for the reader page. Run with a real Chromium through Playwright.

Locally, PW_CHANNEL=chrome uses the installed Google Chrome instead of a downloaded browser.
"""

import datetime as dt
import functools
import http.server
import json
import os
import shutil
import socketserver
import threading
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

SITE = Path(__file__).resolve().parent.parent / "site"
TOPICS = {
    "ai": "AI and coding agents", "web": "Web and frontend", "backend": "Backend and databases",
    "devops": "DevOps and SRE", "cloud": "Kubernetes and cloud native", "security": "Security",
    "systems": "Linux and systems", "languages": "Programming languages", "oss": "Open source",
    "career": "Career and craft",
}


def iso(t):
    return t.isoformat(timespec="seconds").replace("+00:00", "Z")


def make_data(next_refresh_hours=6.0):
    now = dt.datetime.now(dt.timezone.utc)
    picks = []
    for n in range(6):
        picks.append({"id": f"ai{n}", "title": f"AI read {n}", "url": f"https://example.com/ai/{n}",
                      "source": "Hacker News", "why": f"Why AI {n}.", "topics": ["ai"], "minutes": 5,
                      "kind": "article", "score": 9 - n, "discussion": f"https://news.ycombinator.com/item?id={n}"})
    for n in range(2):
        picks.append({"id": f"ops{n}", "title": f"Ops read {n}", "url": f"https://example.com/ops/{n}",
                      "source": "SRE Weekly", "why": "", "topics": ["devops"], "minutes": 7,
                      "kind": "newsletter", "score": 6})
    picks.append({"id": "evil", "title": "Evil link", "url": "javascript:alert(1)", "source": "X",
                  "why": "", "topics": ["ai"], "minutes": 1, "kind": "article", "score": 10})
    picks.append({"id": "vid", "title": "A video", "url": "https://youtube.com/watch?v=1", "source": "Fireship",
                  "why": "", "topics": ["web"], "minutes": 9, "kind": "video", "score": 5})
    return {"version": 1, "date": now.date().isoformat(), "generated_at": iso(now),
            "next_refresh_at": iso(now + dt.timedelta(hours=next_refresh_hours)), "curated_by": "claude-opus-5-5",
            "headline": "The headline of the day.", "considered": 300, "source_count": 80, "topics": TOPICS,
            "picks": picks}


class Server:
    def __init__(self, root: Path):
        handler = functools.partial(_QuietHandler, directory=str(root))
        self.httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as p:
        try:
            b = p.chromium.launch(channel=os.environ.get("PW_CHANNEL") or None)
        except Exception as exc:  # no browser installed: skip instead of failing the unit suite
            pytest.skip(f"no browser available: {exc}")
        yield b
        b.close()


@pytest.fixture
def site(tmp_path):
    root = tmp_path / "site"
    shutil.copytree(SITE, root, ignore=shutil.ignore_patterns("data"))
    (root / "data").mkdir()

    def write(data):
        (root / "data" / "today.json").write_text(json.dumps(data))

    write(make_data())
    server = Server(root)
    server.write = write
    server.root = root
    yield server
    server.close()


@pytest.fixture
def page(browser, site):
    ctx = browser.new_context(viewport={"width": 1100, "height": 900})
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.on("console", lambda m: pg.errors.append(m.text) if m.type == "error" else None)
    yield pg
    ctx.close()


def setup(page, topics=("AI and coding agents",), amount="3"):
    for t in topics:
        page.click(f"label.topic:has-text('{t}')")
    page.click(f"#amount label:has-text('{amount}')")
    page.click("#setup-save")
    page.wait_for_selector("#view-today:not([hidden])")


def titles(page):
    return page.locator("#reads .read h2 a").all_inner_texts()


def test_first_visit_asks_for_topics_and_validates(page, site):
    page.goto(site.url)
    page.wait_for_selector("#view-setup:not([hidden])")
    assert page.locator("label.topic").count() == len(TOPICS)
    page.click("#setup-save")
    assert page.locator("#setup-error").is_visible()
    page.click("label.topic:has-text('Security')")
    assert page.locator("#setup-error").is_hidden()
    assert page.errors == []


def test_shows_best_reads_for_chosen_topics(page, site):
    page.goto(site.url)
    setup(page)
    assert titles(page) == ["AI read 0", "AI read 1", "AI read 2"]
    assert page.inner_text("#stat-add") == "+3"
    assert page.inner_text("#stat-del") == "-297"
    assert page.inner_text("#headline") == "The headline of the day."
    link = page.locator("#reads .read h2 a").first
    assert link.get_attribute("target") == "_blank"
    assert "noopener" in link.get_attribute("rel")
    assert page.locator("#reads .meta a:has-text('Discussion')").count() == 3
    assert "Picked by Claude from 80 sources" in page.inner_text("#foot-sources")
    assert page.errors == []


def test_unsafe_links_are_never_rendered(page, site):
    page.goto(site.url)
    setup(page, amount="5")
    assert "Evil link" not in titles(page)
    assert page.locator("a[href^='javascript']").count() == 0


def test_read_state_persists_and_done_message_appears(page, site):
    page.goto(site.url)
    setup(page, amount="1")
    page.click("#reads .tick")
    page.wait_for_function("document.querySelector('#reads .tick').getAttribute('aria-pressed') === 'true'")
    assert page.locator("#done").is_visible()
    assert page.inner_text("#done").startswith("That's today. New list in")
    page.reload()
    page.wait_for_selector("#view-today:not([hidden])")
    assert page.locator("#reads .read").first.get_attribute("class") == "read is-read"


def test_opening_a_link_marks_it_read(page, site):
    page.goto(site.url)
    setup(page, amount="1")
    with page.context.expect_page() as popup:
        page.click("#reads .read h2 a")
    popup.value.close()
    assert page.locator("#reads .tick").first.get_attribute("aria-pressed") == "true"


def test_show_more_adds_the_next_batch(page, site):
    page.goto(site.url)
    setup(page)
    page.click("#more")
    assert titles(page) == [f"AI read {n}" for n in range(6)]
    assert page.locator("#more").is_hidden()


def test_change_topics_and_cancel(page, site):
    page.goto(site.url)
    setup(page)
    page.click("#edit-topics")
    page.wait_for_selector("#view-setup:not([hidden])")
    assert page.inner_text("#setup-save") == "Save topics"
    page.click("#setup-cancel")
    page.wait_for_selector("#view-today:not([hidden])")
    page.click("#edit-topics")
    page.click("label.topic:has-text('AI and coding agents')")
    page.click("label.topic:has-text('DevOps and SRE')")
    page.click("#setup-save")
    page.wait_for_selector("#view-today:not([hidden])")
    assert titles(page) == ["Ops read 0", "Ops read 1"]


def test_empty_topics_offer_everything(page, site):
    page.goto(site.url)
    setup(page, topics=("Career and craft",))
    assert page.locator("#empty").is_visible()
    page.click("#empty-all")
    assert len(titles(page)) == 3
    assert page.locator("#notice").is_visible()


def test_video_shows_watch_time(page, site):
    page.goto(site.url)
    setup(page, topics=("Web and frontend",))
    assert "9 min watch" in page.inner_text("#reads .meta")


def test_error_state_and_retry(page, site):
    (site.root / "data" / "today.json").unlink()
    page.goto(site.url)
    page.click("label.topic:has-text('AI and coding agents')")
    page.click("#setup-save")
    page.wait_for_selector("#view-error:not([hidden])")
    site.write(make_data())
    page.click("#retry")
    page.wait_for_selector("#view-today:not([hidden])")
    assert len(titles(page)) == 3


def test_late_list_shows_a_notice(page, site):
    site.write(make_data(next_refresh_hours=-5))
    page.goto(site.url)
    setup(page)
    assert "running late" in page.inner_text("#notice")


def test_keyboard_shortcuts(page, site):
    page.goto(site.url)
    setup(page)
    page.keyboard.press("j")
    page.keyboard.press("j")
    page.keyboard.press("x")
    ticks = page.locator("#reads .tick")
    assert ticks.nth(1).get_attribute("aria-pressed") == "true"
    assert ticks.nth(0).get_attribute("aria-pressed") == "false"


def test_storage_blocked_still_works(browser, site):
    ctx = browser.new_context()
    ctx.add_init_script("Object.defineProperty(window, 'localStorage', { get() { throw new Error('blocked'); } });")
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(site.url)
    setup(pg)
    pg.click("#reads .tick")
    assert pg.locator("#reads .tick").first.get_attribute("aria-pressed") == "true"
    assert errors == []
    ctx.close()


def test_mobile_layout_has_no_horizontal_scroll(browser, site):
    ctx = browser.new_context(viewport={"width": 360, "height": 740})
    pg = ctx.new_page()
    pg.goto(site.url)
    setup(pg)
    assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    ctx.close()
