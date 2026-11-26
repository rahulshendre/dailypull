"""Static configuration: the topics readers can choose and the sources we read."""

TOPICS = {
    "ai": "AI and coding agents",
    "web": "Web and frontend",
    "backend": "Backend and databases",
    "devops": "DevOps and SRE",
    "cloud": "Kubernetes and cloud native",
    "security": "Security",
    "systems": "Linux and systems",
    "languages": "Programming languages",
    "oss": "Open source",
    "career": "Career and craft",
}

KINDS = ["article", "discussion", "repo", "release", "paper", "video", "newsletter"]

# Topic tagging. Matched as whole words, case-insensitive. A title match counts; the body text needs two.
KEYWORDS = {
    "ai": ["ai", "llm", "llms", "gpt", "claude", "openai", "anthropic", "gemini", "agent", "agents", "agentic",
           "copilot", "cursor", "mcp", "inference", "rag", "embeddings", "prompt", "machine learning", "neural",
           "transformer", "vibe coding", "fine-tuning", "diffusion"],
    "web": ["css", "html", "javascript", "browser", "browsers", "react", "vue", "svelte", "frontend", "front-end",
            "dom", "next.js", "node.js", "wasm", "webassembly", "accessibility", "chrome", "firefox", "safari"],
    "backend": ["database", "databases", "postgres", "postgresql", "mysql", "sqlite", "redis", "kafka", "backend",
                "distributed", "queue", "caching", "sql", "scalability", "microservices", "grpc", "api design"],
    "devops": ["sre", "devops", "incident", "outage", "postmortem", "post-mortem", "on-call", "oncall",
               "observability", "monitoring", "reliability", "slo", "slos", "ci/cd", "deployment", "terraform",
               "ansible", "opentelemetry", "prometheus", "grafana", "chaos engineering", "platform engineering"],
    "cloud": ["kubernetes", "k8s", "openshift", "container", "containers", "docker", "podman", "helm", "cncf",
              "cloud native", "cloud-native", "aws", "gcp", "azure", "serverless", "istio", "argo", "service mesh"],
    "security": ["security", "vulnerability", "vulnerabilities", "cve", "exploit", "breach", "malware",
                 "ransomware", "phishing", "zero-day", "0day", "supply chain", "authentication", "encryption",
                 "tls", "backdoor", "attack", "attackers"],
    "systems": ["linux", "kernel", "unix", "filesystem", "ebpf", "bpf", "performance", "cpu", "networking", "tcp",
                "dns", "systemd", "rhel", "fedora", "debian", "ubuntu", "assembly", "operating system"],
    "languages": ["rust", "golang", "python", "java", "kotlin", "swift", "zig", "c++", "haskell", "ocaml",
                  "elixir", "ruby", "php", "c#", "typescript", "compiler", "type system", "programming language"],
    "oss": ["open source", "open-source", "github", "license", "licensing", "maintainer", "maintainers", "foss",
            "gitlab", "contributors"],
    "career": ["career", "hiring", "interview", "interviews", "engineering manager",
               "productivity", "layoffs", "promotion", "staff engineer", "burnout", "remote work", "tech lead",
               "engineering management"],
}

