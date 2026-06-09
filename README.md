# BI Report Assistant

An AI-powered workflow tool for Power BI developers. Review dashboards, audit data models, debug DAX measures, generate business insights, and write documentation — all from a single interface connected directly to your open PBIX file.

Built with Streamlit and the OpenAI API. Runs locally as a Power BI External Tool or in the cloud via Streamlit Cloud.

---

## What it does

BI Report Assistant gives you six focused AI modes, each tailored to a specific stage of the Power BI workflow:

| Mode | What it does |
|---|---|
| **Dashboard Review** | Reviews layout, visual hierarchy, spacing, and presentation readiness |
| **Model Review** | Audits table structure, relationships, naming, and star schema design |
| **DAX Debugging** | Finds syntax errors, logic issues, and missing patterns across all measures |
| **Measure Generator** | Suggests practical DAX measures based on your schema and existing measures |
| **Insight Writer** | Turns dashboard metrics into executive-ready business insights |
| **README Writer** | Writes a polished GitHub README for your Power BI project |

---

## Two ways to use it

### Local — Connected Model (recommended)

When launched from Power BI Desktop via the External Tools ribbon, the app automatically extracts your live model — tables, columns, measures, relationships — and loads it as context. No copying and pasting.

<img src="images/external_tool.png" alt="BI Report Assistant in the Power BI External Tools ribbon"/>

Once connected, the assistant reads your model directly:

<img src="images/local_app.png" alt="Local app with connected Power BI model" width="700"/>

### Cloud — Paste Context

Use the app from anywhere by pasting your schema and DAX measures manually, or uploading a dashboard screenshot. No Power BI Desktop required.

<img src="images/cloud_app.png" alt="Cloud version with manual context input" width="700"/>

---

## Features

- **Live model connection** — extracts tables, columns, measures, and relationships from the open PBIX file via ADOMD.NET. Shows sync timestamp and object counts on the model card.
- **Streaming responses** — output appears word by word as the model generates it, with mode-specific loading messages.
- **Smart model routing** — uses `gpt-4o` for vision-based modes (Dashboard Review, Insight Writer) and `gpt-4o-mini` for structured analytical modes, automatically.
- **Per-mode output tabs** — responses from different modes are kept as separate tabs so switching modes doesn't lose previous output.
- **Active context summary** — shows exactly what the assistant has loaded before you submit: connected model, screenshot, schema, DAX, or uploaded file.
- **Mode-aware UI** — the preview column, pipeline steps, and suggested prompts all adapt to the selected mode.
- **Session export** — download all responses from a session as a single Markdown document.
- **DAX formatter** — normalises keyword casing in pasted DAX before sending to the API.
- **Response history with re-run** — every response is stored in history with a Re-run button to reload the question and mode instantly.

---

## Screenshots

### Blank report — getting started

<img src="images/blank_report.png" alt="App on first load with onboarding" width="700"/>

### Output — Dashboard Review

<img src="images/output.png" alt="Dashboard Review output" width="700"/>

### Response history

<img src="images/response_history.png" alt="Response history with re-run buttons" width="700"/>

---

## Setup

### Prerequisites

- Python 3.10+
- An OpenAI API key — [platform.openai.com](https://platform.openai.com)
- Power BI Desktop (local mode only)
- ADOMD.NET 16.0 (local mode only) — installed with [SQL Server Management Studio](https://learn.microsoft.com/en-us/sql/ssms/download-sql-server-management-studio-ssms) or the Analysis Services client

---

### Cloud / Streamlit deployment

```bash
git clone https://github.com/yourusername/bi-report-assistant
cd bi-report-assistant
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your key:

```
OPENAI_API_KEY=sk-...
BI_ASSISTANT_CLOUD=true
```

Run:

```bash
streamlit run app.py
```

---

### Local — Power BI External Tool

Install local dependencies:

```bash
pip install -r requirements-local.txt
```

Copy `.env.example` to `.env` and add your key:

```
OPENAI_API_KEY=sk-...
```

Then follow the setup guide to register the app as a Power BI External Tool:

📄 **[POWERBI_EXTERNAL_TOOL_SETUP.md](POWERBI_EXTERNAL_TOOL_SETUP.md)**

Once registered, the tool appears in the **External Tools** ribbon in Power BI Desktop. Clicking it launches the app and automatically loads the open model.

---

## Project structure

```
bi-report-assistant/
├── app.py                          # Main Streamlit application
├── launch_bi_assistant.py          # External tool launcher — writes context and starts app
├── extract_powerbi_metadata.py     # ADOMD.NET metadata extractor
├── BI Report Assistant.pbitool.json # Power BI External Tool registration file
├── images/                         # Screenshots used in this README
├── requirements.txt                # Cloud/Streamlit dependencies
├── requirements-local.txt          # Local dependencies (includes pythonnet)
├── .env.example                    # Environment variable template
└── POWERBI_EXTERNAL_TOOL_SETUP.md  # Step-by-step External Tool setup guide
```

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Yes | Your OpenAI API key |
| `BI_ASSISTANT_CLOUD` | No | Set to `true` to enable cloud mode (hides model connection UI) |
| `ADOMD_DLL_PATH` | No | Path to `Microsoft.AnalysisServices.AdomdClient.dll` if not in the default location |

---

## Tech stack

- [Streamlit](https://streamlit.io) — UI framework
- [OpenAI API](https://platform.openai.com) — `gpt-4o` and `gpt-4o-mini` with streaming
- [pythonnet](https://github.com/pythonnet/pythonnet) — .NET interop for ADOMD.NET (local mode)
- [ADOMD.NET](https://learn.microsoft.com/en-us/analysis-services/adomd/mpp/adomd-net-client-functionality) — Power BI model metadata extraction
- [Pillow](https://pillow.readthedocs.io) — screenshot processing

---

## Data and privacy

This app sends your Power BI schema, DAX measures, and optionally a dashboard screenshot to the OpenAI API for analysis. No data is stored by this application. Review [OpenAI's data usage policies](https://openai.com/policies/api-data-usage-policies) before using with sensitive or proprietary data.

Do not use real company data, customer information, or confidential business metrics without reviewing your organisation's policies on external AI tool usage.