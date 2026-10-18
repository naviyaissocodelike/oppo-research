"""
agent.py — Wise Glade
Daily job intelligence agent. Surfaces newly-funded companies with open Strategy/Ops/GTM/Product
roles, deep-researches each opportunity, and generates candidate-specific differentiated positioning.

Run:
  python agent.py --dry-run     # Full pipeline, prints digest, no email sent
  python agent.py --test-email  # Sends a test email with sample data to verify Gmail SMTP
  python agent.py               # Full run — research + email
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

from openai import OpenAI

from researcher import (
    search_funded_companies,
    find_open_roles,
    find_open_roles_structured,
    find_watchlist_roles,
    find_watchlist_roles_structured,
    research_company_deep,
    fetch_job_description,
)
try:
    from profile_local import CANDIDATE_PROFILE  # your real, gitignored profile — preferred if present
except ImportError:
    from profile import CANDIDATE_PROFILE  # example template, safe for a public repo
from emailer import compose_html_email, send_email
from config import (
    MAX_COMPANIES_PER_RUN,
    MAX_ROLES_PER_COMPANY,
    MIN_FIT_SCORE_TO_INCLUDE,
    EXCLUDE_SECTORS,
    TARGET_ROLE_KEYWORDS,
    EXCLUDE_ROLE_KEYWORDS,
    WATCHLIST_COMPANIES,
)

# ── OpenAI client ───────────────────────────────────────────────────────────────────

_openai = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))


def _llm_call(system: str, prompt: str, max_tokens: int = 2000, model: str = "gpt-4o-mini") -> str:
    response = _openai.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content


def _parse_json(text: str, fallback) -> any:
    """Strip markdown fences and parse JSON, returning fallback on failure."""
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return fallback


# ── LLM synthesis functions ────────────────────────────────────────────

def parse_funded_companies(raw_results: list[dict]) -> list[dict]:
    """Use the LLM to extract structured company records from Tavily funding news results."""
    if not raw_results:
        return []

    context = "\n\n".join(
        f"Source: {r.get('url', '')}\nTitle: {r.get('title', '')}\nContent: {r.get('content', '')[:600]}"
        for r in raw_results[:20]
    )

    prompt = f"""From these news search results about recent startup funding announcements, extract a list of companies that raised funding.

For each company/organization return a JSON object with:
- name: company or organization name (string)
- amount: funding amount e.g. "$15M", "$5M", "undisclosed" (string)
- stage: funding stage e.g. "Seed", "Series A", "Series B", "Series C", or "Grant" for nonprofit/foundation grant funding (string)
- sector: primary sector e.g. "AI", "fintech", "B2B SaaS", "crypto", "climate tech", "AI for good", "education", "nonprofit/social impact" (string)
- description: 1-sentence company/org description (string)
- url: company website or the news article URL (string)

Rules:
- Only include companies/organizations that clearly and recently raised funding — this includes equity rounds (Seed/Series A/B/C) AND nonprofit or foundation grants (skip opinion pieces, lists, non-funding news)
- Skip companies in these sectors: {', '.join(EXCLUDE_SECTORS)}
- Return a JSON array, no markdown

Search results:
{context}"""

    response = _llm_call(
        "You are a precise JSON extractor. Return only valid JSON arrays, no markdown, no explanation.",
        prompt,
    )
    return _parse_json(response, [])


def parse_job_listings(raw_results: list[dict], company_name: str) -> list[dict]:
    """Use the LLM to extract relevant job listings from Tavily search results."""
    if not raw_results:
        return []

    context = "\n\n".join(
        f"Source: {r.get('url', '')}\nTitle: {r.get('title', '')}\nContent: {r.get('content', '')[:500]}"
        for r in raw_results
    )

    prompt = f"""From these search results about {company_name} job openings, extract relevant roles.

Target role keywords (include if title contains any): {', '.join(TARGET_ROLE_KEYWORDS)}
Exclude if title contains any: {', '.join(EXCLUDE_ROLE_KEYWORDS)}

For each relevant role return a JSON object with:
- title: job title (string)
- url: direct URL to the job posting (string, use the source URL if no better one)
- location: location if mentioned, else "Remote" or "Unknown" (string)
- seniority: "IC", "Senior", "Lead", "Manager", "Director", "VP", "Head", or "C-Level" (string)