# (name, feed URL, topics the source usually covers[, quality prior 0-10, kind])
# The prior is a post's starting score (votes and editors' picks add to it).
# Personal blogs by experts post rarely and well: 7. Company marketing and firehoses
# (Medium tags, general news) start lower.
FEEDS = [
    ("Simon Willison", "https://simonwillison.net/atom/entries/", ["ai"], 7.0),
    ("Latent Space", "https://www.latent.space/feed", ["ai"], 6.0),
    ("Hugging Face", "https://huggingface.co/blog/feed.xml", ["ai"], 5.0),
    ("GitHub Blog", "https://github.blog/feed/", ["oss", "ai"], 5.0),
    ("Smashing Magazine", "https://www.smashingmagazine.com/feed/", ["web"], 5.0),
    ("Josh W Comeau", "https://www.joshwcomeau.com/rss.xml", ["web"], 7.0),
    ("Jake Archibald", "https://jakearchibald.com/posts.rss", ["web"], 7.0),
    ("web.dev", "https://web.dev/static/blog/feed.xml", ["web"], 5.5),
    ("Martin Fowler", "https://martinfowler.com/feed.atom", ["backend", "career"], 7.0),
    ("Cloudflare Blog", "https://blog.cloudflare.com/rss/", ["backend", "systems", "security"], 6.5),
    ("Netflix Tech Blog", "https://netflixtechblog.com/feed", ["backend"], 6.0),
    ("PlanetScale", "https://planetscale.com/blog/feed.atom", ["backend"], 6.0),
    ("Charity Majors", "https://charity.wtf/feed/", ["devops", "career"], 7.0),
    ("Kubernetes Blog", "https://kubernetes.io/feed.xml", ["cloud"], 5.5),
    ("LWKD", "https://lwkd.info/feed.xml", ["cloud"], 5.0),
    ("CNCF", "https://www.cncf.io/feed/", ["cloud"], 4.0),
    ("Red Hat Blog", "https://www.redhat.com/en/rss/blog", ["cloud", "systems"], 4.5),
    ("Krebs on Security", "https://krebsonsecurity.com/feed/", ["security"], 6.5),
    ("Schneier on Security", "https://www.schneier.com/feed/atom/", ["security"], 5.5),
    ("Project Zero", "https://googleprojectzero.blogspot.com/feeds/posts/default", ["security"], 7.0),
    ("Trail of Bits", "https://blog.trailofbits.com/feed/", ["security"], 6.5),
    ("LWN", "https://lwn.net/headlines/rss", ["systems", "oss"], 5.5),
    ("Julia Evans", "https://jvns.ca/atom.xml", ["systems"], 7.0),
    ("Brendan Gregg", "https://www.brendangregg.com/blog/rss.xml", ["systems"], 7.0),
    ("Rust Blog", "https://blog.rust-lang.org/feed.xml", ["languages"], 6.0),
    ("Go Blog", "https://go.dev/blog/feed.atom", ["languages"], 6.0),
    ("Python Insider", "https://blog.python.org/feeds/posts/default", ["languages"], 5.5),
    ("TypeScript Blog", "https://devblogs.microsoft.com/typescript/feed/", ["languages", "web"], 6.0),
    ("Pragmatic Engineer", "https://newsletter.pragmaticengineer.com/feed", ["career"], 6.5),
    ("Will Larson", "https://lethain.com/feeds/", ["career"], 7.0),
    ("Kent Beck", "https://tidyfirst.substack.com/feed", ["career"], 7.0),
    ("Dan Luu", "https://danluu.com/atom.xml", ["systems", "career"], 7.0),
    ("Stack Overflow Blog", "https://stackoverflow.blog/feed/", ["career"], 4.5),
    # Substack and other newsletters
    ("ByteByteGo", "https://blog.bytebytego.com/feed", ["backend"], 5.5),
    ("System Design Newsletter", "https://newsletter.systemdesign.one/feed", ["backend"], 5.0),
    ("Refactoring", "https://refactoring.fm/feed", ["career"], 5.0),
    ("Interconnects", "https://www.interconnects.ai/feed", ["ai"], 6.0),
    ("One Useful Thing", "https://www.oneusefulthing.org/feed", ["ai"], 5.5),
    ("Ahead of AI", "https://magazine.sebastianraschka.com/feed", ["ai"], 6.0),
    ("Engineering Enablement", "https://newsletter.getdx.com/feed", ["career", "devops"], 5.0),
    ("Console.dev", "https://console.dev/rss.xml", ["oss"], 5.5, "newsletter"),
    # Company engineering blogs
    ("Meta Engineering", "https://engineering.fb.com/feed/", ["backend", "systems"], 5.5),
    ("Stripe", "https://stripe.com/blog/feed.rss", ["backend"], 6.0),
    ("Dropbox Tech", "https://dropbox.tech/feed", ["backend", "systems"], 5.5),
    ("Spotify Engineering", "https://engineering.atspotify.com/feed/", ["backend"], 5.0),
    ("Airbnb Engineering", "https://medium.com/feed/airbnb-engineering", ["backend"], 5.5),
    ("Pinterest Engineering", "https://medium.com/feed/@Pinterest_Engineering", ["backend"], 5.0),
    ("Slack Engineering", "https://slack.engineering/feed/", ["backend"], 5.5),
    ("Discord", "https://discord.com/blog/rss.xml", ["backend"], 4.5),
    ("Figma", "https://www.figma.com/blog/feed/atom.xml", ["web"], 4.5),
    ("Shopify Engineering", "https://shopify.engineering/blog.atom", ["backend"], 5.5),
    ("Fly.io", "https://fly.io/blog/feed.xml", ["cloud", "systems"], 6.0),
    ("Tailscale", "https://tailscale.com/blog/index.xml", ["systems", "security"], 6.0),
    ("Grafana", "https://grafana.com/blog/index.xml", ["devops"], 4.5),
    ("Docker", "https://www.docker.com/blog/feed/", ["cloud"], 4.5),
    ("HashiCorp", "https://www.hashicorp.com/blog/feed.xml", ["devops", "cloud"], 4.5),
    ("Supabase", "https://supabase.com/rss.xml", ["backend"], 4.5),
    ("Google Developers", "https://developers.googleblog.com/feeds/posts/default", ["ai", "web"], 4.5),
    ("AWS Architecture", "https://aws.amazon.com/blogs/architecture/feed/", ["cloud"], 4.5),
    # AI labs
    ("OpenAI", "https://openai.com/news/rss.xml", ["ai"], 5.5),
    ("Google AI", "https://blog.google/technology/ai/rss/", ["ai"], 4.5),
    ("Google DeepMind", "https://deepmind.google/blog/rss.xml", ["ai"], 5.5),
    # Tech news (broad, so lower priors; only well-voted stories make it)
    ("Techmeme", "https://www.techmeme.com/feed.xml", [], 4.0),
    ("InfoQ", "https://feed.infoq.com/", [], 4.5),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/technology-lab", [], 4.5),
    ("The Register", "https://www.theregister.com/headlines.atom", [], 3.5),
    # Medium tag firehoses: lots of noise, some gems
    ("Medium", "https://medium.com/feed/tag/programming", [], 3.0),
    ("Medium", "https://medium.com/feed/tag/software-engineering", [], 3.0),
    ("Medium", "https://medium.com/feed/tag/devops", ["devops"], 3.0),
    ("Medium", "https://medium.com/feed/tag/kubernetes", ["cloud"], 3.0),
    ("Medium", "https://medium.com/feed/tag/artificial-intelligence", ["ai"], 3.0),
    ("Medium", "https://medium.com/feed/tag/cybersecurity", ["security"], 3.0),
    # YouTube channels
    ("Fireship", "https://www.youtube.com/feeds/videos.xml?channel_id=UCsBjURrPoezykLs9EqgamOA", ["web", "ai"], 5.0, "video"),
    ("ByteByteGo on YouTube", "https://www.youtube.com/feeds/videos.xml?channel_id=UCZgt6AzoyjslHTC9dz0UoTw", ["backend"], 5.5, "video"),
    ("Hussein Nasser", "https://www.youtube.com/feeds/videos.xml?channel_id=UC_ML5xP23TOWKUcc-oAE_Eg", ["backend"], 5.5, "video"),
]

