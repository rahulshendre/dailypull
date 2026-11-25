"use strict";

(() => {
  // Keep in sync with pipeline/config.py TOPICS (a test checks this).
  const TOPICS = {
    ai: "AI and coding agents",
    web: "Web and frontend",
    backend: "Backend and databases",
    devops: "DevOps and SRE",
    cloud: "Kubernetes and cloud native",
    security: "Security",
    systems: "Linux and systems",
    languages: "Programming languages",
    oss: "Open source",
    career: "Career and craft",
  };
  const AMOUNTS = [1, 3, 5];
  const DEFAULT_AMOUNT = 3;
  const PREFS_KEY = "dd.prefs.v1";
  const READ_KEY = "dd.read.v1";
  const DATA_URL = "data/today.json";
  const LATE_AFTER_MS = 3 * 60 * 60 * 1000;
  const KEEP_READ_MS = 30 * 24 * 60 * 60 * 1000;
  const BAR_CELLS = 24;

  const $ = (id) => document.getElementById(id);
  const VIEWS = ["loading", "error", "setup", "today"];

  // Storage that keeps working in memory when localStorage is blocked or full.
  const store = {
    get(key, fallback) {
      try {
        const raw = localStorage.getItem(key);
        return raw === null ? fallback : JSON.parse(raw);
      } catch {
        return fallback;
      }
    },
    set(key, value) {
      try {
        localStorage.setItem(key, JSON.stringify(value));
      } catch {
        /* private mode or quota: state still lives in memory for this visit */
      }
    },
  };

  let prefs = loadPrefs();
  let readMap = loadRead();
  let data = null;
  let extra = 0;
  let showAll = false;

  function loadPrefs() {
    const p = store.get(PREFS_KEY, null);
    if (!p || !Array.isArray(p.topics)) return null;
    const topics = p.topics.filter((t) => Object.hasOwn(TOPICS, t));
    if (!topics.length) return null;
    return { topics, count: AMOUNTS.includes(p.count) ? p.count : DEFAULT_AMOUNT };
  }

  function loadRead() {
    const raw = store.get(READ_KEY, {});
    const cutoff = Date.now() - KEEP_READ_MS;
    const out = {};
    if (raw && typeof raw === "object") {
      for (const [id, ts] of Object.entries(raw)) if (typeof ts === "number" && ts > cutoff) out[id] = ts;
    }
    return out;
  }

  const isRead = (id) => Object.hasOwn(readMap, id);
  function setRead(id, value) {
    if (value) readMap[id] = Date.now();
    else delete readMap[id];
    store.set(READ_KEY, readMap);
  }

  function show(name) {
    for (const v of VIEWS) $(`view-${v}`).hidden = v !== name;
    $("edit-topics").hidden = name !== "today";
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function safeUrl(value) {
    try {
      const u = new URL(value);
      return u.protocol === "https:" || u.protocol === "http:" ? u.href : null;
    } catch {
      return null;
    }
  }

  const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

  // ---------- data ----------

  function validPick(p) {
    return p && typeof p.id === "string" && typeof p.title === "string" && safeUrl(p.url)
      && Array.isArray(p.topics);
  }

  async function fetchData() {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 10000);
    try {
      const res = await fetch(DATA_URL, { cache: "no-cache", signal: ctrl.signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      if (!json || !Array.isArray(json.picks)) throw new Error("unexpected data");
      json.picks = json.picks.filter(validPick).map((p) => ({
        ...p,
        score: Number(p.score) || 0,
        minutes: Math.max(1, Number(p.minutes) || 5),
      }));
      return json;
    } finally {
      clearTimeout(timer);
    }
  }

  async function load() {
    show("loading");
    try {
      data = await fetchData();
      renderToday();
    } catch {
      $("error-text").textContent = navigator.onLine === false
        ? "You're offline. Connect to the internet, then try again."
        : "The list didn't load. Try again in a moment.";
      show("error");
    }
  }

  // ---------- setup ----------

  function buildSetup() {
    const grid = $("topic-grid");
    grid.textContent = "";
    for (const [id, label] of Object.entries(TOPICS)) {
      const row = el("label", "topic");
      const input = el("input");
      input.type = "checkbox";
      input.name = "topic";
      input.value = id;
      row.append(input, document.createTextNode(label));
      grid.append(row);
    }
    const amount = $("amount");
    amount.textContent = "";
    for (const n of AMOUNTS) {
      const option = el("label");
      const input = el("input");
      input.type = "radio";
      input.name = "count";
      input.value = String(n);
      option.append(input, document.createTextNode(String(n)));
      amount.append(option);
    }
  }

  function openSetup() {
    const current = prefs || { topics: [], count: DEFAULT_AMOUNT };
    document.querySelectorAll('input[name="topic"]').forEach((i) => { i.checked = current.topics.includes(i.value); });
    document.querySelectorAll('input[name="count"]').forEach((i) => { i.checked = Number(i.value) === current.count; });
    $("setup-error").hidden = true;
    $("setup-cancel").hidden = !prefs;
    $("setup-save").textContent = prefs ? "Save topics" : "Show my reads";
    document.title = "Pick your topics: Daily Diff";
    show("setup");
  }

  function saveSetup(event) {
    event.preventDefault();
    const topics = [...document.querySelectorAll('input[name="topic"]:checked')].map((i) => i.value);
    if (!topics.length) {
      $("setup-error").hidden = false;
      document.querySelector('input[name="topic"]').focus();
      return;
    }
    const count = Number(document.querySelector('input[name="count"]:checked')?.value) || DEFAULT_AMOUNT;
    prefs = { topics, count };
    store.set(PREFS_KEY, prefs);
    extra = 0;
    showAll = false;
    route();
    $("main").focus();
  }

  // ---------- today ----------

  function pool() {
    const chosen = new Set(prefs.topics);
    return data.picks
      .filter((p) => showAll || p.topics.some((t) => chosen.has(t)))
      .sort((a, b) => b.score - a.score);
  }

  function formatDate(iso) {
    const d = new Date(`${iso}T12:00:00Z`);
    if (Number.isNaN(d.getTime())) return "";
    return d.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });
  }

  function untilNext() {
    const t = Date.parse(data.next_refresh_at);
    if (Number.isNaN(t)) return "";
    const ms = t - Date.now();
    if (ms <= 60000) return "New list any minute now.";
    const h = Math.floor(ms / 3600000);
    const m = Math.floor((ms % 3600000) / 60000);
    return `New list in ${h ? `${h}h ${m}m` : `${m}m`}.`;
  }

  function isLate() {
    const t = Date.parse(data.next_refresh_at);
    return !Number.isNaN(t) && Date.now() > t + LATE_AFTER_MS;
  }

  function renderBar(kept, total) {
    const bar = $("diffbar");
    bar.textContent = "";
    const keptCells = kept ? Math.max(1, Math.round((BAR_CELLS * kept) / Math.max(total, 1))) : 0;
    for (let i = 0; i < BAR_CELLS; i++) bar.append(el("span", i < keptCells ? "k" : ""));
  }

  function topicLabel(p) {
    const mine = showAll ? p.topics[0] : p.topics.find((t) => prefs.topics.includes(t));
    return TOPICS[mine] || "";
  }

  function lengthLabel(p) {
    if (p.kind === "video") return `${p.minutes} min watch`;
    if (p.kind === "repo") return "Repo";
    return `${p.minutes} min read`;
  }

  function readItem(p) {
    const li = el("li", "read");
    li.dataset.id = p.id;
    const done = isRead(p.id);
    li.classList.toggle("is-read", done);

    const tick = el("button", "tick");
    tick.type = "button";
    tick.setAttribute("aria-pressed", String(done));
    tick.setAttribute("aria-label", `${done ? "Mark as unread" : "Mark as read"}: ${p.title}`);

    const body = el("div", "body");
    const h2 = el("h2");
    const link = el("a", "", p.title);
    link.href = safeUrl(p.url);
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    h2.append(link);

    const meta = el("p", "meta");
    meta.append(el("span", "", p.source), el("span", "", lengthLabel(p)));
    if (["discussion", "release", "paper", "newsletter"].includes(p.kind)) {
      meta.append(el("span", "", p.kind[0].toUpperCase() + p.kind.slice(1)));
    }
    const label = topicLabel(p);
    if (label) meta.append(el("span", "", label));
    const discussion = p.discussion && safeUrl(p.discussion);
    if (discussion) {
      const d = el("a", "", "Discussion");
      d.href = discussion;
      d.target = "_blank";
      d.rel = "noopener noreferrer";
      meta.append(d);
    }
    body.append(h2, meta);
    if (p.why) body.append(el("p", "why", p.why));
    li.append(tick, body);
    return li;
  }

  function renderToday() {
    const all = pool();
    const visible = all.slice(0, prefs.count + extra);
    const considered = Math.max(Number(data.considered) || 0, visible.length);
    const skipped = considered - visible.length;

    $("today-date").textContent = formatDate(data.date);
    $("stat-add").textContent = `+${visible.length}`;
    $("stat-del").textContent = `-${skipped}`;
    $("diffstat").setAttribute("aria-label", `${plural(visible.length, "read")} kept, ${skipped} skipped`);
    renderBar(visible.length, considered);
    $("summary").textContent = visible.length
      ? `${plural(visible.length, "read")} for you today. ${skipped} other posts skipped.`
      : `${considered} posts checked today.`;

    const headline = $("headline");
    headline.textContent = data.headline || "";
    headline.hidden = !data.headline;

    const notice = $("notice");
    if (isLate()) {
      notice.textContent = `Today's list is running late, so these are the picks from ${formatDate(data.date)}. A new list should be here soon.`;
      notice.hidden = false;
    } else if (showAll) {
      notice.textContent = "Showing today's best from every topic. Your topics are unchanged.";
      notice.hidden = false;
    } else {
      notice.hidden = true;
    }

    const list = $("reads");
    list.textContent = "";
    for (const p of visible) list.append(readItem(p));
    list.hidden = !visible.length;
    $("empty").hidden = visible.length > 0;
    $("after").hidden = !visible.length;

    const remaining = all.length - visible.length;
    const more = $("more");
    more.hidden = remaining <= 0;
    more.textContent = `Show ${Math.min(prefs.count, remaining)} more`;

    const curated = data.curated_by === "ranking" ? "Ranked by votes" : "Picked by Claude";
    const refresh = Date.parse(data.next_refresh_at);
    const time = Number.isNaN(refresh) ? "" : new Date(refresh).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    $("foot-sources").textContent = `${curated} from ${data.source_count || "dozens of"} sources: Hacker News, Lobsters, GitHub, Medium, Substack, Mastodon, YouTube and engineering blogs.${time ? ` A new list arrives every day around ${time}.` : ""}`;

    document.title = `+${visible.length} today: Daily Diff`;
    show("today");
    updateDone();
  }

  function updateDone() {
    const items = [...document.querySelectorAll("#reads .read")];
    const allRead = items.length > 0 && items.every((li) => li.classList.contains("is-read"));
    const done = $("done");
    done.hidden = !allRead;
    done.textContent = `That's today. ${untilNext()}`;
  }

  function toggleItem(li, value) {
    const id = li.dataset.id;
    const next = value === undefined ? !isRead(id) : value;
    setRead(id, next);
    li.classList.toggle("is-read", next);
    const tick = li.querySelector(".tick");
    tick.setAttribute("aria-pressed", String(next));
    tick.setAttribute("aria-label", `${next ? "Mark as unread" : "Mark as read"}: ${li.querySelector("h2 a").textContent}`);
    updateDone();
  }

  // ---------- routing and events ----------

  function route() {
    if (!prefs) {
      openSetup();
    } else if (!data) {
      load();
    } else {
      renderToday();
    }
  }

  function bind() {
    $("setup-form").addEventListener("submit", saveSetup);
    $("topic-grid").addEventListener("change", () => { $("setup-error").hidden = true; });
    $("setup-cancel").addEventListener("click", () => route());
    $("edit-topics").addEventListener("click", openSetup);
    $("empty-edit").addEventListener("click", openSetup);
    $("empty-all").addEventListener("click", () => { showAll = true; renderToday(); });
    $("retry").addEventListener("click", load);
    $("more").addEventListener("click", () => {
      const before = document.querySelectorAll("#reads .read").length;
      extra += prefs.count;
      renderToday();
      document.querySelectorAll("#reads .read h2 a")[before]?.focus();
    });

    $("reads").addEventListener("click", (event) => {
      const li = event.target.closest(".read");
      if (!li) return;
      if (event.target.closest(".tick")) toggleItem(li);
      else if (event.target.closest("h2 a")) toggleItem(li, true);
    });
    $("reads").addEventListener("auxclick", (event) => {
      const li = event.target.closest(".read");
      if (li && event.button === 1 && event.target.closest("h2 a")) toggleItem(li, true);
    });

    document.addEventListener("keydown", (event) => {
      if (event.metaKey || event.ctrlKey || event.altKey || $("view-today").hidden) return;
      if (/^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName)) return;
      const links = [...document.querySelectorAll("#reads .read h2 a")];
      if (!links.length) return;
      const at = links.indexOf(document.activeElement);
      if (event.key === "j") {
        event.preventDefault();
        links[Math.min(at + 1, links.length - 1)].focus();
      } else if (event.key === "k") {
        event.preventDefault();
        links[Math.max(at - 1, 0)].focus();
      } else if (event.key === "o" && at >= 0) {
        event.preventDefault();
        links[at].click();
      } else if (event.key === "x" && at >= 0) {
        event.preventDefault();
        toggleItem(links[at].closest(".read"));
      }
    });

    // A tab left open overnight picks up the new list when you come back to it.
    document.addEventListener("visibilitychange", async () => {
      if (document.visibilityState !== "visible" || !data || !prefs) return;
      if (Date.now() < Date.parse(data.next_refresh_at)) {
        updateDone();
        return;
      }
      try {
        const fresh = await fetchData();
        if (fresh.generated_at !== data.generated_at) {
          data = fresh;
          extra = 0;
          showAll = false;
          if (!$("view-today").hidden) renderToday();
        }
      } catch {
        /* keep showing what we have */
      }
    });

    // Another tab changed topics or read state.
    window.addEventListener("storage", (event) => {
      if (event.key === PREFS_KEY) prefs = loadPrefs();
      if (event.key === READ_KEY) readMap = loadRead();
      if ((event.key === PREFS_KEY || event.key === READ_KEY) && !$("view-today").hidden) route();
    });
  }

  buildSetup();
  bind();
  route();
})();
