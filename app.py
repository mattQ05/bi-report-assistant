import base64
import io
import os
import subprocess
import sys

import streamlit as st
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image


# ============================================================
# Page setup
# ============================================================
st.set_page_config(
    page_title="BI Report Assistant",
    page_icon=":bar_chart:",
    layout="wide",
)

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")

try:
    api_key = api_key or st.secrets.get("OPENAI_API_KEY")
except Exception:
    pass

if not api_key:
    st.error(
        "Missing OpenAI API key. Add OPENAI_API_KEY to your local .env file or Streamlit Cloud secrets."
    )
    st.stop()

client = OpenAI(api_key=api_key)


# ============================================================
# Build configuration
# ============================================================
# Set to True for Streamlit Cloud deployments (no local Power BI connection).
# Set to False for local/desktop builds where Power BI External Tools is available.
CLOUD_MODE: bool = os.getenv("BI_ASSISTANT_CLOUD", "false").lower() == "true"

# Maximum characters of context sent to the model. Surfaced visibly to the user.
MAX_CONTEXT_CHARS: int = 8_000


# ============================================================
# App configuration
# ============================================================
ASSISTANT_MODES = [
    "Dashboard Review",
    "Model Review",
    "DAX Debugging",
    "Measure Generator",
    "Insight Writer",
    "README Writer",
]

MODE_ICONS = {
    "Dashboard Review":  "◫",
    "Model Review":      "⬡",
    "DAX Debugging":     "⟨/⟩",
    "Measure Generator": "∑",
    "Insight Writer":    "◎",
    "README Writer":     "☰",
}

MODE_DESCRIPTIONS = {
    "Dashboard Review": "Review dashboard layout, spacing, visuals, labels, and readiness.",
    "Model Review": "Review Power BI model structure, tables, columns, measures, and relationships.",
    "DAX Debugging": "Check DAX syntax, logic, references, and cleaner calculation patterns.",
    "Measure Generator": "Suggest useful DAX measures based on your schema and existing measures.",
    "Insight Writer": "Turn dashboard metrics into executive-friendly business insights.",
    "README Writer": "Generate a polished GitHub README for your Power BI project.",
}

DEFAULT_QUESTIONS = {
    "Dashboard Review": "Can you review my dashboard and tell me what looks good, what looks off, and what I should fix before sharing it?",
    "Model Review": "Can you review my Power BI model structure and tell me what looks good, what needs improvement, and how I can make it cleaner?",
    "DAX Debugging": "Can you check my DAX measures, fix any issues, and explain what I should change?",
    "Measure Generator": "What other useful DAX measures should I add to this report?",
    "Insight Writer": "Can you write the main business insights from this dashboard?",
    "README Writer": "Can you write a professional GitHub README for this Power BI dashboard project?",
}

PROMPT_LIBRARY = {
    "Dashboard Review": {
        "Review layout": "Can you review the dashboard layout, spacing, alignment, and visual hierarchy?",
        "Portfolio readiness": "Is this dashboard ready to include in a portfolio? What should I fix first?",
        "Top visual fixes": "What are the top 5 visual improvements I should make to this dashboard?",
        "Executive polish": "How can I make this dashboard look more professional for stakeholders or executives?",
    },
    "Model Review": {
        "Review model": "Can you review my connected Power BI model and tell me what looks good and what needs improvement?",
        "Find model issues": "Based on the connected model context, what model structure issues should I fix?",
        "Star schema advice": "Does this model look like it would benefit from a star schema? Explain what should change.",
        "Measure organization": "How should I organize, rename, or improve the measures in this Power BI model?",
    },
    "DAX Debugging": {
        "Check DAX": "Can you check my DAX measures for syntax, logic, and naming issues?",
        "Improve measures": "Can you improve these DAX measures and explain what changed?",
        "Explain DAX": "Can you explain what each DAX measure is doing in plain English?",
        "Find risky logic": "Are there any risky calculations, missing DIVIDE patterns, or unclear business definitions in my measures?",
    },
    "Measure Generator": {
        "Suggest KPIs": "What useful KPI measures should I add based on the provided model context?",
        "Generate measures": "Suggest 5 practical DAX measures I can add without inventing new columns or tables.",
        "Ratios and margins": "What ratio, percentage, margin, or efficiency measures would be useful for this dataset?",
        "Dashboard cards": "Which measures would make the best KPI cards for this report?",
    },
    "Insight Writer": {
        "Write insights": "Can you write the main business insights from this dashboard?",
        "Executive summary": "Write a short executive summary based on the dashboard and provided context.",
        "Business questions": "What business questions can this dashboard help answer?",
        "Dashboard callouts": "Write 3 short dashboard callout sentences I could place directly on the report.",
    },
    "README Writer": {
        "Create README": "Can you write a professional GitHub README for this Power BI dashboard project?",
        "Portfolio description": "Can you write a portfolio-friendly project description for this dashboard?",
        "Skills section": "Can you write the skills showcased section for this Power BI project?",
        "Project summary": "Can you summarize this project for GitHub and LinkedIn?",
    },
}

OUTPUT_TITLES = {
    "Dashboard Review": "Dashboard Review",
    "Model Review": "Model Review",
    "DAX Debugging": "DAX Review",
    "Measure Generator": "Suggested Measures",
    "Insight Writer": "Business Insights",
    "README Writer": "Generated README",
}

SAMPLE_SCHEMA = """Project: Business Performance Dashboard

Dataset:
Sample/anonymized business performance data with monthly metrics across departments, categories, or business units.

Table: business_performance_data

Columns:
Date - Date
Business Unit - Text
Category - Text
Region - Text
Revenue - Currency
Cost - Currency
Operating Expense - Currency
Customer Count - Whole Number
Target Revenue - Currency

Existing Measures:
Total Revenue
Total Cost
Total Operating Expense
Total Profit
Profit Margin %
Expense % of Revenue
Revenue vs Target
Target Achievement %
"""

SAMPLE_DAX = """Total Revenue =
SUM(business_performance_data[Revenue])

Total Cost =
SUM(business_performance_data[Cost])

Total Operating Expense =
SUM(business_performance_data[Operating Expense])

Total Profit =
[Total Revenue] - [Total Cost] - [Total Operating Expense]

Profit Margin % =
DIVIDE([Total Profit], [Total Revenue])

Expense % of Revenue =
DIVIDE([Total Operating Expense], [Total Revenue])

Revenue vs Target =
[Total Revenue] - SUM(business_performance_data[Target Revenue])

Target Achievement % =
DIVIDE([Total Revenue], SUM(business_performance_data[Target Revenue]))
"""


SYSTEM_PROMPT = """
You are a senior Power BI consultant helping users improve dashboards, data models, DAX, business insights, and documentation.

The selected assistant mode defines your job for this response. Follow it precisely.

You may receive a screenshot, schema, DAX measures, a connected model context, or a plain question. Work only with what is provided. Do not assume industry, company, or dataset type unless explicitly stated.

Formatting rules:
- Write in clear, direct prose. Be specific — reference actual table names, column names, measure names, and visible chart titles from the provided context.
- Use ## headers to separate major sections. Use **bold** for specific element names, recommendations, and key findings.
- Use bullet points for lists of findings or steps. Use numbered lists only for ranked or sequential items.
- All DAX must be in fenced code blocks marked ```DAX. Never use inline backticks for DAX.
- Never wrap plain text, metric values, chart names, or business terms in backticks.
- Be concise. Skip preamble. Lead with what matters most.
"""

FOLLOW_UP_INSTRUCTIONS = """
You are answering a follow-up question based on the previous response provided.

Answer the user's new question directly. Do not restate the previous response or repeat its structure.

If the user asks to shorten, rewrite, explain, expand, rank, or transform something from the previous response, do exactly that and nothing else.

Match the format to what the question actually needs — not the default format of the original mode.
"""