# Mastodon instances whose public "trending links" we read (no key needed).
MASTODON_INSTANCES = ["hachyderm.io", "fosstodon.org"]  # tech servers; mastodon.social trends are general news

# Read through Reddit's official API when REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET are set.
SUBREDDITS = ["programming", "ExperiencedDevs", "devops", "sre", "kubernetes", "netsec", "linux", "rust",
              "golang", "Python", "javascript", "webdev", "MachineLearning", "LocalLLaMA", "ClaudeAI",
              "selfhosted"]
SUBREDDIT_TOPICS = {
    "programming": [], "ExperiencedDevs": ["career"], "devops": ["devops"], "sre": ["devops"],
    "kubernetes": ["cloud"], "netsec": ["security"], "linux": ["systems"], "rust": ["languages"],
    "golang": ["languages"], "Python": ["languages"], "javascript": ["web"], "webdev": ["web"],
    "MachineLearning": ["ai"], "LocalLLaMA": ["ai"], "ClaudeAI": ["ai"], "selfhosted": ["systems", "oss"],
}

# Lobsters and dev.to tags mapped to our topics.
TAG_TOPICS = {
    "ai": "ai", "vibecoding": "ai", "machinelearning": "ai", "llm": "ai",
    "web": "web", "javascript": "web", "css": "web", "browsers": "web", "react": "web", "webdev": "web",
    "frontend": "web",
    "databases": "backend", "distributed": "backend", "api": "backend", "backend": "backend",
    "devops": "devops", "sre": "devops", "monitoring": "devops",
    "kubernetes": "cloud", "docker": "cloud", "cloud": "cloud", "aws": "cloud", "virtualization": "cloud",
    "security": "security", "privacy": "security", "cybersecurity": "security",
    "linux": "systems", "unix": "systems", "hardware": "systems", "performance": "systems",
    "networking": "systems", "osdev": "systems", "systems": "systems",
    "rust": "languages", "go": "languages", "python": "languages", "plt": "languages", "c": "languages",
    "c++": "languages", "haskell": "languages", "ruby": "languages", "java": "languages", "zig": "languages",
    "lisp": "languages", "elixir": "languages", "typescript": "languages",
    "release": "oss", "opensource": "oss", "law": "oss",
    "culture": "career", "person": "career", "job": "career", "practices": "career", "career": "career",
    "productivity": "career",
}

