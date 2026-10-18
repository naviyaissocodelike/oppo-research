# Oppo Research

A daily job-intelligence agent. It finds newly-funded companies and tracks a watchlist of
companies you care about, pulls their open roles matching whatever you target (Strategy /
Ops / GTM / Product by default — fully customizable to any field or function, see
"Repurposing" below), researches each company, and emails you an HTML digest with positioning
angles tailored to *your* background — not generic cover-letter filler.

This repo is a sanitized template: no one's personal data is committed to it. Fork it,
plug in your own background, and it's yours.

## Quick start (5 minutes to see it work, $0 spent)

```bash
git clone https://github.com/naviyaissocodelike/oppo-research
cd oppo-research
pip install -r requirements.txt
python agent.py --test-email --dry-run
```

That prints a sample digest to your terminal using fake data — no API keys needed, nothing
sent anywhere. If that runs, you're ready for the real setup below.

## What it actually does

1. **Funding discovery** — free RSS feeds (TechCrunch, Crunchbase News, VentureBeat, CoinDesk, etc. by default — swap for any industry's trade press) find companies that just raised money. Tavily search supplements this if you set it up, but RSS alone gets you real results.
2. **Watchlist polling** — a list of companies you name in `config.py` gets checked daily for new postings, regardless of funding news.
3. **Job search** — checks Greenhouse/Lever/Ashby's free public job-board APIs directly first (structured data, full job descriptions, no scraping). Falls back to a Tavily search only for the companies not on one of those three platforms.
4. **Role filtering** — keeps whatever role titles you define in `config.py` (defaults to Strategy/Ops/GTM/Product/Partnerships), drops everything else, purely by keyword — no hardcoded role category baked into the code, on either the direct-API or Tavily-fallback path.
5. **Company research** — pulls a product/traction/investor snapshot per company, via Tavily (the one piece that doesn't have a free structured-API equivalent).
6. **Positioning** — an LLM reads your profile (`profile_local.py`, never committed) and writes 1-2 sentences on why *you specifically* fit each role, plus a 1-10 fit score.
7. **Email digest** — one clean HTML email, sorted by fit score.

## Step-by-step setup

### 1. Clone and install

```bash
git clone https://github.com/naviyaissocodelike/oppo-research
cd oppo-research
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # or skip the venv
```

### 2. Add your real background

`profile.py` ships with a fake placeholder on purpose — it's committed and public, so it
should never hold your real info. Copy it and fill in the copy instead:

```bash
cp profile.py profile_local.py
# now edit profile_local.py with your real background
```

`profile_local.py` is gitignored — it never gets committed, even by accident — and
`agent.py` automatically uses it over `profile.py` whenever it's present.

### 3. Get your API keys and set up `.env`

```bash
cp .env.example .env
# then fill in the values below
```

| Key | Required? | Where to get it | Cost |
|---|---|---|---|
| `OPENAI_API_KEY` | **Yes** | [platform.openai.com](https://platform.openai.com/api-keys) | See cost table below |
| `GMAIL_FROM` / `GMAIL_TO` / `GMAIL_APP_PASSWORD` | **Yes** (to get the email) | Google Account → Security → 2-Step Verification → [App passwords](https://myaccount.google.com/apppasswords) | Free |
| `TAVILY_API_KEY` | Optional | [tavily.com](https://tavily.com) | Free tier works for light use — see "Running for free" below |

### 4. Test before you trust it

```bash
python agent.py --dry-run
```

This runs the full pipeline for real (real API calls, real research) but **prints the
digest to your terminal instead of emailing it** — nothing sent, no surprises. Read the
output, check the fit scores and positioning angles make sense, and look at your OpenAI/Tavily
dashboards afterward to see what it actually cost. Only run `python agent.py` (no flags) once
you're happy — that one sends a real email.

### 5. Automate it (optional)

Two options, pick one:

- **Your own machine (macOS):** `bash schedule.sh install` sets up a daily 8am run via `launchd`. `bash schedule.sh uninstall` removes it.
- **GitHub Actions (cloud, no machine required):** push your fork to GitHub, add the same keys as repo secrets (Settings → Secrets and variables → Actions), plus one more: paste the full contents of your `profile_local.py` into a secret named `CANDIDATE_PROFILE_PY` (it never touches the repo itself — see the note at the top of `.github/workflows/daily.yml`). The workflow runs daily at 13:00 UTC (8am ET) via `schedule:` — edit the cron expression in `daily.yml` to change the time, or delete the `schedule:` block entirely and keep only `workflow_dispatch:` if you'd rather trigger it manually.

**If you stop wanting daily runs:** delete the `schedule:` block in `.github/workflows/daily.yml` (keep `workflow_dispatch:` if you still want to run it by hand sometimes), or just disable the workflow from the repo's Actions tab. Either stops GitHub from running it — nothing else to turn off.

## What it costs

| Service | Typical cost | Notes |
|---|---|---|
| Greenhouse/Lever/Ashby job APIs | **$0** | Public, no key, no cap |
| RSS feeds (funding discovery) | **$0** | Public, no key, no cap |
| Gmail SMTP | **$0** | App password, not a paid API |
| OpenAI | **~$1-3/month** | Extraction/synthesis uses `gpt-4o-mini` (cheap); only the final positioning write-up uses `gpt-4o`, and that's capped at 400 tokens/role. Scales with `MAX_COMPANIES_PER_RUN` in `config.py` (default 25) and how many days you run it. |
| Tavily | **$0-?** | Free tier covers light use. This is the one service with a usage cap that can bind if you run it daily for weeks — see below. |

**Tavily is the one to watch.** It's only used now for company deep-research and as a
fallback for the few watchlist companies not on Greenhouse/Lever/Ashby — real usage, but
much lighter than the original design. Still: check your plan's limits on
[tavily.com](https://tavily.com) before scheduling daily runs, and keep an eye on their
usage dashboard. If you'd rather not think about it at all, see the free-only mode below.

### Running entirely for free

Don't set `TAVILY_API_KEY` at all (leave it out of `.env` / out of your GitHub secrets).
The agent degrades gracefully:
- Funding discovery still works — RSS feeds don't need Tavily.
- Job search still works for any company on Greenhouse, Lever, or Ashby (most funded
  startups and scale-ups are).
- Company research briefs come back thin ("Research unavailable") instead of detailed,
  since that step has no free structured-data equivalent.
- The handful of watchlist companies not on one of the three ATS platforms won't surface
  roles (check `config.py`'s `WATCHLIST_COMPANIES` — most well-known startups are covered).

That's a real tradeoff — thinner company context means slightly more generic positioning
angles — but it's genuinely $0 and still finds real roles at real companies.

You can push OpenAI toward $0 too: everything in `agent.py` already defaults to
`gpt-4o-mini` except the final positioning step (hardcoded to `gpt-4o` for quality). Change
that one `model="gpt-4o"` in `generate_positioning()` to `gpt-4o-mini` and the whole pipeline
runs on the cheap model — noticeably more generic positioning language, but functionally free
at this volume. Further than that (a genuinely $0 LLM) means swapping providers — Google's
Gemini Flash and Groq's hosted open-weight models both have free tiers generous enough for a
once-a-day job like this — but that's a real code change (rewriting `_llm_call` in `agent.py`
against a different SDK), not a flag you flip.

## Customize

Edit `config.py`:

| Setting | What it controls |
|---|---|
| `WATCHLIST_COMPANIES` | Companies polled daily regardless of funding activity |
| `TARGET_ROLE_KEYWORDS` / `EXCLUDE_ROLE_KEYWORDS` | Role titles to include/exclude |
| `EXCLUDE_SECTORS` | Sectors to skip entirely |
| `MAX_COMPANIES_PER_RUN` | Cap on companies researched per run — biggest lever on both runtime and cost |
| `FUNDING_SEARCH_QUERIES` / `FUNDING_RSS_FEEDS` | What funding discovery searches for |
| `MIN_FIT_SCORE_TO_INCLUDE` | How selective the final email is (1-10) |

Edit `profile_local.py` for your background and target roles — see step 2 above.

## Repurposing for a different field or function

Nothing about this agent is fintech/AI-specific by design — the whole watchlist, role
filter, and news sources are just data in `config.py`, and role filtering (both the direct
ATS-API path and the Tavily-fallback path) is purely keyword-driven, with no hardcoded role
category anywhere in the code. To retarget it:

1. **`profile_local.py`** — your own background (see step 2 above).
2. **`config.py` → `WATCHLIST_COMPANIES`** — swap in companies in your target field.
3. **`config.py` → `TARGET_ROLE_KEYWORDS` / `EXCLUDE_ROLE_KEYWORDS`** — the actual role-title
   filter, and the main lever. Some starting points:

   | Field | Add to `TARGET_ROLE_KEYWORDS` | Watch out for in `EXCLUDE_ROLE_KEYWORDS` |
   |---|---|---|
   | Credit / lending | `credit`, `underwriting`, `risk`, `collections`, `lending`, `portfolio` | **Remove `analyst` and `finance`** — the defaults exclude both, which blocks most actual credit titles ("Credit Analyst," "Risk Analyst," "Finance Manager") |
   | Comms / PR | `communications`, `comms`, `public relations`, `content`, `brand`, `corporate affairs` | Defaults don't conflict |
   | Account Executive / BD (any industry) | `account executive`, `business development`, `origination`, `sales`, `development` | Defaults don't conflict |

4. **`config.py` → `FUNDING_SEARCH_QUERIES` / `FUNDING_RSS_FEEDS`** — swap to sources that
   actually cover your field (energy/climate trade press instead of TechCrunch/CoinDesk, for
   example). Check a feed actually returns results in a real run's logs before relying on it —
   a dead or renamed URL is skipped silently, not fatal, but also silently gives you nothing.
5. **`config.py` → `EXCLUDE_SECTORS`** — a quick check that nothing here accidentally excludes
   your field (none of the defaults block credit, comms, or energy, but worth a glance if you're
   going somewhere more unusual).
6. Test with `python agent.py --dry-run` before scheduling anything — see "Test before you
   trust it" above.

## Files

| File | Role |
|---|---|
| `agent.py` | Orchestrator — runs the pipeline, scores and filters opportunities, sends email |
| `researcher.py` | Job/funding/company research — Greenhouse/Lever/Ashby APIs, RSS feeds, Tavily |
| `profile.py` | Placeholder profile template (committed, safe to be public) |
| `profile_local.py` | Your real profile (gitignored, never committed — you create this) |
| `emailer.py` | HTML email composition + Gmail SMTP send |
| `config.py` | Watchlist, role keywords, exclusion rules, run limits |
| `schedule.sh` | macOS `launchd` installer/uninstaller for local daily runs |
| `.github/workflows/daily.yml` | Optional GitHub Actions cloud schedule |

## Notes

- LLM calls go through OpenAI (`_llm_call` in `agent.py`). Swapping to a different provider is a contained change in that one function.
- This repo is designed to be safe to fork and share: nothing personal lives in a committed file, by construction. Keep it that way in your own fork — real background goes in `profile_local.py`, never `profile.py`.
