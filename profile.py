"""
profile.py — example candidate profile for positioning context (template).
This is injected into every LLM positioning call so output is specific, not generic.

This file ships with fictional example content so the repo is safe to fork/share publicly.
To run the agent with YOUR real background without committing it anywhere public:
  1. Copy this file to profile_local.py (already in .gitignore, so it never gets committed)
  2. Replace CANDIDATE_PROFILE below with your own background
agent.py automatically prefers profile_local.py when it exists, falling back to this
template otherwise — so a fresh clone works out of the box with example output, and your
real profile stays local to your machine (or wired in via a CI secret — see README).
"""

CANDIDATE_PROFILE = """
# Example Candidate — Career Profile & Positioning Context
[This is a placeholder. Replace this entire block with your own background in profile_local.py.]

## Summary
Operator-builder turning ambiguous problems into shipped products and closed partnerships.
X years across product, growth, and [your domain], most recently leading [your current focus]
at [Current Company].

## Background

### Current Company — [what they do, scale/stage]
[City] · [Your Title] ([Start]–Now)
- [Achievement with a concrete, measurable outcome — e.g. "Led X initiative, growing Y by Z%"]
- [Achievement showing both the build and the relationship/commercial side]
- [Achievement with a specific metric — reviewers trust numbers over adjectives]

### Prior Company — [what they do]
[Title] ([Dates])
- [One or two concrete outcomes]

### Education
[University] — [Degree], [Honors if relevant] ([Year])

## Capabilities
- [Skill area 1]: [specific tools/techniques]
- [Skill area 2]: [specific tools/techniques]
- [Skill area 3]: [specific tools/techniques]

## Differentiated Angles — Use These Specifically
List 3-5 things that make you a non-generic candidate. Be concrete — name the project, the
metric, the thing you personally built or closed, not just the job title.

1. [ANGLE NAME]
   - [Why this is true, with specifics]

2. [ANGLE NAME]
   - [Why this is true, with specifics]

## Targeting
- Roles: [the role families you actually want]
- Stage: [company stage preference]
- Ideal company: [what makes a company worth your time]
"""
