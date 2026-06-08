import base64
import io
import os

import streamlit as st
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
if not api_key:
    st.error("Missing OpenAI API key. Please add OPENAI_API_KEY to your .env file.")
    st.stop()

client = OpenAI(api_key=api_key)


# ============================================================
# App configuration
# ============================================================
ASSISTANT_MODES = [
    "Dashboard Review",
    "DAX Debugging",
    "Measure Generator",
    "Insight Writer",
    "README Writer",
]

MODE_DESCRIPTIONS = {
    "Dashboard Review": "Review dashboard layout, spacing, visuals, labels, and readiness.",
    "DAX Debugging": "Check DAX syntax, logic, references, and cleaner calculation patterns.",
    "Measure Generator": "Suggest useful DAX measures based on your schema and existing measures.",
    "Insight Writer": "Turn dashboard metrics into executive-friendly business insights.",
    "README Writer": "Generate a polished GitHub README for your Power BI project.",
}

DEFAULT_QUESTIONS = {
    "Dashboard Review": "Can you review my dashboard and tell me what looks good, what looks off, and what I should fix before sharing it?",
    "DAX Debugging": "Can you check my DAX measures, fix any issues, and explain what I should change?",
    "Measure Generator": "What other useful DAX measures should I add to this report?",
    "Insight Writer": "Can you write the main business insights from this dashboard?",
    "README Writer": "Can you write a professional GitHub README for this Power BI dashboard project?",
}