# When two topics match equally, the narrower one wins ("security incident" is security, not devops).
TOPIC_PRIORITY = ["security", "ai", "cloud", "web", "backend", "systems", "languages", "devops", "oss", "career"]

MAX_AGE_HOURS = 96        # blog posts older than this are skipped
PER_FEED = 8              # newest posts taken from each feed
MAX_CANDIDATES = 400      # best candidates kept after scoring
MIN_CANDIDATES = 40       # fewer than this means sources are broken: fail instead of publishing junk
HISTORY_DAYS = 14         # a link shown in the last N days is not shown again
REFRESH_UTC = (0, 30)     # the daily workflow runs at 00:30 UTC

# ---------- editors' picks ----------
# Hand-curated newsletters. Every link in their latest issue is a vote from a human editor.
# (name, feed URL, topics, style) where style "issue" reads every link of an issue and
# "linkblog" takes the first outside link of each post.
EDITORS = [
    ("SRE Weekly", "https://sreweekly.com/feed/", ["devops"], "issue"),
    ("JavaScript Weekly", "https://cprss.s3.amazonaws.com/javascriptweekly.com.xml", ["web"], "issue"),
    ("Node Weekly", "https://cprss.s3.amazonaws.com/nodeweekly.com.xml", ["web", "backend"], "issue"),
    ("Frontend Focus", "https://cprss.s3.amazonaws.com/frontendfoc.us.xml", ["web"], "issue"),
    ("Golang Weekly", "https://cprss.s3.amazonaws.com/golangweekly.com.xml", ["languages"], "issue"),
    ("Postgres Weekly", "https://cprss.s3.amazonaws.com/postgresweekly.com.xml", ["backend"], "issue"),
    ("PyCoder's Weekly", "https://pycoders.com/feed", ["languages"], "issue"),
    ("This Week in Rust", "https://this-week-in-rust.org/rss.xml", ["languages"], "issue"),
    ("Import AI", "https://importai.substack.com/feed", ["ai"], "issue"),
    ("Simon Willison's links", "https://simonwillison.net/atom/links/", ["ai"], "linkblog"),
]
EDITOR_MAX_AGE_DAYS = 10  # weekly newsletters: only the latest issue
EDITOR_MAX_LINKS = 25     # per newsletter
EDITOR_PRIOR = 5.5        # starting score of a link only an editor has picked
SKIP_LINK_HOSTS = {
    "twitter.com", "x.com", "bsky.app", "mastodon.social", "fosstodon.org", "hachyderm.io", "threads.net",
    "linkedin.com", "facebook.com", "instagram.com", "meetup.com", "lu.ma", "eventbrite.com", "discord.gg",
    "discord.com", "t.me", "reddit.com", "patreon.com",
}

