"""
researcher.py — web research engine.
Handles funding discovery, job search, company research, and JD extraction.

Job listings are fetched directly from Greenhouse/Lever/Ashby's public job-board APIs first —
they're free, structured, and already include full job description text, so most companies never
need a Tavily search or extract call at all. Tavily search is only used as a fallback for job
listings (when a company isn't on any of the three ATS platforms).

Funding discovery pulls from free RSS feeds (TechCrunch, Crunchbase News, VentureBeat, CoinDesk,
etc.) alongside Tavily's search queries, not instead of them — RSS has no API key and no cap, so
funding discovery keeps working even when Tavily's plan is fully rate-limited. Company
deep-research still relies on Tavily alone; it doesn't have a free structured-API equivalent the
way job listings and funding news do.
"""

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import feedparser
import requests
from tavily import TavilyClient

from config import (
    FUNDING_SEARCH_QUERIES,
    FUNDING_RSS_FEEDS,
    RSS_LOOKBACK_HOURS,
    WATCHLIST_RECENCY_DAYS,
    TARGET_ROLE_KEYWORDS,
    EXCLUDE_ROLE_KEYWORDS,
)

_client: Optional[TavilyClient] = None
_ATS_TIMEOUT = 8


def _get_client() -> TavilyClient:
    global _client
    if _client is None:
        api_key = os.environ.get("TAVILY_API_KEY")
        if not api_key:
            raise ValueError("TAVILY_API_KEY not set — add it to .env")
        _client = TavilyClient(api_key=api_key)
    return _client


def _role_query_phrase(limit: int = 5) -> str:
    """
    A short free-text phrase built from TARGET_ROLE_KEYWORDS for use in Tavily search queries,
    so the fallback job search actually looks for whatever roles config.py targets instead of
    a category hardcoded into the query string.
    """
    return " ".join(TARGET_ROLE_KEYWORDS[:limit])


