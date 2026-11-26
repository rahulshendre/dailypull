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

# Used only by the free ranking fallback. Matched as whole words, case-insensitive.
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
    "career": ["career", "hiring", "interview", "interviews", "engineering manager", "management", "leadership",
               "productivity", "layoffs", "promotion", "staff engineer", "burnout", "remote work", "culture"],
}

# (name, feed URL, topics the source usually covers[, quality prior 0-10, kind])
# The prior is where a post from this source starts before Claude judges it.
# Hand-picked blogs default to 6. Open firehoses (Medium tags, general news) start lower.
FEEDS = [
    ("Simon Willison", "https://simonwillison.net/atom/everything/", ["ai"]),
    ("Latent Space", "https://www.latent.space/feed", ["ai"]),
    ("Hugging Face", "https://huggingface.co/blog/feed.xml", ["ai"]),
    ("GitHub Blog", "https://github.blog/feed/", ["oss", "ai"]),
    ("Smashing Magazine", "https://www.smashingmagazine.com/feed/", ["web"]),
    ("Josh W Comeau", "https://www.joshwcomeau.com/rss.xml", ["web"]),
    ("Jake Archibald", "https://jakearchibald.com/posts.rss", ["web"]),
    ("web.dev", "https://web.dev/static/blog/feed.xml", ["web"]),
    ("Martin Fowler", "https://martinfowler.com/feed.atom", ["backend", "career"]),
    ("Cloudflare Blog", "https://blog.cloudflare.com/rss/", ["backend", "systems", "security"]),
    ("Netflix Tech Blog", "https://netflixtechblog.com/feed", ["backend"]),
    ("PlanetScale", "https://planetscale.com/blog/feed.atom", ["backend"]),
    ("SRE Weekly", "https://sreweekly.com/feed/", ["devops"], 6.0, "newsletter"),
    ("Charity Majors", "https://charity.wtf/feed/", ["devops", "career"]),
    ("Kubernetes Blog", "https://kubernetes.io/feed.xml", ["cloud"]),
    ("LWKD", "https://lwkd.info/feed.xml", ["cloud"]),
    ("CNCF", "https://www.cncf.io/feed/", ["cloud"]),
    ("Red Hat Blog", "https://www.redhat.com/en/rss/blog", ["cloud", "systems"]),
    ("Krebs on Security", "https://krebsonsecurity.com/feed/", ["security"]),
    ("Schneier on Security", "https://www.schneier.com/feed/atom/", ["security"]),
    ("Project Zero", "https://googleprojectzero.blogspot.com/feeds/posts/default", ["security"]),
    ("Trail of Bits", "https://blog.trailofbits.com/feed/", ["security"]),
    ("LWN", "https://lwn.net/headlines/rss", ["systems", "oss"]),
    ("Julia Evans", "https://jvns.ca/atom.xml", ["systems"]),
    ("Brendan Gregg", "https://www.brendangregg.com/blog/rss.xml", ["systems"]),
    ("Rust Blog", "https://blog.rust-lang.org/feed.xml", ["languages"]),
    ("Go Blog", "https://go.dev/blog/feed.atom", ["languages"]),
    ("Python Insider", "https://blog.python.org/feeds/posts/default", ["languages"]),
    ("TypeScript Blog", "https://devblogs.microsoft.com/typescript/feed/", ["languages", "web"]),
    ("Pragmatic Engineer", "https://newsletter.pragmaticengineer.com/feed", ["career"]),
    ("Will Larson", "https://lethain.com/feeds/", ["career"]),
    ("Kent Beck", "https://tidyfirst.substack.com/feed", ["career"]),
    ("Dan Luu", "https://danluu.com/atom.xml", ["systems", "career"]),
    ("Stack Overflow Blog", "https://stackoverflow.blog/feed/", ["career"]),
    # Substack and other newsletters
    ("ByteByteGo", "https://blog.bytebytego.com/feed", ["backend"]),
    ("System Design Newsletter", "https://newsletter.systemdesign.one/feed", ["backend"]),
    ("Refactoring", "https://refactoring.fm/feed", ["career"]),
    ("Interconnects", "https://www.interconnects.ai/feed", ["ai"]),
    ("One Useful Thing", "https://www.oneusefulthing.org/feed", ["ai"]),
    ("Ahead of AI", "https://magazine.sebastianraschka.com/feed", ["ai"]),
    ("Engineering Enablement", "https://newsletter.getdx.com/feed", ["career", "devops"]),
    ("JavaScript Weekly", "https://cprss.s3.amazonaws.com/javascriptweekly.com.xml", ["web"], 5.5, "newsletter"),
    ("Golang Weekly", "https://cprss.s3.amazonaws.com/golangweekly.com.xml", ["languages"], 5.5, "newsletter"),
    ("Console.dev", "https://console.dev/rss.xml", ["oss"], 5.5, "newsletter"),
    # Company engineering blogs
    ("Meta Engineering", "https://engineering.fb.com/feed/", ["backend", "systems"]),
    ("Stripe", "https://stripe.com/blog/feed.rss", ["backend"]),
    ("Dropbox Tech", "https://dropbox.tech/feed", ["backend", "systems"]),
    ("Spotify Engineering", "https://engineering.atspotify.com/feed/", ["backend"]),
    ("Airbnb Engineering", "https://medium.com/feed/airbnb-engineering", ["backend"]),
    ("Pinterest Engineering", "https://medium.com/feed/@Pinterest_Engineering", ["backend"]),
    ("Slack Engineering", "https://slack.engineering/feed/", ["backend"]),
    ("Discord", "https://discord.com/blog/rss.xml", ["backend"], 4.5),
    ("Figma", "https://www.figma.com/blog/feed/atom.xml", ["web"], 4.5),
    ("Shopify Engineering", "https://shopify.engineering/blog.atom", ["backend"]),
    ("Fly.io", "https://fly.io/blog/feed.xml", ["cloud", "systems"]),
    ("Tailscale", "https://tailscale.com/blog/index.xml", ["systems", "security"]),
    ("Grafana", "https://grafana.com/blog/index.xml", ["devops"], 5.0),
    ("Docker", "https://www.docker.com/blog/feed/", ["cloud"], 5.0),
    ("HashiCorp", "https://www.hashicorp.com/blog/feed.xml", ["devops", "cloud"], 5.0),
    ("Supabase", "https://supabase.com/rss.xml", ["backend"], 5.0),
    ("Google Developers", "https://developers.googleblog.com/feeds/posts/default", ["ai", "web"], 5.0),
    ("AWS Architecture", "https://aws.amazon.com/blogs/architecture/feed/", ["cloud"], 5.0),
    # AI labs
    ("OpenAI", "https://openai.com/news/rss.xml", ["ai"], 5.5),
    ("Google AI", "https://blog.google/technology/ai/rss/", ["ai"], 5.0),
    ("Google DeepMind", "https://deepmind.google/blog/rss.xml", ["ai"], 5.5),
    # Tech news (broad, so lower priors; Claude keeps only what engineers need)
    ("Techmeme", "https://www.techmeme.com/feed.xml", [], 4.5),
    ("InfoQ", "https://feed.infoq.com/", [], 5.0),
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
MASTODON_INSTANCES = ["hachyderm.io", "fosstodon.org", "mastodon.social"]

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

MAX_AGE_HOURS = 96        # blog posts older than this are skipped
PER_FEED = 8              # newest posts taken from each feed
MAX_CANDIDATES = 400      # sent to the picker
MIN_CANDIDATES = 40       # fewer than this means sources are broken: fail instead of publishing junk
HISTORY_DAYS = 14         # a link shown in the last N days is not shown again
DEFAULT_MODEL = "claude-opus-5-5"
REFRESH_UTC = (0, 30)     # the daily workflow runs at 00:30 UTC