Return a JSON array. Only include strategy/ops/product/GTM roles. Skip engineering, design, data science, finance, legal, HR.

Search results:
{context}"""

    response = _llm_call(
        "You are a precise JSON extractor. Return only valid JSON arrays, no markdown.",
        prompt,
    )
    return _parse_json(response, [])


def build_company_brief(company_name: str, research_results: list[dict]) -> dict:
    """Use the LLM to synthesize company research into a structured brief."""
    if not research_results:
        return {
            "product": "Research unavailable",
            "market": "", "stage": "", "traction": "",
            "competitors": "", "hiring_signals": "",
            "investors": "", "recent_news": "",
        }

    context = "\n\n".join(
        f"Source: {r.get('url', '')}\nContent: {r.get('content', '')[:700]}"
        for r in research_results[:8]
    )

    prompt = f"""Synthesize this research about {company_name} into a structured company brief.

Return a JSON object with:
- product: What they build and do (2-3 sentences)
- market: Target market and customer type (1-2 sentences)
- stage: Company stage and approximate team size if known
- traction: Traction signals (revenue, users, partnerships, notable customers — be specific if mentioned)
- competitors: Main competitors or comparable companies
- hiring_signals: What their current hiring pattern suggests about growth priorities
- investors: Notable investors if mentioned (string, comma-separated)
- recent_news: Single most important recent development

Research:
{context}"""

    response = _llm_call(
        "You are a precise JSON extractor. Return only valid JSON, no markdown.",
        prompt,
    )
    return _parse_json(response, {
        "product": "Research unavailable",
        "market": "", "stage": "", "traction": "",
        "competitors": "", "hiring_signals": "",
        "investors": "", "recent_news": "",
    })


def analyze_role(jd_text: str, company_brief: dict) -> dict:
    """Use the LLM to cut through JD filler and identify what the role actually needs."""
    prompt = f"""Analyze this job description. Return a JSON object with:
- core_need: What they ACTUALLY need this person to do (1-2 sentences, cut through HR fluff)
- key_skills: Top 3-5 skills they truly need (list of strings)
- stage_signals: What the role signals about company stage/maturity (1 sentence)
- culture_signals: What the JD reveals about culture (1 sentence)
- growth_path: Where this role could lead in 2-3 years
- red_flags: Any concerning aspects (string, or empty string if none)
- ideal_background: 2-sentence description of the perfect candidate they have in mind

Company context: {json.dumps(company_brief, indent=2)}

Job description:
{jd_text[:3500]}"""

    response = _llm_call(
        "You are a sharp talent advisor who reads between the lines of job descriptions. "
        "Be specific and candid. Return only valid JSON, no markdown.",
        prompt,
    )
    return _parse_json(response, {
        "core_need": "Analysis unavailable",
        "key_skills": [], "stage_signals": "", "culture_signals": "",
        "growth_path": "", "red_flags": "", "ideal_background": "",
    })


def generate_positioning(
    company: dict,
    company_brief: dict,
    role: dict,
    role_analysis: dict,
) -> dict:
    """Generate a brief positioning angle and fit score for this opportunity."""
    prompt = f"""Company: {company['name']} ({company.get('sector', '')})
Product: {company_brief.get('product', '')}
Recent news: {company_brief.get('recent_news', '')}
Role: {role['title']}
What they need: {role_analysis.get('core_need', '')}

Return a JSON object with exactly two fields:
- angle: 1-2 sentences on what makes this company interesting right now, and one specific reason why the candidate's background (see profile below) is a natural fit for this role. Be concrete, not generic.
- fit_score: Integer 1-10. 10 = they'd be a top candidate. Be honest."""

    response = _llm_call(
        f"You are a concise talent advisor. Here is the candidate's profile:\n\n{CANDIDATE_PROFILE}\n\nReturn only valid JSON, no markdown.",
        prompt,
        max_tokens=400,
        model="gpt-4o",  # positioning quality matters most here; cost is already small (400 max tokens)
    )
    return _parse_json(response, {"angle": "", "fit_score": 0})


# ── Sample data for --test-email ────────────────────────────────────────────