def fetch_funding_rss() -> list[dict]:
    """
    Pull recent funding-relevant news from free RSS feeds (FUNDING_RSS_FEEDS in config.py) —
    no API key, no rate limit, no monthly cap. Returns the same {title, url, content} shape as
    Tavily search results so it drops straight into parse_funded_companies' existing extraction
    prompt, which already filters for genuine funding news vs. everything else in a feed.
    A feed that fails to load, times out, or doesn't parse is skipped — one dead URL just means
    slightly less coverage that run, not a broken pipeline.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=RSS_LOOKBACK_HOURS)
    all_results = []
    seen_urls: set[str] = set()

    for feed_url in FUNDING_RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            if not feed.entries:
                print(f"  [rss] No entries from {feed_url}")
                continue
            for entry in feed.entries[:30]:
                url = entry.get("link", "")
                if not url or url in seen_urls:
                    continue

                published = entry.get("published_parsed") or entry.get("updated_parsed")
                if published:
                    published_dt = datetime(*published[:6], tzinfo=timezone.utc)
                    if published_dt < cutoff:
                        continue
                    date_label = published_dt.strftime("%Y-%m-%d")
                else:
                    date_label = "date unknown"

                summary = entry.get("summary", "") or entry.get("description", "")
                summary = re.sub("<[^<]+?>", " ", summary)[:600]
                seen_urls.add(url)
                all_results.append({
                    "title": entry.get("title", ""),
                    "url": url,
                    "content": f"[Published: {date_label}] {summary}",
                })
        except Exception as e:
            print(f"  [rss] Failed for {feed_url}: {e}")

    print(f"  [rss] {len(all_results)} unique items across {len(FUNDING_RSS_FEEDS)} feeds")
    return all_results


def search_funded_companies(days_back: int = 2) -> list[dict]:
    """
    Search for recently funded companies via Tavily plus free RSS feeds. RSS is always
    attempted regardless of Tavily's state, so funding discovery keeps producing results even
    when Tavily is fully rate-limited or over its plan's usage cap.
    Returns a deduped list combining both sources (list of {title, url, content}).
    """
    all_results = []
    seen_urls: set[str] = set()

    try:
        client = _get_client()
        for query in FUNDING_SEARCH_QUERIES:
            try:
                print(f"  [search] {query}")
                response = client.search(
                    query=query,
                    search_depth="advanced",
                    max_results=8,
                    days=days_back,
                    include_raw_content=False,
                )
                for r in response.get("results", []):
                    url = r.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_results.append(r)
            except Exception as e:
                print(f"  [search] Failed: {e}")
    except ValueError as e:
        print(f"  [search] Tavily unavailable: {e}")

    print(f"  [search] {len(all_results)} unique Tavily results across {len(FUNDING_SEARCH_QUERIES)} queries")

    for r in fetch_funding_rss():
        url = r.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            all_results.append(r)

    print(f"  [search] {len(all_results)} unique results total (Tavily + RSS)")
    return all_results


def _slug_candidates(company_name: str) -> list[str]:
    """Generate plausible ATS board slugs for a company name, e.g. 'Together AI' -> 'togetherai', 'together-ai'."""
    base = re.sub(r"[^a-z0-9 ]", "", company_name.lower()).strip()
    bases = {base}
    for suffix in (" inc", " labs", " ai", " technologies", " technology", " co", " hq"):
        if base.endswith(suffix):
            bases.add(base[: -len(suffix)].strip())

    slugs: list[str] = []
    for b in bases:
        if not b:
            continue
        for candidate in (b.replace(" ", ""), b.replace(" ", "-")):
            if candidate and candidate not in slugs:
                slugs.append(candidate)
    return slugs


def _fetch_greenhouse(slug: str) -> Optional[list[dict]]:
    try:
        resp = requests.get(
            f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
            params={"content": "true"},
            timeout=_ATS_TIMEOUT,
        )
        if resp.status_code != 200:
            return None
        jobs = resp.json().get("jobs", [])
        if not jobs:
            return None
        return [
            {
                "title": j.get("title", ""),
                "url": j.get("absolute_url", ""),
                "location": (j.get("location") or {}).get("name", "Unknown"),
                "content": re.sub("<[^<]+?>", " ", j.get("content", "")),
            }
            for j in jobs
        ]
    except requests.RequestException:
        return None


def _fetch_lever(slug: str) -> Optional[list[dict]]:
    try:
        resp = requests.get(
            f"https://api.lever.co/v0/postings/{slug}",
            params={"mode": "json"},
            timeout=_ATS_TIMEOUT,
        )
        if resp.status_code != 200:
            return None
        jobs = resp.json()
        if not isinstance(jobs, list) or not jobs:
            return None
        return [
            {
                "title": j.get("text", ""),
                "url": j.get("hostedUrl", ""),
                "location": (j.get("categories") or {}).get("location", "Unknown"),
                "content": re.sub("<[^<]+?>", " ", j.get("descriptionPlain") or j.get("description", "")),
            }
            for j in jobs
        ]
    except requests.RequestException:
        return None


def _fetch_ashby(slug: str) -> Optional[list[dict]]:
    try:
        resp = requests.get(
            f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
            timeout=_ATS_TIMEOUT,
        )
        if resp.status_code != 200:
            return None
        jobs = resp.json().get("jobs", [])
        if not jobs:
            return None
        return [
            {
                "title": j.get("title", ""),
                "url": j.get("jobUrl", ""),
                "location": j.get("location", "Unknown"),
                "content": re.sub("<[^<]+?>", " ", j.get("descriptionHtml", "") or ""),
            }
            for j in jobs
        ]
    except requests.RequestException:
        return None


def fetch_ats_jobs(company_name: str) -> Optional[list[dict]]:
    """
    Try Greenhouse, Lever, and Ashby's public job-board APIs across plausible slugs for this
    company. Returns a list of {title, url, location, content} on the first platform that has a
    matching, non-empty board, or None if the company isn't found on any of the three (caller
    should fall back to Tavily search).
    """
    for slug in _slug_candidates(company_name):
        for fetch_fn in (_fetch_greenhouse, _fetch_lever, _fetch_ashby):
            jobs = fetch_fn(slug)
            if jobs:
                return jobs
    return None


def _matches_target_role(title: str) -> bool:
    t = title.lower()
    if any(k in t for k in EXCLUDE_ROLE_KEYWORDS):
        return False
    return any(k in t for k in TARGET_ROLE_KEYWORDS)


def _guess_seniority(title: str) -> str:
    t = title.lower()
    for label, keywords in (
        ("C-Level", ("chief", "ceo", "coo", "cfo", "cto")),
        ("VP", ("vp ", "vice president")),
        ("Head", ("head of", "head,")),
        ("Director", ("director",)),
        ("Lead", ("lead",)),
        ("Manager", ("manager",)),
        ("Senior", ("senior", "sr.", "sr ")),
    ):
        if any(k in t for k in keywords):
            return label
    return "IC"


def find_open_roles_structured(company_name: str) -> Optional[list[dict]]:
    """
    Fetch this company's open roles straight from its Greenhouse/Lever/Ashby board and filter
    locally by role keyword — no Tavily search, no LLM parsing needed since the API already
    returns clean titles and full JD text. Returns None if the company isn't on any of the
    three platforms, so the caller can fall back to find_open_roles (Tavily search).
    """
    jobs = fetch_ats_jobs(company_name)
    if jobs is None:
        return None
    return [
        {
            "title": j["title"],
            "url": j["url"],
            "location": j["location"] or "Unknown",
            "seniority": _guess_seniority(j["title"]),
            "content": j["content"],
        }
        for j in jobs
        if _matches_target_role(j["title"])
    ]


def find_open_roles(company_name: str) -> list[dict]:
    """
    Fallback: search for open roles matching TARGET_ROLE_KEYWORDS at a specific company via
    Tavily. Only used when find_open_roles_structured() returns None (company not on
    Greenhouse/Lever/Ashby). Returns raw Tavily results.
    """
    client = _get_client()
    all_results = []
    seen_urls: set[str] = set()
    role_phrase = _role_query_phrase()

    queries = [
        f"{company_name} open jobs {role_phrase} site:greenhouse.io OR site:lever.co OR site:ashbyhq.com OR site:jobs.lever.co OR site:boards.greenhouse.io",
        f"{company_name} careers hiring {role_phrase} 2026",
    ]

    for query in queries:
        try:
            response = client.search(
                query=query,
                search_depth="basic",
                max_results=8,
                days=30,
            )
            for r in response.get("results", []):
                url = r.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(r)
        except Exception as e:
            print(f"  [jobs] Search failed for {company_name}: {e}")

    return all_results


def research_company_deep(company_name: str) -> list[dict]:
    """
    Deep research on a company: product, market, team, investors, recent news.
    Returns raw Tavily results.
    """
    client = _get_client()
    all_results = []
    seen_urls: set[str] = set()

    queries = [
        f"{company_name} company what they do product overview 2025 2026",
        f"{company_name} funding investors team size traction customers revenue",
    ]

    for query in queries:
        try:
            response = client.search(
                query=query,
                search_depth="advanced",
                max_results=6,
                days=180,
            )
            for r in response.get("results", []):
                url = r.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(r)
        except Exception as e:
            print(f"  [research] Failed for {company_name}: {e}")

    return all_results


def find_watchlist_roles_structured(company_name: str) -> Optional[list[dict]]:
    """
    Same as find_open_roles_structured, for watchlist companies. The ATS APIs return whatever is
    currently posted (no recency filter available), so this trades the tight
    WATCHLIST_RECENCY_DAYS window for zero-cost, fully accurate current listings — a new posting
    just shows up here on the next run instead of being caught by a recency search.
    """
    return find_open_roles_structured(company_name)


def find_watchlist_roles(company_name: str) -> list[dict]:
    """
    Fallback: search for recently posted roles matching TARGET_ROLE_KEYWORDS at a watchlist
    company. Only used when find_watchlist_roles_structured() returns None (company not on
    Greenhouse/Lever/Ashby). Uses a tight recency window (WATCHLIST_RECENCY_DAYS) so only
    genuinely new postings surface. Returns raw Tavily results.
    """
    client = _get_client()
    all_results = []
    seen_urls: set[str] = set()
    role_phrase = _role_query_phrase()

    queries = [
        f"{company_name} new job openings {role_phrase} site:greenhouse.io OR site:lever.co OR site:ashbyhq.com OR site:jobs.lever.co OR site:boards.greenhouse.io",
        f"{company_name} hiring {role_phrase} 2026",
    ]

    for query in queries:
        try:
            response = client.search(
                query=query,
                search_depth="basic",
                max_results=8,
                days=WATCHLIST_RECENCY_DAYS,
            )
            for r in response.get("results", []):
                url = r.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(r)
        except Exception as e:
            print(f"  [watchlist] Search failed for {company_name}: {e}")

    return all_results


def fetch_job_description(url: str) -> str:
    """
    Extract full text from a job posting URL using Tavily's extract endpoint.
    Returns raw text content or empty string on failure.
    """
    if not url or url in ("#", "Unknown", ""):
        return ""

    client = _get_client()
    try:
        response = client.extract(urls=[url])
        results = response.get("results", [])
        if results:
            return results[0].get("raw_content", "")
    except Exception as e:
        print(f"  [extract] Failed for {url}: {e}")

    return ""
