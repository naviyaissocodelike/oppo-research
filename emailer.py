"""
emailer.py — HTML email composer and Gmail SMTP sender.
Lean cards: role + company brief + 1-2 line positioning angle.
"""

import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def compose_html_email(opportunities: list[dict], run_date: datetime) -> str:
    """Build the full HTML email digest from a list of opportunities."""
    date_str = run_date.strftime("%B %d, %Y")
    count = len(opportunities)

    cards_html = ""
    for opp in opportunities:
        company = opp["company"]
        role = opp["role"]
        brief = opp["company_brief"]
        analysis = opp["role_analysis"]
        pos = opp["positioning"]

        job_url = role.get("url", "#")
        location_str = role.get("location", "")
        location_suffix = f" · {location_str}" if location_str and location_str not in ("Unknown", "") else ""

        source = company.get("source", "funded")
        if source == "watchlist":
            company_meta = company.get("sector", "")
        else:
            parts = [x for x in [company.get("stage", ""), company.get("amount", ""), company.get("sector", "")] if x]
            company_meta = " · ".join(parts)

        source_badge = (
            '<span style="font-size:11px; background:#e0e7ff; color:#6366f1; padding:2px 8px; border-radius:10px; font-weight:600; margin-left:8px;">NEW FUNDING</span>'
            if source == "funded"
            else '<span style="font-size:11px; background:#f3f4f6; color:#6b7280; padding:2px 8px; border-radius:10px; font-weight:600; margin-left:8px;">WATCHLIST</span>'
        )

        company_snapshot = brief.get("product", "")
        investors = brief.get("investors", "")
        angle = pos.get("angle", "")

        cards_html += f"""
        <div style="background:white; border:1px solid #e5e7eb; border-radius:10px; padding:22px 24px; margin-bottom:16px;">

          <!-- Company + role header -->
          <div style="margin-bottom:12px;">
            <div style="font-size:17px; font-weight:700; color:#111827; margin-bottom:3px;">
              {company['name']}{source_badge}
            </div>
            <div style="font-size:12px; color:#9ca3af;">{company_meta}</div>
          </div>

          <!-- Role -->
          <div style="margin-bottom:14px;">
            <a href="{job_url}" style="font-size:14px; font-weight:600; color:#6366f1; text-decoration:none;">
              {role['title']}{location_suffix} →
            </a>
            {f'<div style="font-size:13px; color:#6b7280; margin-top:4px; line-height:1.5;">{analysis.get("core_need", "")}</div>' if analysis.get("core_need") else ""}
          </div>

          <!-- Company brief -->
          <div style="font-size:13px; color:#374151; line-height:1.65; margin-bottom:{'12px' if angle else '0'};">{company_snapshot}{f' <span style="color:#9ca3af;">· {investors}</span>' if investors else ""}</div>

          <!-- Positioning angle -->
          {f'<div style="font-size:13px; color:#6b7280; line-height:1.65; border-top:1px solid #f3f4f6; padding-top:12px; font-style:italic;">{angle}</div>' if angle else ""}

        </div>
        """

    no_results_html = '<div style="text-align:center; color:#6b7280; padding:48px 24px; font-size:14px;">No new opportunities found today — check back tomorrow.</div>'

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:0; background:#f3f4f6; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;">
  <div style="max-width:640px; margin:0 auto; padding:28px 16px;">

    <!-- Header -->
    <div style="text-align:center; margin-bottom:36px;">
      <div style="font-size:26px; font-weight:800; color:#111827; letter-spacing:-0.5px;">Oppo Research</div>
      <div style="font-size:14px; color:#6b7280; margin-top:6px;">
        {date_str} &nbsp;·&nbsp; {count} opportunit{'y' if count == 1 else 'ies'} found
      </div>
    </div>

    {cards_html if opportunities else no_results_html}

    <!-- Footer -->
    <div style="text-align:center; font-size:12px; color:#9ca3af; margin-top:28px; line-height:1.6;">
      Oppo Research &nbsp;·&nbsp; Automated job intelligence
    </div>

  </div>
</body>
</html>"""


def send_email(html: str, subject: str) -> None:
    """Send an HTML email via Gmail SMTP using an App Password."""
    gmail_from = os.environ.get("GMAIL_FROM")
    gmail_to = os.environ.get("GMAIL_TO")
    gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not all([gmail_from, gmail_to, gmail_app_password]):
        raise ValueError(
            "Missing email credentials. Set GMAIL_FROM, GMAIL_TO, GMAIL_APP_PASSWORD in .env\n"
            "Get an App Password at: https://myaccount.google.com/apppasswords"
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_from
    msg["To"] = gmail_to
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(gmail_from, gmail_app_password)
        smtp.sendmail(gmail_from, gmail_to, msg.as_string())