SAMPLE_OPPORTUNITY = {
    "company": {
        "name": "Luma AI",
        "amount": "$43M",
        "stage": "Series B",
        "sector": "AI / generative video",
        "description": "AI-powered 3D and video generation for enterprises",
        "url": "https://lumalabs.ai",
    },
    "role": {
        "title": "Head of Strategy & Operations",
        "url": "https://jobs.ashbyhq.com/luma/sample",
        "location": "San Francisco, CA",
        "seniority": "Head",
    },
    "company_brief": {
        "product": "Luma builds generative AI tools for 3D scene capture and video synthesis, used by creative studios and enterprise product teams. Their Dream Machine model generates high-quality video from text and images.",
        "market": "Creative agencies, entertainment studios, and enterprise teams building product visualizations and marketing content.",
        "stage": "~80 people, post Series B",
        "traction": "$43M raised, partnerships with major studios, 2M+ users of Dream Machine in first month",
        "competitors": "Runway, Pika, Sora (OpenAI), Stability AI",
        "hiring_signals": "Scaling into enterprise GTM — need operationally rigorous leaders who can own the B2B motion",
        "investors": "Andreessen Horowitz, Nat Friedman, Daniel Gross",
        "recent_news": "Raised $43M Series B to expand enterprise offerings and international markets",
    },
    "role_analysis": {
        "core_need": "Someone to own the operating model for scaling enterprise — building the systems, processes, and partnerships that let the company grow beyond the founding team's bandwidth.",
        "key_skills": ["Enterprise GTM", "Operational infrastructure", "Cross-functional coordination", "Data-driven decision making", "Market expansion"],
        "stage_signals": "They're at the inflection point where product-led growth needs an operational layer to scale",
        "culture_signals": "Fast-moving, technical team — they'll want someone who can match their pace without adding bureaucracy",
        "growth_path": "COO or VP Operations within 18 months as company scales to Series C",
        "red_flags": "",
        "ideal_background": "An operator who has built GTM systems at a scaling AI company, ideally with enterprise experience and enough technical depth to work closely with the product team.",
    },
    "positioning": {
        "angle": "Luma is one of the few AI companies where the video generation product is mature enough to need real enterprise infrastructure — the operational scaling challenge, not the research one. This candidate's background running AI product operations at scale across multiple markets is a direct match for what this role actually requires.",
        "fit_score": 8,
    },
}


# ── Main orchestration ────────────────────────────────────────────────