OUTPUT_TITLES = {
    "Dashboard Review": "Dashboard Review",
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
You are a Power BI workflow assistant that helps users improve dashboards, DAX measures, data models, business insights, documentation, and BI storytelling.

The selected assistant mode is the highest priority. Always follow the mode-specific instructions provided in the user prompt.

You may receive:
- A selected assistant mode
- A dashboard screenshot
- A table schema
- Existing DAX measures
- A user question

Use the user's provided schema, measures, screenshot, and question to infer the context. Do not assume the dataset is about a specific company, industry, store, sales, finance, or operations unless that information is provided.

If an image is provided, use it as supporting context for the selected mode. Do not automatically perform a dashboard review unless the selected mode is Dashboard Review or the user explicitly asks for a visual critique.

General rules:
- Be specific, practical, and easy to understand.
- Do not assume access to data that was not provided.
- If something cannot be verified from the screenshot, say so.
- Use clean Markdown formatting.
- Use ## section headers.
- Use **bold** for important dashboard elements, measure names, chart titles, and final recommendations.
- Use *italics* only for short emphasis, not full paragraphs.
- Use bullet points or numbered steps when helpful.
- Keep responses concise unless the user asks for detail.
- Do not give long generic Power BI explanations unless the user asks for them.
- Do not use inline code formatting with single backticks for normal words, numbers, values, chart labels, or business insights.
- Only use fenced code blocks with ```DAX for DAX measures.
- For dashboard reviews, insights, and README writing, never wrap normal text or metric values in backticks.
"""

FOLLOW_UP_INSTRUCTIONS = """
You are answering a follow-up question.

Use the previous assistant response as context, but answer the user's latest question directly.

Do not force the selected mode's default Markdown structure unless the user explicitly asks for that format again.

If the user asks to shorten, rewrite, rank, choose, explain, expand, simplify, or transform the previous response, do only that task.

Keep the answer focused on the follow-up request.
"""

MODE_PROMPTS = {
    "Dashboard Review": """
You are in Dashboard Review mode.

Your job is to review the uploaded Power BI dashboard screenshot like a senior BI dashboard reviewer.

Focus only on visible dashboard design and presentation:
- layout
- spacing
- alignment
- KPI cards
- slicers / filters
- chart titles
- color consistency
- readability
- visual hierarchy
- portfolio or presentation readiness

Do not assume the business context. Use only what is visible in the screenshot and what the user provides in the schema or prompt.

Do not focus on DAX or schema unless the user asks.

Use this exact Markdown structure:

## 1. What looks strong
- Mention specific visible dashboard elements that work well.

## 2. What looks unpolished
- Mention specific visible issues with spacing, alignment, colors, titles, labels, slicers, legends, or readability.

## 3. Top 5 changes to make
1. **Change/Improve X** — explain briefly.
2. **Change/Improve X** — explain briefly.
3. **Change/Improve X** — explain briefly.
4. **Change/Improve X** — explain briefly.
5. **Change/Improve X** — explain briefly.

## 4. Readiness score
**Score:** X/10  
**Reason:** Give one short sentence explaining the score.

## 5. Final verdict
Give a short final verdict in 2–3 sentences. State whether the dashboard is ready to share, almost ready, or needs more work.
""",
    "DAX Debugging": """
You are in DAX Debugging mode.

Your job is to review the user's DAX measures and find syntax errors, logic issues, naming problems, or business-definition problems.

Focus on:
- whether the DAX syntax is valid
- whether columns and measures are referenced correctly
- whether the calculation matches the intended business meaning
- whether the measure names are clear
- whether better DAX patterns should be used

Do not assume the dataset is about sales, stores, finance, or operations. Use the table names, column names, existing measures, and user question to infer context.

Do not give dashboard layout feedback unless the user asks.

When suggesting DIVIDE alternate results, explain that 0 is useful for cleaner visuals, while BLANK() may be better when the user wants to avoid showing misleading zero values.

Use this exact Markdown structure:

## 1. Issue found
Explain the problem clearly.

## 2. Why it happens
Explain the DAX or model reason.

## 3. Corrected DAX
```DAX
Corrected measure here
```

## 4. How to verify it
Give a simple way to check if the measure is working in Power BI.
""",
    "Measure Generator": """
You are in Measure Generator mode.

Your job is to suggest useful DAX measures based only on the provided schema and existing measures.

Use the exact table, column, and measure names provided by the user.

Do not assume the dataset is about a specific industry, company, store, product, sales, finance, or operations unless those fields are clearly provided in the schema, measures, screenshot, or user question.

Do not invent new tables, columns, or relationships.
Do not suggest measures that require missing tables or missing columns unless you place them under an optional section called "Optional future improvements."

Important formatting rules:
- Put every DAX measure inside its own fenced code block using ```DAX.
- Do not use inline code formatting for full DAX measures.
- Do not output broken or partial DAX.
- Include a short plain-English explanation after each measure.
- Prioritize practical measures the user can actually add to the current Power BI model.
- Avoid duplicate measures that already exist unless suggesting a better version.
- If a measure depends on another measure, mention that dependency.
- Keep the response focused. Do not overwhelm the user with too many measures.

For time intelligence:
- Do not write final time-intelligence DAX using a Date table unless the schema includes a Date table.
- If only a date column exists in the fact table, explain that a Date table is recommended first.
- Place Date-table-based measures under Optional future improvements.

Every DAX measure must be formatted like this:

```DAX
Measure Name =
DAX expression
```

Use this exact Markdown structure:

## 1. Recommended measures to add first
List the 3–5 most useful measures for the current dataset.

## 2. Core total measures
Provide basic SUM, COUNT, DISTINCTCOUNT, AVERAGE, MIN, or MAX measures only if useful and not already provided.

## 3. Ratio and percentage measures
Provide useful percentage, rate, margin, completion, conversion, or efficiency measures based only on available columns and measures.

## 4. Category comparison measures
Provide comparison measures only for dimensions that exist in the schema, such as category, product, department, region, location, customer, employee, or store.

## 5. Time intelligence measures
Only include these if a Date column or Date table is available. If a Date table is needed, clearly say it is recommended before using advanced time intelligence.

## 6. Recommended dashboard KPIs
List the best existing and new measures to use as KPI cards.

## 7. Optional future improvements
Only include this section if a useful measure would require a table, column, relationship, or target that does not currently exist.
""",
    "Insight Writer": """
You are in Insight Writer mode.

Your job is to write business insights from the dashboard screenshot, schema, DAX measures, and visible metrics.

Focus on business interpretation, not dashboard design critique.

Do not assume the dataset is about restaurants, stores, sales, finance, or operations. Infer the context from the dashboard screenshot, schema, measure names, and user prompt.

Look for:
- trends over time
- high and low performing categories
- major drivers or contributors
- changes in key metrics
- unusual patterns or outliers
- efficiency, performance, or comparison takeaways

Important rules:
- Do not critique layout, colors, spacing, or design unless the user asks.
- Do not overstate trends unless they are clearly visible or supported by the provided data.
- When reading from a screenshot, use careful language like "appears to," "suggests," or "may indicate."
- Do not say a KPI is an average unless the visual explicitly says average.
- Treat KPI cards as totals, averages, percentages, counts, or rates based on their visible labels.
- Keep insights business-friendly and practical.
- Do not use inline code formatting for normal metric values.
- Bold important visible metrics and values when useful, but only use values that are visible in the screenshot or provided by the user.
- Do not invent or hard-code example values.

Formatting rules:
- Do not use inline code formatting.
- Do not wrap numbers, ranges, chart names, KPI values, or business terms in backticks.
- Use **bold** for important metrics or dashboard elements instead of backticks.
- Only use plain text and Markdown bullets/headings.

Use this exact Markdown structure:

## Executive summary
Give 2–3 sentences summarizing the overall business story.

## Key insights
- **Insight 1:** Explain the business meaning.
- **Insight 2:** Explain the business meaning.
- **Insight 3:** Explain the business meaning.

## Recommended actions
- **Action 1:** Practical recommendation based on the data.
- **Action 2:** Practical recommendation based on the data.
- **Action 3:** Practical recommendation based on the data.

## Suggested dashboard callout
Write one short insight sentence the user could place directly on the Power BI report.
""",
    "README Writer": """
You are in README Writer mode.

Your job is to write GitHub README content for a Power BI dashboard project.

Focus on:
- project explanation
- dashboard purpose
- skills showcased
- tools used
- dataset description
- dashboard features
- data disclaimer
- future improvements

Do not assume the project is about a specific company, industry, or dataset unless the user provides that information.

If the screenshot or schema suggests sensitive, private, internal, or company-specific data, include a disclaimer recommending anonymized, synthetic, or sample data for public sharing.

Do not critique the dashboard design unless the user asks.

Do not claim the project uses multiple tables, relationships, star schema, APIs, or advanced modeling unless the user provided that information.

Include a placeholder image section using: ![Dashboard Preview](images/dashboard_preview.png)
Return only the README content, with no extra explanation before or after.

Important formatting rules:
- Return the README as clean Markdown.
- Put the full README inside one fenced code block using ```markdown.
- Use professional but natural wording.
- Avoid sounding too generic.
- Do not invent project details that were not provided.
- If something is unknown, write it generally or label it as optional.
- Fix spelling, grammar, and formatting automatically.

Use this exact Markdown structure:

# Project Title

## Introduction

## Dashboard Overview

## Dashboard Features

## Skills Showcased

## Tools Used

## Data Disclaimer

## Future Improvements
""",
}


# ============================================================
# Styling
# ============================================================
def apply_custom_css() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: linear-gradient(135deg, #0e1117 0%, #111827 45%, #0e1117 100%);
        }

        .block-container {
            max-width: 1250px;
            padding-top: 3rem;
            padding-bottom: 3rem;
        }

        h1, h2, h3 {
            letter-spacing: -0.4px;
        }

        .hero-card {
            background: linear-gradient(135deg, rgba(37, 99, 235, 0.18), rgba(30, 41, 59, 0.55));
            border: 1px solid rgba(96, 165, 250, 0.25);
            border-radius: 22px;
            padding: 24px 28px;
            margin-bottom: 26px;
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.25);
        }

        .hero-title {
            font-size: 34px;
            font-weight: 800;
            margin-bottom: 8px;
        }

        .hero-subtitle {
            color: #cbd5e1;
            font-size: 15px;
        }

        .mode-pill, .output-mode-pill {
            display: inline-block;
            padding: 7px 13px;
            border-radius: 999px;
            background-color: rgba(96, 165, 250, 0.16);
            border: 1px solid rgba(96, 165, 250, 0.35);
            color: #bfdbfe;
            font-size: 13px;
            font-weight: 700;
        }

        .mode-pill {
            margin-top: 14px;
        }

        .output-mode-pill {
            margin-bottom: 22px;
        }

        .feature-row {
            display: flex;
            gap: 10px;
            margin-top: -8px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }

        .feature-pill {
            background: rgba(30, 64, 175, 0.18);
            border: 1px solid rgba(96, 165, 250, 0.35);
            padding: 8px 12px;
            border-radius: 999px;
            color: #dbeafe;
            font-size: 13px;
            font-weight: 650;
        }

        .stTextArea textarea {
            border-radius: 16px !important;
            border: 1px solid #343846 !important;
            background-color: #1f2330 !important;
            padding: 14px !important;
        }

        div[data-baseweb="select"] > div {
            border-radius: 14px !important;
            background-color: #1f2330 !important;
            border: 1px solid #343846 !important;
        }

        section[data-testid="stFileUploader"] {
            background-color: #1f2330;
            border: 1px dashed #3f4454;
            border-radius: 16px;
            padding: 12px;
        }

        div.stButton > button,
        div.stDownloadButton > button {
            border-radius: 999px !important;
            font-weight: 700 !important;
            border: 1px solid #4b5563 !important;
            background: linear-gradient(90deg, #1f2937, #111827) !important;
            color: white !important;
            transition: all 0.2s ease-in-out;
        }

        div.stButton > button:hover,
        div.stDownloadButton > button:hover {
            border-color: #60a5fa !important;
            transform: translateY(-1px);
        }

        div[data-testid="stImage"] {
            background: rgba(30, 41, 59, 0.55);
            border: 1px solid rgba(148, 163, 184, 0.22);
            border-radius: 22px;
            padding: 14px;
            box-shadow: 0 18px 45px rgba(0, 0, 0, 0.38);
        }

        div[data-testid="stImage"] img {
            border-radius: 14px !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(15, 23, 42, 0.55);
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 22px;
            padding: 18px;
            box-shadow: 0 16px 45px rgba(0, 0, 0, 0.22);
        }

        .output-title {
            font-size: 34px;
            font-weight: 800;
            letter-spacing: -0.6px;
            margin-bottom: 4px;
        }

        .feedback-card h2,
        div[data-testid="stVerticalBlockBorderWrapper"] h2 {
            font-size: 26px !important;
            margin-top: 24px !important;
        }

        hr {
            border-color: #2f3542;
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
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_inputs() -> None:
    st.session_state.schema_input = ""
    st.session_state.dax_input = ""
    st.session_state.assistant_response = ""
    st.session_state.response_mode = ""
    st.session_state.response_history = []


MAX_CONTEXT_CHARS = 8000  # Limit context file text to prevent excessively long inputs
def read_uploaded_context_file(uploaded_file) -> str:
    if uploaded_file is None:
        return ""

    try:
        file_bytes = uploaded_file.getvalue()
        text = file_bytes.decode("utf-8")

        if len(text) > MAX_CONTEXT_CHARS:
            return text[:MAX_CONTEXT_CHARS] + "\n\n[Context file truncated for length.]"

        return text

    except UnicodeDecodeError:
        return "The uploaded context file could not be decoded as UTF-8 text."
    except Exception as e:
        return f"Error reading uploaded context file: {e}"


def load_sample_inputs() -> None:
    st.session_state.schema_input = SAMPLE_SCHEMA
    st.session_state.dax_input = SAMPLE_DAX
    st.session_state.assistant_response = ""
    st.session_state.response_mode = ""


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


def call_openai(user_prompt: str, image_data_url: str | None = None) -> str:
    if image_data_url:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": user_prompt},
                        {"type": "input_image", "image_url": image_data_url},
                    ],
                },
            ],
        )
    else:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

    return response.output_text


# ============================================================
# UI sections
# ============================================================
def render_header() -> None:
    st.markdown(
        """
        <div class="hero-card">
            <div class="hero-title">📊 BI Report Assistant</div>
            <div class="hero-subtitle">
                Review Power BI dashboards, debug DAX, generate measures, write insights, and create project documentation.
            </div>
            <div class="mode-pill">AI-powered Power BI workflow assistant</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="feature-row">
            <span class="feature-pill">🖼️ Screenshot-aware</span>
            <span class="feature-pill">📐 DAX + schema context</span>
            <span class="feature-pill">📝 Exportable outputs</span>
            <span class="feature-pill">⚡ Multi-mode workflow</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

def has_report_context(
    uploaded_image,
    uploaded_context_file,
    schema_text: str,
    dax_text: str,
) -> bool:
    return any(
        [
            uploaded_image is not None,
            uploaded_context_file is not None,
            schema_text.strip(),
            dax_text.strip(),
        ]
    )

def render_context_column():
    st.subheader("Report Context")

    with st.expander("How do I provide Power BI context?"):
        st.markdown(
            """
            You can give the assistant context in any of these ways:

            **1. Upload a screenshot**
            - Best for dashboard layout reviews, visual feedback, and business insights.

            **2. Paste schema/data context**
            Include:
            - Table names
            - Column names
            - Data types
            - Short notes about what the data represents

            **3. Paste current DAX measures**
            Include any existing measures you want reviewed, improved, or used as context.

            **4. Upload a context file**
            Supported files:
            - `.txt`
            - `.md`
            - `.csv`
            - `.json`

            Good context files include exported measures, data dictionaries, schema notes, or model documentation.
            """
        )

    uploaded_image = st.file_uploader(
        "Upload your Power BI screenshot",
        type=["png", "jpg", "jpeg"],
    )

    uploaded_context_file = st.file_uploader(
        "Upload optional context file",
        type=["txt", "md", "csv", "json"],
        help="Upload a schema, data dictionary, exported measures, or report notes file."
    )
    if uploaded_context_file:
        st.success(f"Loaded context file: {uploaded_context_file.name}")

        context_preview = read_uploaded_context_file(uploaded_context_file)

        with st.expander("Preview uploaded context"):
            st.text(context_preview[:2000])    

    mode = st.selectbox("Assistant Mode", ASSISTANT_MODES)
    st.caption(MODE_DESCRIPTIONS.get(mode, ""))

    schema_text = st.text_area(
        "Schema / Data Context",
        height=180,
        placeholder="Table: business_performance_data\nColumns:\nDate - Date\nCategory - Text\nRevenue - Currency\nCost - Currency...",
        key="schema_input",
    )

    dax_text = st.text_area(
        "Current DAX Measures",
        height=220,
        placeholder="Total Revenue = SUM(business_performance_data[Revenue])",
        key="dax_input",
    )

    button_col1, button_col2 = st.columns(2)
    with button_col1:
        st.button("Load Sample", on_click=load_sample_inputs, use_container_width=True)
    with button_col2:
        st.button("Reset Inputs", on_click=reset_inputs, use_container_width=True)

    return uploaded_image, uploaded_context_file, mode, schema_text, dax_text


def render_preview_column(uploaded_image) -> str | None:
    image_data_url = None

    if uploaded_image:
        st.subheader("Dashboard Preview")
        image = Image.open(uploaded_image)
        st.image(image, use_container_width=True)
        image_data_url = image_to_data_url(uploaded_image)
    else:
        st.subheader("Upload a Screenshot")
        st.caption("Upload a Power BI screenshot to enable visual review and screenshot-based insights.")
        st.info("The assistant can still help with DAX, measures, insights, and README writing without a screenshot.")

    return image_data_url


def render_prompt_section(mode: str) -> tuple[str, bool]:
    st.markdown("---")
    prompt_col1, prompt_col2, prompt_col3 = st.columns([0.22, 0.56, 0.22])

    with prompt_col2:
        st.markdown(
            """
            <div style="
                height: 3px;
                width: 200px;
                background: linear-gradient(90deg, #60a5fa, #a78bfa);
                border-radius: 999px;
                margin-bottom: 14px;
            "></div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("### Ask the Assistant")
        st.caption("Use the selected mode to review, debug, generate, or summarize your report.")

        default_question = DEFAULT_QUESTIONS.get(mode, "What do you need help with?")
        user_question = st.text_area(
            "Message",
            value=default_question,
            height=110,
            label_visibility="collapsed",
        )
        use_latest_response = st.checkbox(
            "Use latest response as context",
            value=False,
            help="Include the most recent assistant response when asking a follow-up question."
)
        analyze_clicked = st.button("Analyze Report →", use_container_width=True)

    return user_question, analyze_clicked, use_latest_response


def render_output_section() -> None:
    if not st.session_state.assistant_response:
        return

    st.divider()
    output_col1, output_col2, output_col3 = st.columns([0.08, 0.84, 0.08])

    with output_col2:
        with st.container(border=True):
            output_title = OUTPUT_TITLES.get(
                st.session_state.response_mode,
                "Assistant Feedback",
            )

            st.markdown(
                f"""
                <div class="output-title">{output_title}</div>
                <div class="output-mode-pill">Generated using {st.session_state.response_mode} mode</div>
                """,
                unsafe_allow_html=True,
            )

            response_mode = st.session_state.response_mode
            response_text = st.session_state.assistant_response

            if response_mode == "README Writer":
                st.code(response_text, language="markdown")
            elif response_mode in ["DAX Debugging", "Measure Generator"]:
                st.markdown(response_text)
            else:
                st.markdown(clean_non_code_output(response_text))

            download_label, download_file_name, download_data = get_download_info(
                response_mode,
                response_text,
            )

            button_col1, button_col2 = st.columns(2)
            with button_col1:
                st.download_button(
                    label=download_label,
                    data=download_data,
                    file_name=download_file_name,
                    mime="text/markdown",
                    use_container_width=True,
                )
            with button_col2:
                if st.button("Clear Output", use_container_width=True):
                    st.session_state.assistant_response = ""
                    st.session_state.response_mode = ""
                    st.rerun()

def render_history_section() -> None:
    if not st.session_state.response_history:
        return

    st.divider()

    history_col1, history_col2 = st.columns([0.78, 0.22])

    with history_col1:
        st.subheader("Response History")

    with history_col2:
        if st.button("Clear History", use_container_width=True):
            st.session_state.response_history = []
            st.rerun()

    for index, item in enumerate(reversed(st.session_state.response_history), start=1):
        with st.expander(f"{index}. {item['mode']} — {item['question'][:80]}"):
            st.markdown(item["response"])

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
    
    context_file_text = read_uploaded_context_file(uploaded_context_file)

    with right_col:
        image_data_url = render_preview_column(uploaded_image)

    user_question, analyze_clicked, use_latest_response = render_prompt_section(mode)

    if analyze_clicked:
            if not user_question.strip():
                st.warning("Please enter a question or request for analysis.")

            elif not has_report_context(
                uploaded_image=uploaded_image,
                uploaded_context_file=uploaded_context_file,
                schema_text=schema_text,
                dax_text=dax_text,
    ):
                st.warning(
                    "Please upload a screenshot, upload a context file, paste schema/data context, or paste DAX measures before analyzing."
                )

            else:
                with st.spinner("Analyzing your report..."):

                    previous_response_text = (
                        st.session_state.assistant_response
                        if use_latest_response
                        else ""
                    )
                    user_prompt = build_user_prompt(
                        mode=mode,
                        user_question=user_question,
                        schema_text=schema_text,
                        dax_text=dax_text,
                        context_file_text=context_file_text,
                        previous_response_text=previous_response_text,
                    )

                    try:
                        output_text = call_openai(user_prompt, image_data_url)
                        st.session_state.assistant_response = output_text
                        st.session_state.response_mode = mode
                        st.session_state.response_history.append(
                        {
                            "mode": mode,
                            "question": user_question,
                            "response": output_text,
                    }
)

                    except Exception as e:
                        st.error("Something went wrong while calling the AI.")
                        st.code(str(e))

    render_output_section()
    render_history_section()


if __name__ == "__main__":
    main()