MODE_PROMPTS = {
    "Dashboard Review": """
You are in Dashboard Review mode. Review the uploaded Power BI dashboard screenshot as a senior BI consultant would before a client presentation.

If no screenshot is provided, say clearly that a screenshot is required for this mode and stop. Do not attempt a generic review.

Lead with the most important finding — if there is one glaring problem, say so first. Do not bury critical issues in a balanced structure.

Evaluate only what is visible:
- Visual hierarchy and layout — does the eye land in the right place?
- KPI cards — are values, labels, and units readable at a glance?
- Chart titles — are they descriptive or just field names?
- Color usage — consistent, purposeful, or distracting?
- Spacing and alignment — does it look intentional or accidental?
- Slicers and filters — are they clearly labeled and positioned logically?
- Readability — would this hold up on a projected screen or in a PDF?

Do not comment on DAX, schema, or data quality unless asked.

Structure your response as follows:

## Status
One of: **Ready to share** / **Needs minor polish** / **Needs rework** — followed by one sentence explaining why.

## What works
Bullet the specific elements that are genuinely strong. Be precise — name the actual charts, cards, or layout choices.

## What to fix
List issues in priority order, most impactful first. For each one, say what it is, why it matters, and what to do about it. Do not pad this list — if there are 2 real issues, say 2.

## Before you share
End with 2–3 sentences of direct advice on the single most important thing to address before publishing or presenting this dashboard.
""",

    "Model Review": """
You are in Model Review mode. Review the Power BI data model using the provided context — connected model metadata, pasted schema, or both.

If the connected model context is available, use it as the primary source. Pasted schema is supplementary.

Do not invent tables, columns, relationships, or measures that are not in the provided context. If relationships are missing, note it but do not assume it is a mistake — some models intentionally have no relationships.

Use careful language when inferring design intent: "appears to", "suggests", "based on the provided context".

Prioritise findings by impact. A missing Date table or a flat table structure that should be dimensional matters more than a slightly unclear column name. Lead with the highest-impact issues.

Evaluate:
- Table structure — flat, dimensional, or star schema?
- Relationships — present, missing, or ambiguous direction?
- Column naming — clear to a business user or raw field names?
- Measure naming and organisation — logical grouping, display folders, base vs derived measures?
- Hidden auto-generated tables — are Power BI's auto date/time tables present and should they be disabled?
- Date table — is one present, and is it needed?

## Model summary
Briefly state what the model contains: number of tables, key columns, measures, and relationships. This gives the user confidence you read the context correctly.

## Priority findings
List the most impactful issues first. For each one: name it, explain why it matters in practice, and give a concrete recommendation. Skip minor cosmetic issues unless nothing significant exists.

## What is working well
Note genuine strengths — good naming conventions, clean relationships, well-structured measures. Be specific.

## DAX and measures
Practical notes on measure quality, naming consistency, missing base measures, DIVIDE patterns, and whether display folders would help.

## Verdict
One of: **Production ready** / **Usable, improvements recommended** / **Needs restructuring** — followed by 2 sentences explaining the key reason.
""",

    "DAX Debugging": """
You are in DAX Debugging mode. Review the provided DAX measures and find real problems — syntax errors, incorrect column or measure references, logic that does not match its name, missing DIVIDE patterns, or filter context issues.

Do not assume the dataset is about any specific industry. Use the actual table names, column names, and measure names provided to understand the context.

If multiple measures are provided, work through all of them. Group related issues together rather than repeating the same 4-section structure for every single measure.

For each issue found:
- Name the measure and state the problem precisely
- Explain why it is wrong or risky — what incorrect result would it produce?
- Show the corrected version in a DAX code block
- Give a one-line tip for verifying it works in Power BI

If a measure uses DIVIDE, note whether the alternate result (0 vs BLANK) is appropriate for the intended use — 0 is better for visuals that should show zero, BLANK is better when zero would be misleading.

If no real issues are found, say so directly. Do not invent minor issues to fill the response.

Structure:

## Summary
State how many measures were reviewed and whether any issues were found. If clean, say so here and keep the rest brief.

## Issues found
For each issue, use a clear subheading with the measure name. Explain the problem, show the fix, and explain how to verify.

## Patterns to watch
End with any recurring patterns across the measures — things that are technically working but could cause problems at scale or are worth standardising.
""",

    "Measure Generator": """
You are in Measure Generator mode. Suggest practical DAX measures based strictly on the provided schema and existing measures.

Use the exact table and column names from the provided context. Do not invent column names or assume columns exist that were not provided.

Do not suggest measures that duplicate what already exists unless you are offering a meaningfully better version — and if so, say why it is better.

Do not produce a taxonomy of categories. Produce a prioritised list of measures the user should actually add, ordered by usefulness. Quality over quantity.

For time intelligence: only write complete time-intelligence DAX if a proper Date table is present in the schema. If only a date column exists in a fact table, explain that a dedicated Date table is needed and show what the measure would look like once one exists — do not pretend the measure is ready to use.

Each measure must follow this format exactly:

```DAX
Measure Name =
DAX expression
```

Followed immediately by one sentence explaining what it measures and when to use it.

Structure:

## Measures to add now
The 3–6 most immediately useful measures given the current schema. These must be ready to copy and paste — no placeholders, no assumed columns.

## Measures worth adding next
Secondary measures that add value but are less urgent, or depend on the measures above being in place first.

## What would unlock more
If a Date table, a Targets table, or another missing element would enable significantly better analytics, explain what it would unlock and why it is worth building. Keep this brief and practical.
""",

    "Insight Writer": """
You are in Insight Writer mode. Write business insights from the provided dashboard screenshot, schema, DAX measures, and visible metrics.

Your job is business interpretation, not design critique. Write as a business analyst presenting findings to a stakeholder — confident, clear, and grounded in what the data actually shows.

Work only from what is visible or explicitly provided. When reading from a screenshot, use language like "shows", "indicates", or "suggests" — do not overstate certainty. Never invent numbers or trends that are not visible.

Do not treat every KPI card as an average unless the label says average. Read the label.

Lead with the most significant finding. If one number or trend dominates the story, say that first.

## The headline
One sentence — the single most important thing this dashboard tells you. Write it as a business finding, not a data description.

## Key insights
3–5 specific insights in priority order. For each one: what the data shows, what it means for the business, and — where visible — what is driving it. Bold the specific metric or dimension name being referenced.

## Suggested actions
2–3 concrete recommendations that follow logically from the insights. Be specific about who should act and what they should do — not generic advice.

## Dashboard callout
One short sentence suitable for placing directly on the Power BI report as a text box or subtitle. Should be punchy and self-contained.
""",

    "README Writer": """
You are in README Writer mode. Write a professional GitHub README for a Power BI dashboard project.

Return only the README content as clean Markdown. No preamble, no explanation, no fenced code block wrapper — just the Markdown itself starting with the # title.

Write in a professional but human tone. Avoid filler phrases like "this project aims to" or "leveraging the power of". Say what the dashboard does and why it is useful.

Do not claim features, tools, schema complexity, or modeling techniques that were not provided. If something is unknown, write it generically or mark it as a placeholder with [square brackets].

If the context suggests real company data, internal systems, or identifiable individuals, include a data disclaimer recommending anonymised or sample data for public sharing.

Use only what was provided — screenshot, schema, measures, model context, and the user's description — to write specific, accurate content.

Structure:

# [Project Title]

A one-paragraph introduction: what the dashboard shows, who it is for, and what decisions it supports.

## Dashboard Preview
![Dashboard Preview](images/dashboard_preview.png)

## Features
Bullet the specific visuals, interactions, and analytical capabilities visible or described. Be concrete — name the actual charts and KPIs.

## Data Model
Briefly describe the tables, key columns, and relationships. If only a single table exists, say so.

## DAX Measures
List the key measures with a one-line description of each. Group by type if there are many.

## Tools and Skills
- Tools used (Power BI Desktop, DAX, Power Query, etc.)
- Skills demonstrated (data modelling, time intelligence, UX design, etc.)

## Data Source
Describe the data source or note that sample/anonymised data was used.

## Future Improvements
2–3 specific things that would make the dashboard more powerful — not generic wishes, but things grounded in what the current model is missing.
""",
}


