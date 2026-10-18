"""
config.py — Oppo Research Configuration
Sectors, role keywords, search queries, and run limits.
"""

# Curated watchlist — established aligned companies polled daily for new roles.
# Format: { "Company Name": "sector label" }
# These are searched regardless of recent funding activity. Replace with your own targets.
WATCHLIST_COMPANIES = {
    # AI / LLM infra
    "Anthropic":       "AI safety / LLM",
    "OpenAI":          "AI / LLM",
    "Cohere":          "AI / enterprise LLM",
    "Mistral AI":      "AI / LLM",
    "Scale AI":        "AI data / infra",
    "Weights & Biases":"AI / MLOps",
    "Perplexity":      "AI / search",
    "Together AI":     "AI / infra",
    # Fintech scaling
    "Stripe":          "fintech / payments",
    "Ramp":            "fintech / spend management",
    "Plaid":           "fintech / data",
    "Mercury":         "fintech / banking",
    # Crypto / web3 infra
    "Coinbase":        "crypto / exchange",
    "Circle":          "crypto / stablecoin",
    "Fireblocks":      "crypto / institutional",
    "Chainalysis":     "crypto / compliance",
    "Alchemy":         "crypto / developer infra",
    "Solana":         "crypto / developer infra",
    "Ethereum":         "crypto / developer infra",
    "Stellar":         "crypto / developer infra",
}

# How many days back to look for new role postings on watchlist companies
WATCHLIST_RECENCY_DAYS = 1

# Funding news search queries — Tavily runs these with a 2-day recency window
FUNDING_SEARCH_QUERIES = [
    "AI startup raised Series A Series B seed round funding 2026",
    "fintech startup new funding round announced 2026",
    "B2B SaaS startup funding announcement 2026",
    "emerging markets fintech AI startup raised investment 2026",
    "crypto web3 startup funding Series A seed 2026",
    # AI for good: nonprofit / social impact / education / economic mobility / AI diffusion
    "AI nonprofit humanitarian social impact funding grant announced 2026",
    "education AI startup funding raised 2026",
    "economic mobility financial inclusion AI startup funding raised 2026",
    "AI diffusion access emerging markets nonprofit initiative funding 2026",
    "AI for good startup nonprofit funding announcement 2026",
]

# Free RSS feeds for funding discovery — no API key, no rate limit, no monthly cap. Pulled
# alongside the Tavily queries above (not instead of) so this keeps working even when Tavily's
# plan is fully rate-limited or capped. Covers the same categories: AI, fintech, crypto/web3,
# and AI-for-good (nonprofit/social impact, education, economic mobility, AI diffusion).
# Note: RSS feed URLs occasionally change or get renamed by the publisher — fetch_funding_rss()
# skips any feed that fails to load rather than erroring, so a dead URL here just means slightly
# less coverage that day, not a broken run. Worth spot-checking these against a live run's logs
# periodically and pruning/replacing any that consistently return nothing.
FUNDING_RSS_FEEDS = [
    "https://techcrunch.com/category/fintech/feed/",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://techcrunch.com/category/startups/feed/",
    "https://techcrunch.com/tag/funding/feed/",
    "https://news.crunchbase.com/feed/",
    "https://venturebeat.com/category/ai/feed/",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://www.theblock.co/rss.xml",
    "https://www.devex.com/rss/news",
    "https://www.edsurge.com/news.rss",
]

# How far back an RSS item can be and still count as "recent" funding news. Wider than the
# Tavily queries' 2-day window since RSS has no server-side recency filter to apply up front.
RSS_LOOKBACK_HOURS = 72

# Role title keywords to include
TARGET_ROLE_KEYWORDS = [
    "strategy", "operations", "gtm", "go-to-market", "growth",
    "product", "partnerships", "chief of staff", "business development",
    "bizops", "revenue operations", "revops", "general manager",
    "market development", "expansion", "biz dev", "commerc",
]

# Role title keywords that disqualify a listing
EXCLUDE_ROLE_KEYWORDS = [
    "engineer", "developer", "designer", "data scientist", "analyst",
    "intern", "recruiter", "legal", "counsel", "finance", "accounting",
    "hr ", "people ops", "security", "devops", "ml ", "research scientist",
    "qa ", "qa/", "support", "customer success",
]

# Sectors to deprioritize — exclude these from company list
EXCLUDE_SECTORS = [
    "biotech", "pharma", "medical device", "defense", "aerospace",
    "real estate", "proptech", "gaming", "entertainment",
]

# Max companies to deeply research per run (controls Tavily + OpenAI spend)
MAX_COMPANIES_PER_RUN = 25

# Max roles to surface per company (1 keeps the digest scannable)
MAX_ROLES_PER_COMPANY = 1

# Minimum fit score to include in email (0-10)
MIN_FIT_SCORE_TO_INCLUDE = 5