def run(dry_run: bool = False, test_email: bool = False) -> None:
    print(f"\n{'='*60}")
    print(f"  WISE GLADE — {datetime.now().strftime('%B %d, %Y %I:%M %p')}")
    print(f"{'='*60}\n")

    if test_email:
        print("[test-email] Composing sample digest...")
        html = compose_html_email([SAMPLE_OPPORTUNITY], datetime.now())
        subject = f"[TEST] Wise Glade — {datetime.now().strftime('%B %d')}"
        if dry_run:
            print("[test-email] --dry-run active: would send test email but skipping")
            print(f"Subject: {subject}")
            print(f"HTML length: {len(html)} chars")
        else:
            send_email(html, subject=subject)
            print("[test-email] Sent. Check your inbox.")
        return

    # ── Path A: Recently funded companies ─────────────────────────────────
    print("[1/2] Discovering companies...")
    print("  [A] Searching for recently funded companies...")
    raw_funding_results = search_funded_companies()
    funded_companies = parse_funded_companies(raw_funding_results)
    print(f"       {len(funded_companies)} funded companies found")

    # ── Path B: Watchlist companies with new role postings ──────────────────────
    print("  [B] Scanning watchlist for new role postings...")
    watchlist_candidates = []
    for company_name, sector in WATCHLIST_COMPANIES.items():
        roles = find_watchlist_roles_structured(company_name)
        if roles is None:
            raw_job_results = find_watchlist_roles(company_name)
            roles = parse_job_listings(raw_job_results, company_name)
        if roles:
            print(f"       {company_name}: {len(roles)} new role(s)")
            watchlist_candidates.append({
                "company": {
                    "name": company_name,
                    "sector": sector,
                    "source": "watchlist",
                    "amount": "",
                    "stage": "",
                },
                "roles": roles,
            })

    # ── Merge: funded companies also need a job search; watchlist already has roles ──
    # Build a unified work queue: list of {company_dict, roles_or_None}
    work_queue = []
    for company in funded_companies:
        company["source"] = "funded"
        work_queue.append({"company": company, "roles": None})  # roles fetched below
    for entry in watchlist_candidates:
        work_queue.append({"company": entry["company"], "roles": entry["roles"]})

    if not work_queue:
        print("\n  No companies or new watchlist postings found today.")
        html = compose_html_email([], datetime.now())
        if not dry_run:
            send_email(html, subject=f"Wise Glade — No opportunities — {datetime.now().strftime('%B %d')}")
        return

    total = min(len(work_queue), MAX_COMPANIES_PER_RUN)
    opportunities = []

    print(f"\n[2/2] Researching {total} companies ({len(funded_companies)} funded + {len(watchlist_candidates)} watchlist)...\n")
    for i, entry in enumerate(work_queue[:MAX_COMPANIES_PER_RUN]):
        company = entry["company"]
        name = company.get("name", "Unknown")
        source = company.get("source", "funded")
        label = f"{company.get('stage','')} {company.get('amount','')}".strip() if source == "funded" else f"watchlist · {company.get('sector','')}"
        print(f"  [{i+1}/{total}] {name} ({label})")

        # Funded companies need a job search; watchlist roles were pre-fetched
        if entry["roles"] is not None:
            roles = entry["roles"]
        else:
            roles = find_open_roles_structured(name)
            if roles is None:
                raw_job_results = find_open_roles(name)
                roles = parse_job_listings(raw_job_results, name)

        if not roles:
            print(f"       No matching roles found — skipping")
            continue
        print(f"       {len(roles)} role(s): {[r['title'] for r in roles[:3]]}")

        # Research the company
        raw_company_research = research_company_deep(name)
        company_brief = build_company_brief(name, raw_company_research)

        # For each role: analyze + position
        for role in roles[:MAX_ROLES_PER_COMPANY]:
            print(f"       Analyzing: {role['title']}")
            jd_text = role.get("content") or fetch_job_description(role.get("url", ""))
            if not jd_text:
                jd_text = f"Role: {role['title']} at {name}. No job description retrieved."

            role_analysis = analyze_role(jd_text, company_brief)
            positioning = generate_positioning(company, company_brief, role, role_analysis)
            fit = positioning.get("fit_score", 0)
            print(f"       Fit: {fit}/10")

            if fit >= MIN_FIT_SCORE_TO_INCLUDE:
                opportunities.append({
                    "company": company,
                    "role": role,
                    "company_brief": company_brief,
                    "role_analysis": role_analysis,
                    "positioning": positioning,
                })

    # Sort by fit score descending
    opportunities.sort(key=lambda x: x["positioning"].get("fit_score", 0), reverse=True)

    print(f"\n{len(opportunities)} opportunities above fit threshold ({MIN_FIT_SCORE_TO_INCLUDE}/10)")

    html = compose_html_email(opportunities, datetime.now())
    subject = f"Wise Glade — {len(opportunities)} opportunit{'y' if len(opportunities) == 1 else 'ies'} — {datetime.now().strftime('%B %d')}"

    if dry_run:
        print("\n[dry-run] Digest summary (email not sent):")
        print("─" * 60)
        for opp in opportunities:
            print(f"\n  {opp['company']['name']} • {opp['role']['title']}")
            print(f"  Fit: {opp['positioning'].get('fit_score')}/10")
            angle = opp['positioning'].get('angle', '')
            if angle:
                print(f"  {angle[:140]}...")
        print(f"\n[dry-run] Subject would be: {subject}")
    else:
        send_email(html, subject=subject)
        print(f"[done] Email sent: {subject}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Wise Glade — Daily job intelligence agent")
    parser.add_argument("--dry-run", action="store_true", help="Run full pipeline, print digest, skip email")
    parser.add_argument("--test-email", action="store_true", help="Send a test email with sample data")
    args = parser.parse_args()
    run(dry_run=args.dry_run, test_email=args.test_email)


if __name__ == "__main__":
    main()