# ============================================================
# Styling
# ============================================================
def apply_custom_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        /* ── Design tokens ── */
        :root {
            --bg-base:      #080C14;
            --bg-surface:   #0E1420;
            --bg-raised:    #141C2E;
            --bg-hover:     #1A2338;
            --border:       #1E2A40;
            --border-light: #243048;
            --accent:       #4F8EF7;
            --accent-dim:   rgba(79, 142, 247, 0.12);
            --accent-glow:  rgba(79, 142, 247, 0.22);
            --green:        #34D399;
            --green-dim:    rgba(52, 211, 153, 0.10);
            --text-primary: #F0F4FF;
            --text-secondary: #7B8BAA;
            --text-muted:   #4A566E;
            --radius-sm:    6px;
            --radius-md:    10px;
            --radius-lg:    14px;
        }

        /* ── Base ── */
        html, body, .stApp {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--bg-base) !important;
            color: var(--text-primary) !important;
        }

        .block-container {
            max-width: 1280px !important;
            padding: 0 2rem 4rem 2rem !important;
        }

        /* hide default streamlit header chrome */
        header[data-testid="stHeader"] { background: transparent !important; }
        #MainMenu, footer { display: none !important; }

        /* ── Typography ── */
        h1, h2, h3, h4 {
            font-family: 'Inter', sans-serif;
            letter-spacing: -0.02em;
            color: var(--text-primary);
        }

        /* ── App topbar ── */
        .topbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 18px 0 18px 0;
            border-bottom: 1px solid var(--border);
            margin-bottom: 28px;
        }

        .topbar-brand {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .topbar-logo {
            width: 34px;
            height: 34px;
            border-radius: var(--radius-sm);
            background: var(--accent);
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }

        .topbar-logo svg {
            width: 18px;
            height: 18px;
            fill: #fff;
        }

        .topbar-name {
            font-size: 15px;
            font-weight: 600;
            color: var(--text-primary);
            letter-spacing: -0.01em;
        }

        .topbar-divider {
            width: 1px;
            height: 18px;
            background: var(--border-light);
        }

        .topbar-product {
            font-size: 13px;
            color: var(--text-secondary);
            font-weight: 400;
        }

        .topbar-right {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 12px;
            font-weight: 500;
            color: var(--text-secondary);
            border: 1px solid var(--border-light);
            border-radius: 999px;
            padding: 5px 11px;
            background: var(--bg-surface);
        }

        .status-dot {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: var(--green);
            box-shadow: 0 0 6px var(--green);
            flex-shrink: 0;
        }

        /* ── Pipeline steps ── */
        .pipeline {
            display: flex;
            align-items: center;
            gap: 0;
            margin-bottom: 28px;
            background: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 0;
            overflow: hidden;
        }

        .pipeline-step {
            display: flex;
            align-items: center;
            gap: 8px;
            flex: 1;
            padding: 11px 16px;
            font-size: 12px;
            font-weight: 500;
            color: var(--text-muted);
            border-right: 1px solid var(--border);
            transition: background 0.15s;
        }

        .pipeline-step:last-child { border-right: none; }

        .pipeline-step.active {
            color: var(--text-primary);
            background: var(--bg-raised);
        }

        .pipeline-step.active .pipeline-num {
            background: var(--accent);
            color: #fff;
            border-color: var(--accent);
        }

        .pipeline-num {
            width: 20px;
            height: 20px;
            border-radius: 50%;
            border: 1px solid var(--border-light);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 10px;
            font-weight: 600;
            flex-shrink: 0;
            color: var(--text-muted);
        }

        /* ── Section labels ── */
        .section-label {
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.07em;
            text-transform: uppercase;
            color: var(--text-muted);
            margin-bottom: 10px;
        }

        /* ── Connected model card ── */
        .model-card {
            background: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: 16px;
            margin-bottom: 12px;
        }

        .model-card-header {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 14px;
        }

        .model-card-title {
            font-size: 13px;
            font-weight: 600;
            color: var(--text-primary);
        }

        .model-card-sub {
            font-size: 11px;
            color: var(--text-secondary);
            margin-top: 1px;
        }

        .live-dot {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: var(--green);
            box-shadow: 0 0 8px var(--green);
            flex-shrink: 0;
        }

        .model-stats {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 8px;
        }

        .model-stat {
            background: var(--bg-raised);
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            padding: 10px 12px;
            text-align: center;
        }

        .model-stat-value {
            font-size: 22px;
            font-weight: 700;
            color: var(--text-primary);
            font-variant-numeric: tabular-nums;
            letter-spacing: -0.02em;
        }

        .model-stat-label {
            font-size: 10px;
            font-weight: 500;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-top: 2px;
        }

        /* ── Mode selector tabs ── */
        .mode-tabs {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 6px;
            margin-bottom: 16px;
        }

        .mode-tab {
            padding: 9px 10px;
            background: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            font-size: 12px;
            font-weight: 500;
            color: var(--text-secondary);
            cursor: pointer;
            text-align: center;
            transition: all 0.15s;
        }

        .mode-tab.selected {
            background: var(--accent-dim);
            border-color: var(--accent);
            color: var(--accent);
            font-weight: 600;
        }

        /* ── Mode description ── */
        .mode-desc {
            font-size: 12px;
            color: var(--text-secondary);
            background: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            padding: 10px 12px;
            margin-bottom: 14px;
            line-height: 1.5;
        }

        /* ── Prompt library ── */
        .prompt-lib-label {
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            color: var(--text-muted);
            margin-bottom: 8px;
        }

        /* ── Output card ── */
        .output-card {
            background: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: 28px 32px;
            margin-top: 6px;
        }

        .output-header {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border);
        }

        .output-title {
            font-size: 20px;
            font-weight: 700;
            letter-spacing: -0.02em;
            color: var(--text-primary);
        }

        .output-mode-pill {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            font-size: 11px;
            font-weight: 500;
            color: var(--accent);
            background: var(--accent-dim);
            border: 1px solid rgba(79,142,247,0.25);
            border-radius: 999px;
            padding: 4px 10px;
            margin-top: 6px;
        }

        /* ── History ── */
        .history-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 12px;
        }

        .history-title {
            font-size: 13px;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.06em;
        }

        /* ── Streamlit widget overrides ── */

        /* Text areas */
        .stTextArea textarea {
            border-radius: var(--radius-md) !important;
            border: 1px solid var(--border-light) !important;
            background-color: var(--bg-surface) !important;
            color: var(--text-primary) !important;
            font-family: 'Inter', sans-serif !important;
            font-size: 13px !important;
            padding: 12px 14px !important;
            box-shadow: none !important;
            resize: vertical;
        }

        .stTextArea textarea:focus {
            border-color: var(--accent) !important;
            box-shadow: 0 0 0 2px var(--accent-glow) !important;
        }

        /* Select box */
        div[data-baseweb="select"] > div {
            border-radius: var(--radius-md) !important;
            background-color: var(--bg-surface) !important;
            border: 1px solid var(--border-light) !important;
            color: var(--text-primary) !important;
            font-size: 13px !important;
        }

        /* File uploader */
        section[data-testid="stFileUploader"] {
            background-color: var(--bg-surface);
            border: 1px dashed var(--border-light);
            border-radius: var(--radius-md);
        }

        section[data-testid="stFileUploader"]:hover {
            border-color: var(--accent);
        }

        /* Buttons — default */
        div.stButton > button {
            border-radius: var(--radius-sm) !important;
            font-weight: 500 !important;
            font-size: 13px !important;
            font-family: 'Inter', sans-serif !important;
            border: 1px solid var(--border-light) !important;
            background: var(--bg-raised) !important;
            color: var(--text-secondary) !important;
            padding: 8px 16px !important;
            transition: border-color 0.15s, color 0.15s !important;
            box-shadow: none !important;
        }

        div.stButton > button:hover {
            border-color: var(--accent) !important;
            color: var(--text-primary) !important;
        }

        /* Primary CTA button — "Analyze Report" */
        div.stButton > button[kind="primary"],
        div[data-testid="stBaseButton-primary"] > button {
            background: var(--accent) !important;
            border-color: var(--accent) !important;
            color: #fff !important;
            font-weight: 600 !important;
        }

        div.stButton > button[kind="primary"]:hover {
            background: #6B9FFF !important;
            border-color: #6B9FFF !important;
        }

        /* Download button */
        div.stDownloadButton > button {
            border-radius: var(--radius-sm) !important;
            font-weight: 500 !important;
            font-size: 13px !important;
            border: 1px solid var(--border-light) !important;
            background: var(--bg-raised) !important;
            color: var(--text-secondary) !important;
            transition: border-color 0.15s, color 0.15s !important;
        }

        div.stDownloadButton > button:hover {
            border-color: var(--accent) !important;
            color: var(--text-primary) !important;
        }

        /* Expander */
        div[data-testid="stExpander"] {
            border: 1px solid var(--border) !important;
            border-radius: var(--radius-md) !important;
            background: var(--bg-surface) !important;
        }

        div[data-testid="stExpander"] summary {
            font-size: 13px !important;
            font-weight: 500 !important;
            color: var(--text-secondary) !important;
        }

        /* Container with border */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--bg-surface);
            border: 1px solid var(--border) !important;
            border-radius: var(--radius-lg) !important;
            padding: 20px !important;
            box-shadow: none !important;
        }

        /* Image wrapper */
        div[data-testid="stImage"] {
            background: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: 12px;
        }

        div[data-testid="stImage"] img {
            border-radius: var(--radius-md) !important;
        }

        /* Checkbox */
        label[data-testid="stCheckbox"] {
            font-size: 13px !important;
            color: var(--text-secondary) !important;
        }

        /* Caption / small text */
        .stCaption, div[data-testid="stCaptionContainer"] p {
            color: var(--text-secondary) !important;
            font-size: 12px !important;
        }

        /* Divider */
        hr { border-color: var(--border) !important; }

        /* Info/success/warning boxes */
        div[data-testid="stAlert"] {
            border-radius: var(--radius-md) !important;
            font-size: 13px !important;
        }

        /* Subheader */
        div[data-testid="stHeadingWithActionElements"] h2,
        .stSubheader {
            font-size: 14px !important;
            font-weight: 600 !important;
            color: var(--text-secondary) !important;
            letter-spacing: 0 !important;
            text-transform: none !important;
        }

        /* Spinner */
        div[data-testid="stSpinner"] p {
            font-size: 13px !important;
            color: var(--text-secondary) !important;
        }

        /* Code blocks */
        pre, code {
            font-size: 12.5px !important;
            border-radius: var(--radius-sm) !important;
        }

        /* Scrollbar */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: var(--bg-base); }
        ::-webkit-scrollbar-thumb { background: var(--border-light); border-radius: 3px; }

        /* ── Markdown output inside st.markdown ── */
        .element-container .stMarkdown h2 {
            font-size: 15px !important;
            font-weight: 600 !important;
            color: var(--text-primary) !important;
            border-bottom: 1px solid var(--border) !important;
            padding-bottom: 6px !important;
            margin-top: 22px !important;
            margin-bottom: 10px !important;
        }

        .element-container .stMarkdown h3 {
            font-size: 13px !important;
            font-weight: 600 !important;
            color: var(--text-secondary) !important;
            margin-top: 16px !important;
        }

        .element-container .stMarkdown p,
        .element-container .stMarkdown li {
            font-size: 13.5px !important;
            line-height: 1.65 !important;
            color: #C4CEDF !important;
        }

        /* ── Mode grid ── */
        .mode-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 6px;
            margin-bottom: 14px;
        }

        .mode-grid-item {
            background: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            padding: 10px 8px 8px 8px;
            cursor: pointer;
            text-align: center;
            transition: border-color 0.15s, background 0.15s;
        }

        .mode-grid-item:hover {
            border-color: var(--border-light);
            background: var(--bg-raised);
        }

        .mode-grid-item.selected {
            background: var(--accent-dim);
            border-color: var(--accent);
        }

        .mode-grid-icon {
            font-size: 16px;
            line-height: 1;
            margin-bottom: 5px;
            color: var(--text-secondary);
        }

        .mode-grid-item.selected .mode-grid-icon {
            color: var(--accent);
        }

        .mode-grid-name {
            font-size: 10px;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.04em;
            line-height: 1.3;
        }

        .mode-grid-item.selected .mode-grid-name {
            color: var(--accent);
        }

        /* ── Follow-up button variant ── */
        div.stButton > button.followup-btn {
            border-color: var(--border-light) !important;
            color: var(--text-secondary) !important;
        }

        /* ── Schema / DAX prominence in cloud mode ── */
        .cloud-input-label {
            font-size: 12px;
            font-weight: 600;
            color: var(--text-secondary);
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        /* ── Demo banner ── */
        .demo-banner {
            background: var(--accent-dim);
            border: 1px solid rgba(79,142,247,0.25);
            border-radius: var(--radius-sm);
            padding: 10px 14px;
            font-size: 12px;
            color: var(--accent);
            font-weight: 500;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        /* ── Active context summary ── */
        .ctx-summary {
            background: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 10px 14px;
            margin-bottom: 14px;
        }
        .ctx-label {
            font-size: 10px;
            font-weight: 600;
            letter-spacing: 0.07em;
            text-transform: uppercase;
            color: var(--text-muted);
            margin-bottom: 6px;
        }
        .ctx-tags { display: flex; flex-wrap: wrap; gap: 6px; }
        .ctx-tag {
            font-size: 11px;
            font-weight: 500;
            padding: 3px 8px;
            border-radius: 4px;
        }
        .ctx-green {
            color: var(--green);
            background: var(--green-dim);
            border: 1px solid rgba(52,211,153,0.2);
        }
        .ctx-blue {
            color: var(--accent);
            background: var(--accent-dim);
            border: 1px solid rgba(79,142,247,0.2);
        }
        .ctx-nudge {
            font-size: 11px;
            color: var(--text-muted);
            font-style: italic;
            margin-top: 6px;
            display: block;
        }

        /* ── Confirm dialog ── */
        .confirm-dialog {
            background: var(--bg-raised);
            border: 1px solid #F87171;
            border-radius: var(--radius-md);
            padding: 14px 16px;
            margin-bottom: 10px;
        }
        .confirm-dialog-title {
            font-size: 13px;
            font-weight: 600;
            color: #F87171;
            margin-bottom: 4px;
        }
        .confirm-dialog-body {
            font-size: 12px;
            color: var(--text-secondary);
            margin-bottom: 10px;
        }

        /* ── Mode selector — radio styled as 3-column grid ── */

        /* Container: make the radio options sit in a 3-column grid */
        div[data-testid="stRadio"] > div {
            display: grid !important;
            grid-template-columns: repeat(3, 1fr) !important;
            gap: 6px !important;
        }

        /* Hide the actual radio circle */
        div[data-testid="stRadio"] input[type="radio"] {
            display: none !important;
        }

        /* Each option label — style as a card button */
        div[data-testid="stRadio"] label {
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            text-align: center !important;
            padding: 9px 6px !important;
            background: var(--bg-surface) !important;
            border: 1px solid var(--border) !important;
            border-radius: var(--radius-sm) !important;
            font-size: 11.5px !important;
            font-weight: 500 !important;
            color: var(--text-secondary) !important;
            cursor: pointer !important;
            transition: border-color 0.15s, color 0.15s, background 0.15s !important;
            line-height: 1.3 !important;
            min-height: 38px !important;
        }

        div[data-testid="stRadio"] label:hover {
            border-color: var(--accent) !important;
            color: var(--text-primary) !important;
        }

        /* Selected option */
        div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked),
        div[data-testid="stRadio"] div[role="radiogroup"] > label:has(input[type="radio"]:checked) {
            background: var(--accent-dim) !important;
            border-color: var(--accent) !important;
            color: var(--accent) !important;
            font-weight: 600 !important;
        }

        /* Hide the radio label markdown wrapper padding */
        div[data-testid="stRadio"] > label {
            display: none !important;
        }

        div[data-testid="stRadio"] p {
            margin: 0 !important;
            font-size: 11.5px !important;
        }

        /* ── Follow-up hint ── */
        .followup-hint {
            font-size: 11px;
            color: var(--text-muted);
            text-align: center;
            margin-top: 6px;
        }

        /* ── Onboarding cards ── */
        .onboarding-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin: 18px 0 24px 0;
        }

        .onboarding-card {
            background: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: 20px;
        }

        .onboarding-card-icon {
            font-size: 22px;
            margin-bottom: 10px;
        }

        .onboarding-card-title {
            font-size: 14px;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 6px;
        }

        .onboarding-card-body {
            font-size: 12px;
            color: var(--text-secondary);
            line-height: 1.6;
            margin-bottom: 12px;
        }

        .onboarding-card-steps {
            font-size: 11px;
            color: var(--text-muted);
            line-height: 1.8;
        }

        .onboarding-card-steps b {
            color: var(--text-secondary);
        }

        .onboarding-dismiss {
            font-size: 11px;
            color: var(--text-muted);
            text-align: center;
            margin-bottom: 10px;
            cursor: pointer;
        }

        /* ── Mode output tabs ── */
        .stTabs [data-baseweb="tab-list"] {
            background: var(--bg-surface) !important;
            border-bottom: 1px solid var(--border) !important;
            gap: 0 !important;
            padding: 0 !important;
        }

        .stTabs [data-baseweb="tab"] {
            font-size: 12px !important;
            font-weight: 500 !important;
            color: var(--text-secondary) !important;
            background: transparent !important;
            border: none !important;
            border-bottom: 2px solid transparent !important;
            padding: 10px 16px !important;
            margin: 0 !important;
        }

        .stTabs [aria-selected="true"] {
            color: var(--accent) !important;
            border-bottom-color: var(--accent) !important;
            background: transparent !important;
        }

        .stTabs [data-baseweb="tab-panel"] {
            padding: 20px 0 0 0 !important;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# Helper functions
# ============================================================
def init_session_state() -> None:
    defaults = {
        "assistant_response": "",
        "response_mode": "",
        "schema_input": "",
        "dax_input": "",
        "response_history": [],
        "prompt_input": "",
        "last_mode": "",
        "report_reset_id": 0,
        "mode_chosen": False,
        "analysis_done": False,
        "refresh_message": "",
        "refresh_error": "",
        "confirm_new_report": False,   # confirmation dialog for New Report
        "scroll_to_output": False,     # trigger auto-scroll after analysis
        "confirm_clear_model": False,  # confirmation dialog for Clear model context
        "onboarding_dismissed": False, # hide onboarding once user has context
        "response_by_mode": {},        # per-mode last response for tabbed output
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def refresh_powerbi_model_context() -> None:
    st.session_state.refresh_message = ""
    st.session_state.refresh_error = ""

    if not POWERBI_EXTRACTOR_SCRIPT.exists():
        st.session_state.refresh_error = (
            "Could not find extract_powerbi_metadata.py in the project folder."
        )
        return

    try:
        result = subprocess.run(
            [sys.executable, str(POWERBI_EXTRACTOR_SCRIPT)],
            cwd=str(Path(__file__).resolve().parent),
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            st.session_state.refresh_message = "Power BI model context refreshed successfully."
        else:
            st.session_state.refresh_error = (
                "Power BI model refresh failed.\n\n"
                + result.stderr
            )

    except Exception as e:
        st.session_state.refresh_error = f"Power BI model refresh failed: {e}"


def reset_inputs() -> None:
    st.session_state.schema_input = ""
    st.session_state.dax_input = ""
    st.session_state.assistant_response = ""
    st.session_state.response_mode = ""
    st.session_state.response_history = []

def request_new_report() -> None:
    """Show the confirmation dialog instead of immediately clearing."""
    st.session_state.confirm_new_report = True

def confirm_new_report() -> None:
    """User confirmed — clear everything."""
    st.session_state.schema_input = ""
    st.session_state.dax_input = ""
    st.session_state.assistant_response = ""
    st.session_state.response_mode = ""
    st.session_state.response_history = []
    st.session_state.prompt_input = ""
    st.session_state.last_mode = ""
    st.session_state.mode_chosen = False
    st.session_state.analysis_done = False
    st.session_state.confirm_new_report = False
    st.session_state.scroll_to_output = False
    st.session_state.response_by_mode = {}
    st.session_state.report_reset_id += 1

def cancel_new_report() -> None:
    st.session_state.confirm_new_report = False

def start_new_report() -> None:
    st.session_state.schema_input = ""
    st.session_state.dax_input = ""
    st.session_state.assistant_response = ""
    st.session_state.response_mode = ""
    st.session_state.response_history = []
    st.session_state.prompt_input = ""
    st.session_state.last_mode = ""
    st.session_state.mode_chosen = False
    st.session_state.analysis_done = False
    st.session_state.response_by_mode = {}
    st.session_state.report_reset_id += 1

AUTO_POWERBI_CONTEXT_FILE = Path(__file__).resolve().parent / "powerbi_model_context.txt"
POWERBI_CONNECTION_FILE = Path(__file__).resolve().parent / "powerbi_context.txt"
POWERBI_EXTRACTOR_SCRIPT = Path(__file__).resolve().parent / "extract_powerbi_metadata.py"

def read_uploaded_context_file(uploaded_file) -> tuple[str, bool, int]:
    """Returns (text, was_truncated, original_char_count)."""
    if uploaded_file is None:
        return "", False, 0

    try:
        file_bytes = uploaded_file.getvalue()
        text = file_bytes.decode("utf-8")
        original_len = len(text)
        if original_len > MAX_CONTEXT_CHARS:
            return text[:MAX_CONTEXT_CHARS] + "\n\n[Context truncated]", True, original_len
        return text, False, original_len
    except UnicodeDecodeError:
        return "The uploaded context file could not be decoded as UTF-8 text.", False, 0
    except Exception as e:
        return f"Error reading uploaded context file: {e}", False, 0


def read_auto_powerbi_context_file() -> tuple[str, bool, int]:
    """Returns (text, was_truncated, original_char_count)."""
    if not AUTO_POWERBI_CONTEXT_FILE.exists():
        return "", False, 0

    try:
        text = AUTO_POWERBI_CONTEXT_FILE.read_text(encoding="utf-8")
        original_len = len(text)
        if original_len > MAX_CONTEXT_CHARS:
            return (
                text[:MAX_CONTEXT_CHARS] + "\n\n[Auto-loaded Power BI model context truncated]",
                True,
                original_len,
            )
        return text, False, original_len
    except Exception as e:
        return f"Error reading auto-loaded Power BI model context: {e}", False, 0


def load_demo() -> None:
    """Load sample schema + DAX and pre-select a sensible mode for new users."""
    st.session_state.schema_input = SAMPLE_SCHEMA
    st.session_state.dax_input = SAMPLE_DAX
    st.session_state.assistant_response = ""
    st.session_state.response_mode = ""
    st.session_state.assistant_mode = "Model Review"
    st.session_state.mode_chosen = True


def parse_sync_timestamp(context_text: str) -> str:
    """Extract the 'Synced: <iso>' line and return a human-readable 'X ago' string.
    Returns empty string if no timestamp found."""
    from datetime import datetime, timezone

    for line in context_text.splitlines()[:5]:
        if line.startswith("Synced:"):
            raw = line.replace("Synced:", "").strip()
            try:
                synced_at = datetime.fromisoformat(raw)
                if synced_at.tzinfo is None:
                    synced_at = synced_at.replace(tzinfo=timezone.utc)
                delta = datetime.now(timezone.utc) - synced_at
                total_seconds = int(delta.total_seconds())
                if total_seconds < 60:
                    return "just now"
                elif total_seconds < 3600:
                    m = total_seconds // 60
                    return f"{m} minute{'s' if m != 1 else ''} ago"
                elif total_seconds < 86400:
                    h = total_seconds // 3600
                    return f"{h} hour{'s' if h != 1 else ''} ago"
                else:
                    d = total_seconds // 86400
                    return f"{d} day{'s' if d != 1 else ''} ago"
            except ValueError:
                return ""
    return ""


def clear_model_context() -> None:
    """Delete the extracted model context files so the card disappears."""
    for f in [AUTO_POWERBI_CONTEXT_FILE, POWERBI_CONNECTION_FILE]:
        try:
            if f.exists():
                f.unlink()
        except Exception:
            pass
    st.session_state.confirm_clear_model = False

def update_prompt_from_library(prompt_text: str) -> None:
    st.session_state.prompt_input = prompt_text


def context_size_indicator(char_count: int, was_truncated: bool) -> str:
    """Return an HTML badge showing context usage."""
    pct = min(100, int(char_count / MAX_CONTEXT_CHARS * 100))
    if was_truncated:
        color = "#F87171"
        label = f"Truncated at {MAX_CONTEXT_CHARS:,} chars"
    elif pct > 75:
        color = "#FBBF24"
        label = f"{char_count:,} / {MAX_CONTEXT_CHARS:,} chars"
    else:
        color = "#34D399"
        label = f"{char_count:,} / {MAX_CONTEXT_CHARS:,} chars"
    return (
        f'<span style="font-size:11px;font-weight:500;color:{color};'
        f'background:rgba(0,0,0,0.25);border:1px solid {color}33;'
        f'border-radius:4px;padding:2px 7px;">{label}</span>'
    )


def spinner_message(mode: str, is_followup: bool = False) -> str:
    """Return a mode-specific loading message."""
    if is_followup:
        return "Building on your last response…"
    messages = {
        "Dashboard Review":  "Reviewing your dashboard layout and visuals…",
        "Model Review":      "Analysing your Power BI model structure…",
        "DAX Debugging":     "Checking your DAX measures for issues…",
        "Measure Generator": "Generating DAX measure suggestions…",
        "Insight Writer":    "Writing business insights from your data…",
        "README Writer":     "Drafting your GitHub README…",
    }
    return messages.get(mode, "Analysing your report…")


def render_active_context_summary(
    uploaded_image,
    uploaded_context_file,
    schema_text: str,
    dax_text: str,
    auto_powerbi_context_text: str,
    mode: str,
) -> None:
    """Show a compact summary of what context the assistant will use, with a mode nudge."""
    items = []

    if auto_powerbi_context_text.strip():
        summary = parse_powerbi_model_summary(auto_powerbi_context_text)
        items.append(
            f'<span class="ctx-tag ctx-green">⬤ Connected model '
            f'({summary["tables"]}T · {summary["measures"]}M · {summary["relationships"]}R)</span>'
        )
    if uploaded_image:
        items.append('<span class="ctx-tag ctx-blue">⬤ Screenshot</span>')
    if schema_text.strip():
        items.append('<span class="ctx-tag ctx-blue">⬤ Schema</span>')
    if dax_text.strip():
        items.append('<span class="ctx-tag ctx-blue">⬤ DAX measures</span>')
    if uploaded_context_file:
        items.append(f'<span class="ctx-tag ctx-blue">⬤ {uploaded_context_file.name}</span>')

    # Mode nudge — suggest a better mode if the loaded context implies one
    nudge = ""
    if auto_powerbi_context_text.strip() and not uploaded_image and mode != "Model Review":
        nudge = '<span class="ctx-nudge">→ Model Review is a good starting point with a connected model</span>'
    elif uploaded_image and not auto_powerbi_context_text.strip() and mode != "Dashboard Review":
        nudge = '<span class="ctx-nudge">→ Dashboard Review works best when a screenshot is loaded</span>'

    if not items:
        return  # nothing active yet, don't show the bar

    tags_html = " ".join(items)
    nudge_html = f"<div style='margin-top:6px'>{nudge}</div>" if nudge else ""

    st.markdown(
        f"""
<div class="ctx-summary">
    <div class="ctx-label">Active context</div>
    <div class="ctx-tags">{tags_html}</div>
    {nudge_html}
</div>
        """,
        unsafe_allow_html=True,
    )


def format_dax(dax_text: str) -> str:
    """Normalise DAX keyword casing and basic indentation before sending to the API.
    Pure Python — no API call. Handles the most common patterns only."""
    import re

    # Keywords to uppercase
    keywords = [
        "CALCULATE", "FILTER", "ALL", "ALLEXCEPT", "ALLSELECTED",
        "SUM", "SUMX", "COUNT", "COUNTX", "COUNTROWS", "COUNTA", "DISTINCTCOUNT",
        "AVERAGE", "AVERAGEX", "MIN", "MINX", "MAX", "MAXX",
        "DIVIDE", "IF", "IFERROR", "ISBLANK", "BLANK", "TRUE", "FALSE",
        "AND", "OR", "NOT", "IN", "SWITCH",
        "RELATED", "RELATEDTABLE", "LOOKUPVALUE",
        "EARLIER", "EARLIEST", "VALUES", "HASONEVALUE", "SELECTEDVALUE",
        "DATEADD", "DATESINPERIOD", "DATESYTD", "DATESMTD", "DATESQTD",
        "TOTALYTD", "TOTALMTD", "TOTALQTD",
        "SAMEPERIODLASTYEAR", "PREVIOUSYEAR", "PREVIOUSMONTH", "PREVIOUSQUARTER",
        "STARTOFYEAR", "ENDOFYEAR", "STARTOFMONTH", "ENDOFMONTH",
        "YEAR", "MONTH", "DAY", "QUARTER", "WEEKDAY", "WEEKNUM",
        "DATE", "TODAY", "NOW", "FORMAT",
        "RANKX", "TOPN", "MAXX", "MINX",
        "USERELATIONSHIP", "CROSSFILTER", "KEEPFILTERS",
        "VAR", "RETURN",
    ]

    result = dax_text
    for kw in keywords:
        # Match keyword as whole word, case-insensitive, not inside quotes
        result = re.sub(
            rf'\b{re.escape(kw)}\b',
            kw,
            result,
            flags=re.IGNORECASE,
        )

    return result


def render_onboarding(has_any_context: bool) -> None:
    """Show getting-started cards when the app is opened cold with no context."""
    if has_any_context or st.session_state.get("onboarding_dismissed", False):
        return

    st.markdown(
        """
<div style="margin: 4px 0 8px 0;">
    <div class="section-label">Getting started</div>
    <div style="font-size:13px;color:var(--text-secondary);margin-bottom:4px;">
        Choose how you want to use BI Report Assistant.
    </div>
</div>
<div class="onboarding-grid">
    <div class="onboarding-card">
        <div class="onboarding-card-icon">⚡</div>
        <div class="onboarding-card-title">Local — Connected Model</div>
        <div class="onboarding-card-body">
            Full experience. The assistant reads your live Power BI model — tables, columns, measures, and relationships — automatically.
        </div>
        <div class="onboarding-card-steps">
            <b>1.</b> Open your report in Power BI Desktop<br>
            <b>2.</b> Click <b>BI Report Assistant</b> in the External Tools ribbon<br>
            <b>3.</b> The app launches with your model pre-loaded
        </div>
    </div>
    <div class="onboarding-card">
        <div class="onboarding-card-icon">☁</div>
        <div class="onboarding-card-title">Cloud — Paste Context</div>
        <div class="onboarding-card-body">
            Works anywhere. Paste your schema and DAX measures manually, upload a screenshot, or try the demo to see what the assistant can do.
        </div>
        <div class="onboarding-card-steps">
            <b>1.</b> Paste your schema and DAX in the context fields<br>
            <b>2.</b> Upload a dashboard screenshot (optional)<br>
            <b>3.</b> Pick a mode and ask a question
        </div>
    </div>
</div>
        """,
        unsafe_allow_html=True,
    )

    dismiss_col1, dismiss_col2, dismiss_col3 = st.columns([0.35, 0.3, 0.35])
    with dismiss_col2:
        if st.button("Dismiss  ×", use_container_width=True, key="dismiss_onboarding"):
            st.session_state.onboarding_dismissed = True


def build_session_export(response_history: list, response_by_mode: dict) -> str:
    """Build a single Markdown document from the full session."""
    from datetime import datetime
    lines = []

    lines.append("# BI Report Assistant — Session Export")
    lines.append(f"\nExported: {datetime.now().strftime('%B %d, %Y at %H:%M')}\n")
    lines.append("---\n")

    # Summary table
    if response_history:
        lines.append("## Session Summary\n")
        lines.append(f"Total analyses run: **{len(response_history)}**\n")
        modes_used = list(dict.fromkeys(item["mode"] for item in response_history))
        lines.append(f"Modes used: {', '.join(f'**{m}**' for m in modes_used)}\n")
        lines.append("---\n")

    # Full responses
    lines.append("## Responses\n")
    for i, item in enumerate(response_history, 1):
        lines.append(f"### {i}. {item['mode']}\n")
        lines.append(f"**Question:** {item['question']}\n")
        lines.append(item["response"])
        lines.append("\n---\n")

    if not response_history:
        lines.append("_No analyses have been run in this session._\n")

    return "\n".join(lines)


def clipboard_button(text: str) -> None:
    """Render a copy-to-clipboard button.
    Uses st.components.v1.html so the raw HTML is never processed by Streamlit's
    markdown pipeline, which was mangling the injected button code."""
    import html as html_module
    import streamlit.components.v1 as components

    safe_id = f"cb_{abs(hash(text)) % 10_000_000}"
    escaped_html = html_module.escape(text)

    components.html(
        f"""
        <pre id="{safe_id}" style="display:none">{escaped_html}</pre>
        <button onclick="
            var t = document.getElementById('{safe_id}').textContent;
            navigator.clipboard.writeText(t).then(function(){{
                this.textContent = '✓ Copied';
                var btn = this;
                setTimeout(function(){{ btn.textContent = 'Copy to clipboard'; }}, 1600);
            }}.bind(this));
        " style="
            font-size:12px;font-weight:500;font-family:Inter,-apple-system,sans-serif;
            color:#7B8BAA;background:#141C2E;
            border:1px solid #243048;border-radius:6px;
            padding:7px 14px;cursor:pointer;
            width:100%;box-sizing:border-box;
        "
        onmouseover="this.style.borderColor='#4F8EF7';this.style.color='#F0F4FF'"
        onmouseout="this.style.borderColor='#243048';this.style.color='#7B8BAA'">
            Copy to clipboard
        </button>
        """,
        height=40,
    )

def get_section_text(text: str, section_name: str) -> str:
    section_header = f"## {section_name}"

    if section_header not in text:
        return ""

    section_start = text.find(section_header)
    next_section_start = text.find("\n## ", section_start + len(section_header))

    if next_section_start == -1:
        return text[section_start:]

    return text[section_start:next_section_start]

def parse_powerbi_model_summary(context_text: str) -> dict:
    tables_section = get_section_text(context_text, "Tables")
    columns_section = get_section_text(context_text, "Columns")
    measures_section = get_section_text(context_text, "Measures")
    relationships_section = get_section_text(context_text, "Relationships")

    table_count = tables_section.count("### Table:")

    column_count = 0
    for line in columns_section.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") and "[" in stripped and "]" in stripped:
            column_count += 1

    measure_count = 0
    for line in measures_section.splitlines():
        stripped = line.strip()
        if stripped.startswith("### "):
            measure_count += 1

    relationship_count = 0
    for line in relationships_section.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") and "→" in stripped:
            relationship_count += 1

    return {
        "tables": table_count,
        "columns": column_count,
        "measures": measure_count,
        "relationships": relationship_count,
    }

def image_to_data_url(uploaded_image) -> str:
    image = Image.open(uploaded_image).convert("RGB")

    max_width = 1200
    if image.width > max_width:
        ratio = max_width / image.width
        new_height = int(image.height * ratio)
        image = image.resize((max_width, new_height))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{encoded_image}"


def clean_non_code_output(text: str) -> str:
    return text.replace("`", "")


def get_download_info(mode: str, output: str) -> tuple[str, str, str]:
    if mode == "README Writer":
        return "Download README.md", "README.md", output

    if mode in ["DAX Debugging", "Measure Generator"]:
        return "Download DAX Output", "dax_output.md", output

    if mode == "Insight Writer":
        return "Download Insights", "dashboard_insights.md", clean_non_code_output(output)

    if mode == "Model Review":
        return "Download Model Review", "model_review.md", clean_non_code_output(output)

    return "Download Feedback", "dashboard_feedback.md", clean_non_code_output(output)


def build_user_prompt(
    mode: str,
    user_question: str,
    schema_text: str,
    dax_text: str,
    context_file_text: str,
    previous_response_text: str = "",
) -> str:
    mode_instructions = MODE_PROMPTS.get(mode, "")

    instructions_to_use = (
        FOLLOW_UP_INSTRUCTIONS
        if previous_response_text.strip()
        else mode_instructions
    )

    return f"""
Assistant Mode:
{mode}

Mode-Specific Instructions:
{instructions_to_use}

User Question:
{user_question}

Power BI Schema:
{schema_text}

Current DAX Measures:
{dax_text}

Uploaded Context File:
{context_file_text}

Previous Assistant Response:
{previous_response_text}

Follow the instructions above.

If this is a follow-up question, answer the follow-up directly instead of regenerating the full original mode format.

Follow the selected assistant mode.

If a screenshot is uploaded, use it only as supporting context for the selected mode.
Do not switch into Dashboard Review mode unless the selected mode is Dashboard Review or the user explicitly asks for visual critique.
"""


# Per-mode model routing and max_tokens
# gpt-4o for modes needing vision or nuanced analysis
# gpt-4o-mini for structured/generative modes that don't need frontier reasoning
MODE_MODEL = {
    "Dashboard Review":  "gpt-4o",       # needs vision + design judgment
    "Model Review":      "gpt-4o",       # nuanced structural analysis
    "DAX Debugging":     "gpt-4o-mini",  # structured, rule-based
    "Measure Generator": "gpt-4o-mini",  # generative, schema-driven
    "Insight Writer":    "gpt-4o",       # needs vision for screenshot reading
    "README Writer":     "gpt-4o-mini",  # templated writing task
}

MODE_MAX_TOKENS = {
    "Dashboard Review":  1000,
    "Model Review":      1400,
    "DAX Debugging":     1200,
    "Measure Generator": 1400,
    "Insight Writer":    900,
    "README Writer":     1200,
}

DEFAULT_MODEL      = "gpt-4o-mini"
DEFAULT_MAX_TOKENS = 1000


def stream_openai(user_prompt: str, mode: str, image_data_url: str | None = None):
    """Return a streaming generator of text chunks from the OpenAI chat completions API.
    Uses chat.completions.create which has first-class streaming support."""
    model      = MODE_MODEL.get(mode, DEFAULT_MODEL)
    max_tokens = MODE_MAX_TOKENS.get(mode, DEFAULT_MAX_TOKENS)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if image_data_url:
        messages.append({
            "role": "user",
            "content": [
                {"type": "text",      "text": user_prompt},
                {"type": "image_url", "image_url": {"url": image_data_url, "detail": "high"}},
            ],
        })
    else:
        messages.append({"role": "user", "content": user_prompt})

    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        stream=True,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


# ============================================================
# UI sections
# ============================================================
def render_header() -> None:
    model_connected = (not CLOUD_MODE) and AUTO_POWERBI_CONTEXT_FILE.exists()

    screenshot_key = f"uploaded_image_{st.session_state.get('report_reset_id', 0)}"
    screenshot_added = st.session_state.get(screenshot_key) is not None
    mode_selected = True  # a mode is always selected (defaults to Dashboard Review)
    analysis_done = st.session_state.get("analysis_done", False)
    current_mode = st.session_state.get("assistant_mode", ASSISTANT_MODES[0])

    # Modes where a screenshot is the primary context input
    visual_modes = {"Dashboard Review", "Insight Writer"}
    needs_screenshot = current_mode in visual_modes

    # For non-visual modes, "context" means model, schema, DAX, or uploaded file
    has_non_screenshot_context = (
        model_connected
        or bool(st.session_state.get("schema_input", "").strip())
        or bool(st.session_state.get("dax_input", "").strip())
    )

    def step_cls(cond): return "pipeline-step active" if cond else "pipeline-step"

    if CLOUD_MODE:
        has_context = (
            screenshot_added
            or bool(st.session_state.get("schema_input", "").strip())
            or bool(st.session_state.get("dax_input", "").strip())
        )
        pipeline_html = f"""
<div class="pipeline">
    <div class="{step_cls(has_context)}"><span class="pipeline-num">1</span>Add Context</div>
    <div class="{step_cls(mode_selected)}"><span class="pipeline-num">2</span>Choose Mode</div>
    <div class="{step_cls(analysis_done)}"><span class="pipeline-num">3</span>Analyze</div>
</div>"""
    else:
        s1 = step_cls(model_connected)
        # Step 2: screenshot for visual modes, any context for non-visual modes
        if needs_screenshot:
            s2_active = screenshot_added
            s2_label = "Add Screenshot"
        else:
            s2_active = has_non_screenshot_context or screenshot_added
            s2_label = "Add Context"
        s2 = step_cls(s2_active)
        s3 = step_cls(mode_selected)
        s4 = step_cls(analysis_done)
        pipeline_html = f"""
<div class="pipeline">
    <div class="{s1}"><span class="pipeline-num">1</span>Connect Model</div>
    <div class="{s2}"><span class="pipeline-num">2</span>{s2_label}</div>
    <div class="{s3}"><span class="pipeline-num">3</span>Choose Mode</div>
    <div class="{s4}"><span class="pipeline-num">4</span>Analyze</div>
</div>"""

    st.markdown(
        f"""
<div class="topbar">
    <div class="topbar-brand">
        <div class="topbar-logo">
            <svg viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                <rect x="2" y="10" width="4" height="8" rx="1"/>
                <rect x="8" y="6" width="4" height="12" rx="1"/>
                <rect x="14" y="2" width="4" height="16" rx="1"/>
            </svg>
        </div>
        <span class="topbar-name">BI Report Assistant</span>
        <div class="topbar-divider"></div>
        <span class="topbar-product">Power BI Workflow</span>
    </div>
    <div class="topbar-right">
        <div class="status-badge">
            <span class="status-dot"></span>
            AI Ready
        </div>
    </div>
</div>
{pipeline_html}
        """,
        unsafe_allow_html=True,
    )
    
def has_report_context(
    uploaded_image,
    uploaded_context_file,
    schema_text: str,
    dax_text: str,
    context_file_text: str,
) -> bool:
        return any(
        [
            uploaded_image is not None,
            uploaded_context_file is not None,
            schema_text.strip(),
            dax_text.strip(),
            context_file_text.strip(),
        ]
    )

def render_connected_powerbi_card() -> None:
    if not AUTO_POWERBI_CONTEXT_FILE.exists():
        return

    auto_context_text, _, _ = read_auto_powerbi_context_file()
    summary = parse_powerbi_model_summary(auto_context_text)
    synced_ago = parse_sync_timestamp(auto_context_text)

    tables = summary["tables"]
    columns = summary["columns"]
    measures = summary["measures"]
    relationships = summary["relationships"]

    synced_html = (
        f'<div class="model-card-sub">Last synced {synced_ago}</div>'
        if synced_ago else
        '<div class="model-card-sub">Live context from open PBIX file</div>'
    )

    st.markdown(
        f"""
<div class="model-card">
    <div class="model-card-header">
        <span class="live-dot"></span>
        <div>
            <div class="model-card-title">Connected Model</div>
            {synced_html}
        </div>
    </div>
    <div class="model-stats">
        <div class="model-stat">
            <div class="model-stat-value">{tables}</div>
            <div class="model-stat-label">Tables</div>
        </div>
        <div class="model-stat">
            <div class="model-stat-value">{columns}</div>
            <div class="model-stat-label">Columns</div>
        </div>
        <div class="model-stat">
            <div class="model-stat-value">{measures}</div>
            <div class="model-stat-label">Measures</div>
        </div>
        <div class="model-stat">
            <div class="model-stat-value">{relationships}</div>
            <div class="model-stat-label">Relations</div>
        </div>
    </div>
</div>
        """,
        unsafe_allow_html=True,
    )

    # Reconnect instructions — collapsed, always available
    with st.expander("ℹ  How to reconnect or switch models"):
        st.markdown(
            """
To connect a different model or refresh the connection:

1. Open the report you want to work with in **Power BI Desktop**
2. Click **BI Report Assistant** in the **External Tools** ribbon
3. The app will automatically extract the new model context

The connected model context is tied to whichever PBIX file was open when the tool was last launched.
            """
        )

    # Clear model context — with inline confirmation
    if st.session_state.get("confirm_clear_model", False):
        st.markdown(
            """
<div class="confirm-dialog">
    <div class="confirm-dialog-title">Clear model context?</div>
    <div class="confirm-dialog-body">
        This removes the extracted model data from this session.
        To reconnect, open your report in Power BI Desktop and click the External Tools shortcut again.
    </div>
</div>
            """,
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns(2)
        with c1:
            st.button("Yes, clear it", on_click=clear_model_context, use_container_width=True)
        with c2:
            st.button(
                "Cancel",
                on_click=lambda: st.session_state.update({"confirm_clear_model": False}),
                use_container_width=True,
                key="cancel_clear_model",
            )
    else:
        st.button(
            "Clear model context",
            on_click=lambda: st.session_state.update({"confirm_clear_model": True}),
            use_container_width=True,
            key="request_clear_model",
            help="Removes the extracted model data. Reconnect by relaunching from Power BI External Tools.",
        )
def render_context_column():
    model_context_exists = (not CLOUD_MODE) and AUTO_POWERBI_CONTEXT_FILE.exists()
    powerbi_refresh_available = (
        (not CLOUD_MODE)
        and AUTO_POWERBI_CONTEXT_FILE.exists()
        and POWERBI_CONNECTION_FILE.exists()
    )

    # ── Mode selector (top of panel, always visible) ──────────
    st.markdown('<div class="section-label">Assistant Mode</div>', unsafe_allow_html=True)

    if "assistant_mode" not in st.session_state:
        st.session_state.assistant_mode = ASSISTANT_MODES[0]

    # Use st.radio — Streamlit manages selected state natively and reliably.
    # CSS below transforms the default radio into a styled 3-column grid.
    radio_labels = [f"{MODE_ICONS.get(m, '')}  {m}" for m in ASSISTANT_MODES]
    current_label = f"{MODE_ICONS.get(st.session_state.assistant_mode, '')}  {st.session_state.assistant_mode}"

    selected_label = st.radio(
        "Mode",
        options=radio_labels,
        index=radio_labels.index(current_label),
        label_visibility="collapsed",
        key="mode_radio",
    )

    # Extract mode name from label and sync to session state
    selected_mode = next(
        (m for m in ASSISTANT_MODES if selected_label and m in selected_label),
        ASSISTANT_MODES[0],
    )
    if selected_mode != st.session_state.assistant_mode:
        st.session_state.assistant_mode = selected_mode

    mode = st.session_state.assistant_mode

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── Cloud mode: schema + DAX are primary inputs ────────────
    if CLOUD_MODE:
        st.markdown('<div class="section-label" style="margin-top:14px;">Report Context</div>', unsafe_allow_html=True)

        # Demo link
        if not st.session_state.get("schema_input", "").strip():
            demo_col1, demo_col2 = st.columns([0.65, 0.35])
            with demo_col1:
                st.caption("No context loaded yet. Paste schema + DAX or try the demo.")
            with demo_col2:
                st.button("Try demo →", on_click=load_demo, use_container_width=True)

        schema_chars = len(st.session_state.get("schema_input", ""))
        dax_chars = len(st.session_state.get("dax_input", ""))
        total_chars = schema_chars + dax_chars
        is_truncated = total_chars > MAX_CONTEXT_CHARS

        if total_chars > 0:
            st.markdown(
                context_size_indicator(total_chars, is_truncated),
                unsafe_allow_html=True,
            )
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        schema_text = st.text_area(
            "Schema / Data Context",
            height=180,
            placeholder="Table: sales_data\nColumns:\n  Date — Date\n  Category — Text\n  Revenue — Currency",
            key="schema_input",
        )

        dax_text = st.text_area(
            "Current DAX Measures",
            height=200,
            placeholder="Total Revenue = SUM(sales_data[Revenue])",
            key="dax_input",
        )

        uploaded_image = st.file_uploader(
            "Screenshot (optional)",
            type=["png", "jpg", "jpeg"],
            key=f"uploaded_image_{st.session_state.report_reset_id}",
        )

        uploaded_context_file = st.file_uploader(
            "Context file (optional)",
            type=["txt", "md", "csv", "json"],
            key=f"uploaded_context_{st.session_state.report_reset_id}",
        )

        if uploaded_context_file:
            ctx_text, ctx_truncated, ctx_len = read_uploaded_context_file(uploaded_context_file)
            st.markdown(
                f"Loaded **{uploaded_context_file.name}** &nbsp;"
                + context_size_indicator(ctx_len, ctx_truncated),
                unsafe_allow_html=True,
            )

        st.button("New Report", on_click=request_new_report, use_container_width=True)

    # ── Local mode: connected model is primary ─────────────────
    else:
        if model_context_exists:
            st.markdown('<div class="section-label" style="margin-top:14px;">Model Context</div>', unsafe_allow_html=True)
            render_connected_powerbi_card()

        if powerbi_refresh_available:
            st.button(
                "↻  Refresh Model",
                on_click=refresh_powerbi_model_context,
                use_container_width=True,
                help="Re-extract tables, columns, measures, and relationships.",
            )
            if st.session_state.refresh_error:
                st.error(st.session_state.refresh_error)

        st.markdown('<div class="section-label" style="margin-top:14px;">Screenshot</div>', unsafe_allow_html=True)

        uploaded_image = st.file_uploader(
            "Upload your Power BI screenshot",
            type=["png", "jpg", "jpeg"],
            key=f"uploaded_image_{st.session_state.report_reset_id}",
            label_visibility="collapsed",
        )

        st.button("New Report", on_click=request_new_report, use_container_width=True)

        uploaded_context_file = None
        schema_text = ""
        dax_text = ""

        with st.expander("Manual Override — Schema / DAX", expanded=False):
            st.caption("Use only if you need to supplement or replace the connected model context.")

            uploaded_context_file = st.file_uploader(
                "Context file",
                type=["txt", "md", "csv", "json"],
                key=f"uploaded_context_{st.session_state.report_reset_id}",
                label_visibility="collapsed",
            )
            if uploaded_context_file:
                ctx_text, ctx_truncated, ctx_len = read_uploaded_context_file(uploaded_context_file)
                st.markdown(
                    f"Loaded **{uploaded_context_file.name}** &nbsp;"
                    + context_size_indicator(ctx_len, ctx_truncated),
                    unsafe_allow_html=True,
                )

            schema_text = st.text_area(
                "Schema / Data Context",
                height=150,
                placeholder="Table: sales_data\nColumns:\n  Date — Date\n  Category — Text\n  Revenue — Currency",
                key="schema_input",
            )

            dax_text = st.text_area(
                "Current DAX Measures",
                height=180,
                placeholder="Total Revenue = SUM(sales_data[Revenue])",
                key="dax_input",
            )

        with st.expander("How do I provide context?"):
            st.markdown(
                """
**1. Connected model** — launched from Power BI External Tools, auto-loads tables, columns, measures, and relationships.

**2. Screenshot** — best for layout reviews, visual feedback, and business insights.

**3. Schema** — table names, column names, and data types.

**4. DAX measures** — existing measures to review or use as context.

**5. Context file** — `.txt`, `.md`, `.csv`, or `.json`.
                """
            )

    # ── New Report confirmation dialog ────────────────────────
    if st.session_state.get("confirm_new_report", False):
        st.markdown(
            """
<div class="confirm-dialog">
    <div class="confirm-dialog-title">Clear everything and start fresh?</div>
    <div class="confirm-dialog-body">This will remove all uploads, schema, DAX, output, and history for this session.</div>
</div>
            """,
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns(2)
        with c1:
            st.button("Yes, clear all", on_click=confirm_new_report, use_container_width=True)
        with c2:
            st.button("Cancel", on_click=cancel_new_report, use_container_width=True)

    return uploaded_image, uploaded_context_file, mode, schema_text, dax_text


def render_preview_column(uploaded_image, mode: str = "") -> str | None:
    image_data_url = None

    # Modes that genuinely benefit from a screenshot
    visual_modes = {"Dashboard Review", "Insight Writer"}
    needs_screenshot = mode in visual_modes

    if uploaded_image:
        st.markdown('<div class="section-label">Dashboard Preview</div>', unsafe_allow_html=True)
        image = Image.open(uploaded_image)
        st.image(image, use_container_width=True)
        image_data_url = image_to_data_url(uploaded_image)
    else:
        st.markdown('<div class="section-label">Preview</div>', unsafe_allow_html=True)

        if needs_screenshot:
            icon = "🖼"
            title = "Screenshot recommended"
            body = f"{mode} works best with a dashboard screenshot. Upload one from the left panel."
            hint = "Drag and drop a PNG or JPG of your Power BI report."
        else:
            icon = "◎"
            title = "No screenshot needed"
            if mode in ("DAX Debugging", "Measure Generator"):
                body = f"{mode} works from your schema and DAX measures — no screenshot required."
            elif mode == "Model Review":
                body = "Model Review uses your connected model or pasted schema. A screenshot is optional."
            elif mode == "README Writer":
                body = "README Writer works from your schema and measures. You can optionally upload a preview screenshot."
            else:
                body = "Upload a screenshot if you'd like visual context included in the analysis."
            hint = "You can still upload a screenshot and it will be used as additional context."

        st.markdown(
            f"""
            <div style="
                background: #0E1420;
                border: 1px dashed {'#1E2A40' if not needs_screenshot else '#243048'};
                border-radius: 10px;
                padding: 36px 24px;
                text-align: center;
                line-height: 1.6;
            ">
                <div style="font-size: 26px; margin-bottom: 10px;">{icon}</div>
                <div style="color: #7B8BAA; font-weight: 600; font-size: 13px; margin-bottom: 6px;">{title}</div>
                <div style="color: #4A566E; font-size: 12px;">{body}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(hint)

    return image_data_url


def render_prompt_section(mode: str) -> tuple[str, bool, bool]:
    st.markdown("<hr style='margin: 24px 0;'>", unsafe_allow_html=True)
    prompt_col1, prompt_col2, prompt_col3 = st.columns([0.18, 0.64, 0.18])

    if st.session_state.last_mode != mode:
        st.session_state.prompt_input = DEFAULT_QUESTIONS.get(mode, "What do you need help with?")
        st.session_state.last_mode = mode

    with prompt_col2:
        # Prompt library — collapsed by default
        prompt_options = PROMPT_LIBRARY.get(mode, {})
        if prompt_options:
            with st.expander("Suggested prompts", expanded=False):
                prompt_items = list(prompt_options.items())
                for row_start in range(0, len(prompt_items), 2):
                    cols = st.columns(2)
                    for col_index, (label, prompt_text) in enumerate(prompt_items[row_start:row_start + 2]):
                        with cols[col_index]:
                            st.button(
                                label,
                                key=f"prompt_{mode}_{label}",
                                use_container_width=True,
                                on_click=update_prompt_from_library,
                                args=(prompt_text,),
                            )

        user_question = st.text_area(
            "Message",
            key="prompt_input",
            height=110,
            label_visibility="collapsed",
            placeholder="Describe what you'd like the assistant to do…",
        )

        # Live char counter beneath textarea
        q_len = len(user_question)
        counter_color = "#F87171" if q_len > 1200 else "#FBBF24" if q_len > 800 else "#4A566E"
        st.markdown(
            f'<div style="text-align:right;font-size:10px;color:{counter_color};'
            f'margin-top:-10px;margin-bottom:8px;">{q_len} chars</div>',
            unsafe_allow_html=True,
        )

        # Cmd+Enter / Ctrl+Enter keyboard shortcut
        # Uses components.html so JS can reach the parent DOM and dispatch
        # a proper bubbling MouseEvent that React's synthetic event system catches
        import streamlit.components.v1 as _comp
        _comp.html(
            r"""
            <script>
            (function() {
                function attachShortcut() {
                    var doc = window.parent.document;
                    var ta = doc.querySelector('textarea');
                    if (!ta) { setTimeout(attachShortcut, 300); return; }
                    if (ta._biShortcut) return;
                    ta._biShortcut = true;
                    ta.addEventListener('keydown', function(e) {
                        if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                            e.preventDefault();
                            var btns = doc.querySelectorAll('button');
                            for (var i = 0; i < btns.length; i++) {
                                var txt = btns[i].innerText.replace(/\s+/g,' ').trim();
                                if (txt.startsWith('Analyze') && !btns[i].disabled) {
                                    btns[i].dispatchEvent(new MouseEvent('click', {
                                        bubbles: true, cancelable: true, view: window.parent
                                    }));
                                    break;
                                }
                            }
                        }
                    });
                }
                setTimeout(attachShortcut, 400);
                setTimeout(attachShortcut, 1000);
            })();
            </script>
            """,
            height=0,
        )

        # Always render both button columns — follow-up disabled until a response exists
        has_previous = bool(st.session_state.get("assistant_response", "").strip())

        btn_left, btn_right = st.columns(2)
        with btn_left:
            analyze_clicked = st.button(
                "Analyze →",
                key="analyze_btn",
                use_container_width=True,
                type="primary",
                help="Run a fresh analysis using the selected mode.  ⌘↵ / Ctrl+Enter",
            )
        with btn_right:
            follow_up_clicked = st.button(
                "Follow up on last response →",
                key="followup_btn",
                use_container_width=True,
                disabled=not has_previous,
                help="Build on the previous response rather than starting fresh." if has_previous else "Run your first analysis to unlock this.",
            )

        if not has_previous:
            st.markdown(
                '<div class="followup-hint">Run an analysis first to unlock follow-up.</div>',
                unsafe_allow_html=True,
            )

        use_latest_response = follow_up_clicked and not analyze_clicked

    return user_question, analyze_clicked or follow_up_clicked, use_latest_response


def render_output_section() -> None:
    """Render per-mode tabbed output. Each mode keeps its last response as a tab."""
    response_by_mode = st.session_state.get("response_by_mode", {})
    if not response_by_mode:
        return

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    out_col1, out_col2, out_col3 = st.columns([0.04, 0.92, 0.04])

    with out_col2:
        st.markdown('<div class="section-label">Output</div>', unsafe_allow_html=True)

        # Build tabs for every mode that has a response, most recent first
        mode_order = list(dict.fromkeys(
            reversed([item["mode"] for item in st.session_state.response_history])
        ))
        available = [m for m in mode_order if m in response_by_mode]

        if not available:
            return

        tab_labels = [f"{MODE_ICONS.get(m, '')}  {OUTPUT_TITLES.get(m, m)}" for m in available]
        tabs = st.tabs(tab_labels)

        for tab, mode_key in zip(tabs, available):
            with tab:
                response_text = response_by_mode[mode_key]["response"]
                question = response_by_mode[mode_key]["question"]

                st.markdown(
                    f'<div style="font-size:11px;color:var(--text-muted);margin-bottom:16px;">'
                    f'Q: {question[:120]}{"…" if len(question) > 120 else ""}</div>',
                    unsafe_allow_html=True,
                )

                if mode_key == "README Writer":
                    st.markdown(response_text)
                elif mode_key in ["DAX Debugging", "Measure Generator"]:
                    st.markdown(response_text)
                else:
                    st.markdown(clean_non_code_output(response_text))

                download_label, download_file_name, download_data = get_download_info(mode_key, response_text)

                btn_c1, btn_c2, btn_c3 = st.columns(3)
                with btn_c1:
                    st.download_button(
                        label=download_label,
                        data=download_data,
                        file_name=download_file_name,
                        mime="text/markdown",
                        use_container_width=True,
                        key=f"dl_{mode_key}",
                    )
                with btn_c2:
                    clipboard_button(response_text)
                with btn_c3:
                    if st.button("Clear this tab", use_container_width=True, key=f"clear_{mode_key}"):
                        del st.session_state.response_by_mode[mode_key]
                        if st.session_state.response_mode == mode_key:
                            st.session_state.assistant_response = ""
                            st.session_state.response_mode = ""
                        st.rerun()


def rerun_from_history(item: dict) -> None:
    """Load a history item's mode and question back into the prompt for re-running."""
    st.session_state.assistant_mode = item["mode"]
    st.session_state.prompt_input = item["question"]
    st.session_state.last_mode = item["mode"]


def render_history_section() -> None:
    if not st.session_state.response_history:
        return

    st.markdown("<hr style='margin: 28px 0 20px 0;'>", unsafe_allow_html=True)

    h_col1, h_col2, h_col3 = st.columns([0.55, 0.25, 0.20])
    with h_col1:
        st.markdown('<div class="section-label">Response History</div>', unsafe_allow_html=True)
    with h_col2:
        export_data = build_session_export(
            st.session_state.response_history,
            st.session_state.get("response_by_mode", {}),
        )
        st.download_button(
            label="Export session",
            data=export_data,
            file_name="bi_assistant_session.md",
            mime="text/markdown",
            use_container_width=True,
            help="Download all responses from this session as a single Markdown document.",
        )
    with h_col3:
        if st.button("Clear History", use_container_width=True):
            st.session_state.response_history = []
            st.rerun()

    for index, item in enumerate(reversed(st.session_state.response_history), start=1):
        mode_icon = MODE_ICONS.get(item["mode"], "◆")
        label = f"{mode_icon}  {item['mode']}  —  {item['question'][:70]}{'…' if len(item['question']) > 70 else ''}"
        with st.expander(label):
            st.markdown(item["response"])
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            if st.button(
                "↺  Re-run this",
                key=f"rerun_{index}_{item['mode']}",
                use_container_width=False,
                help="Load this question and mode back into the prompt.",
                on_click=rerun_from_history,
                args=(item,),
            ):
                pass

# ============================================================
# Main app
# ============================================================
def main() -> None:
    apply_custom_css()
    init_session_state()
    render_header()

    left_col, right_col = st.columns([0.95, 1.05])

    with left_col:
        uploaded_image, uploaded_context_file, mode, schema_text, dax_text = render_context_column()

    uploaded_context_text, _, _ = read_uploaded_context_file(uploaded_context_file)
    auto_powerbi_context_text, _, _ = read_auto_powerbi_context_file()

    context_file_text_parts = []
    if auto_powerbi_context_text.strip():
        context_file_text_parts.append(
            "Auto-loaded Power BI Model Context:\n" + auto_powerbi_context_text
        )
    if uploaded_context_text.strip():
        context_file_text_parts.append(
            "User-uploaded Context File:\n" + uploaded_context_text
        )
    context_file_text = "\n\n---\n\n".join(context_file_text_parts)

    # Dismiss onboarding as soon as any context is present
    has_any_context = bool(
        uploaded_image
        or uploaded_context_file
        or schema_text.strip()
        or dax_text.strip()
        or auto_powerbi_context_text.strip()
    )
    if has_any_context:
        st.session_state.onboarding_dismissed = True

    with right_col:
        image_data_url = render_preview_column(uploaded_image, mode=mode)

    # Onboarding — shown in the main area when no context is loaded
    render_onboarding(has_any_context)

    user_question, analyze_clicked, use_latest_response = render_prompt_section(mode)

    # Active context summary
    render_active_context_summary(
        uploaded_image=uploaded_image,
        uploaded_context_file=uploaded_context_file,
        schema_text=schema_text,
        dax_text=dax_text,
        auto_powerbi_context_text=auto_powerbi_context_text,
        mode=mode,
    )

    if analyze_clicked:
        if not user_question.strip():
            st.warning("Please enter a question or request for analysis.")

        elif not has_report_context(
            uploaded_image=uploaded_image,
            uploaded_context_file=uploaded_context_file,
            schema_text=schema_text,
            dax_text=dax_text,
            context_file_text=context_file_text,
        ):
            st.warning(
                "Please provide some context first — upload a screenshot, connect your Power BI model, or paste schema/DAX measures."
            )

        else:
            # Apply DAX formatter before sending to API
            formatted_dax = format_dax(dax_text) if dax_text.strip() else dax_text

            previous_response_text = (
                st.session_state.assistant_response
                if use_latest_response
                else ""
            )
            user_prompt = build_user_prompt(
                mode=mode,
                user_question=user_question,
                schema_text=schema_text,
                dax_text=formatted_dax,
                context_file_text=context_file_text,
                previous_response_text=previous_response_text,
            )

            # Scroll anchor + output container rendered before streaming starts
            # so the text appears in the right place immediately
            st.markdown('<div id="output-anchor"></div>', unsafe_allow_html=True)
            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

            stream_col1, stream_col2, stream_col3 = st.columns([0.04, 0.92, 0.04])
            with stream_col2:
                st.markdown(
                    f'<div class="section-label" style="margin-bottom:10px;">'
                    f'{spinner_message(mode, is_followup=use_latest_response)}</div>',
                    unsafe_allow_html=True,
                )
                try:
                    gen = stream_openai(user_prompt, mode, image_data_url)
                    output_text = st.write_stream(gen)

                    # Store completed response
                    st.session_state.assistant_response = output_text
                    st.session_state.response_mode = mode
                    st.session_state.analysis_done = True
                    st.session_state.scroll_to_output = False  # already visible

                    if "response_by_mode" not in st.session_state:
                        st.session_state.response_by_mode = {}
                    st.session_state.response_by_mode[mode] = {
                        "response": output_text,
                        "question": user_question,
                    }

                    st.session_state.response_history.append({
                        "mode": mode,
                        "question": user_question,
                        "response": output_text,
                    })
                    st.rerun()

                except Exception as e:
                    err = str(e).lower()
                    if "401" in err or "authentication" in err or "api key" in err or "invalid_api_key" in err:
                        st.error(
                            "**API key error** — the OpenAI API key is missing, invalid, or expired. "
                            "Check that `OPENAI_API_KEY` is set correctly in your `.env` file or Streamlit secrets."
                        )
                    elif "429" in err or "rate limit" in err or "quota" in err:
                        st.error(
                            "**Rate limit or quota exceeded** — your OpenAI account has hit its usage limit. "
                            "Check your usage and billing at platform.openai.com."
                        )
                    elif "timeout" in err or "timed out" in err:
                        st.error(
                            "**Request timed out** — the API took too long to respond. "
                            "This usually resolves on retry — try again in a moment."
                        )
                    elif "connection" in err or "network" in err:
                        st.error(
                            "**Connection error** — could not reach the OpenAI API. "
                            "Check your internet connection and try again."
                        )
                    elif "context_length" in err or "maximum context" in err or "token" in err:
                        st.error(
                            "**Context too long** — the combined prompt and context exceeded the model's limit. "
                            "Try reducing your schema, DAX, or uploaded context file size."
                        )
                    else:
                        st.error(
                            "**Something went wrong** — the AI request failed. "
                            "Try again, and if the problem persists check your API key and account status."
                        )
                        with st.expander("Error details"):
                            st.code(str(e))

    render_output_section()
    render_history_section()


if __name__ == "__main__":
    main()