# ---------- scoring ----------
# Votes are compared within each site: a story's score is lo + span * (its rank among that
# site's stories today, 0 to 1). So 300 points on Hacker News and 40 on Lobsters can tie.
VOTE_SCALE = {
    "Hacker News": (4.0, 5.0),
    "Lobsters": (4.0, 5.0),
    "Mastodon": (3.0, 4.5),
    "Reddit": (3.0, 4.5),
    "GitHub Trending": (2.5, 4.0),
    "DEV": (1.5, 3.5),
}
AGREEMENT_BONUS = 1.2      # per extra independent place (site, editor, blog) with the same link
AGREEMENT_MAX = 4.0
CLICKBAIT_PENALTY = 3.0
FLAMEWAR_PENALTY = 2.0     # far more comments than votes usually means an argument, not a read
AGE_PENALTY_PER_DAY = 0.3  # for blog posts and editors' picks
SOURCE_PENALTY = 0.8       # each extra pick from the same source costs this much, to keep the list varied
HN_WINDOW_HOURS = 48       # Hacker News stories from the last two days...
HN_MIN_POINTS = 60         # ...that at least this many people voted for
PICKS_PER_TOPIC = 6
MAX_PICKS = 50

# Dropped outright.
# Checked against titles only ("leader election" in a Raft post is fine, so no bare "election").
POLITICS = ["trump", "biden", "kamala", "presidential", "midterms", "electoral", "republican", "republicans", "democrat",
            "democrats", "gop", "maga", "white house", "putin", "netanyahu", "gaza", "hamas", "zelensky",
            "senator", "congressman", "congresswoman"]
NOISE_TITLES = [r"who is hiring", r"who wants to be hired", r"seeking freelancer", r"^security updates for ",
                r"^\[?sponsored\]?\b"]
# Lowered, not dropped.
CLICKBAIT = [r"^\d+\s+(things|ways|tips|reasons|tools|mistakes|habits|secrets|tricks|lessons|libraries|books)\b",
             r"you won.?t believe", r"blow your mind", r"must[- ]know", r"nobody tells you",
             r"every (developer|programmer|engineer) should", r"\bstop using\b", r"ultimate guide",
             r"cheat ?sheet", r"interview (questions|preparation|prep)", r"\bin \d+ minutes\b", r"game[- ]changer"]

# ---------- classics ----------
# Old posts that Hacker News readers keep posting again: their titles end in a year, like "(2015)".
CLASSIC_MIN_POINTS = 150
CLASSIC_MIN_AGE_YEARS = 3       # the article itself is at least this old
CLASSIC_FIRST_YEAR = 1960
CLASSIC_HISTORY_DAYS = 3650     # each classic is shown once
# Extra title words that place a classic under "Career and craft" (general programming essays).
CLASSIC_CRAFT_WORDS = ["programmer", "programmers", "programming", "software", "engineer", "engineers",
                       "engineering", "code", "coding", "debugging", "bug", "bugs", "computer", "computers",
                       "hacker", "hackers", "complexity"]
