# BI Report Assistant

BI Report Assistant is an AI-powered Streamlit application that helps Power BI users review dashboards, debug DAX measures, generate new measures, write business insights, and create project documentation.

The app allows users to upload a Power BI screenshot, provide schema or DAX context, upload optional text-based context files, and ask targeted questions using different assistant modes.

## Features

### Dashboard Review

Upload a Power BI dashboard screenshot and receive feedback on:

- Layout
- Spacing
- KPI placement
- Chart readability
- Visual hierarchy
- Colors and design consistency
- Presentation readiness

### DAX Debugging

Paste DAX measures and get help with:

- Syntax issues
- Measure logic
- Naming clarity
- Better DAX patterns
- Safer `DIVIDE()` usage
- Simple verification steps

### Measure Generator

Generate useful DAX measures based on the provided schema and existing measures.

The assistant can suggest:

- Core totals
- Ratio and percentage measures
- Category comparison measures
- Time intelligence recommendations
- KPI card ideas

### Insight Writer

Turn dashboard metrics into business-friendly insights, including:

- Executive summaries
- Key insights
- Recommended actions
- Dashboard callout text

### README Writer

Generate a professional GitHub README for a Power BI dashboard project using the provided dashboard context.

### Optional Context File Upload

Users can upload supporting files such as:

- `.txt`
- `.md`
- `.csv`
- `.json`

These files can contain schema notes, data dictionaries, exported measures, or project documentation.

### Response History

The app stores generated responses during the session so users can review previous outputs and ask follow-up questions.

### Exportable Outputs

Generated responses can be downloaded as Markdown files for use in reports, documentation, or GitHub projects.

## Tech Stack

- Python
- Streamlit
- OpenAI API
- Pillow
- python-dotenv

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/YOUR-USERNAME/bi-report-assistant.git
cd bi-report-assistant
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

### 3. Activate the virtual environment

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Create a `.env` file

Create a file named `.env` in the root folder and add your OpenAI API key:

```text
OPENAI_API_KEY=your_api_key_here
```

### 6. Run the app

```bash
streamlit run app.py
```

## How to Use

1. Upload a Power BI screenshot if you want visual dashboard feedback.
2. Paste schema or data context into the schema box.
3. Paste DAX measures into the DAX box.
4. Optionally upload a context file.
5. Select an assistant mode.
6. Ask a question.
7. Click **Analyze Report**.
8. Review, download, or continue refining the response.

## Example Prompts

### Dashboard Review

```text
Can you review my dashboard and tell me what looks good, what looks off, and what I should fix before sharing it?
```

### DAX Debugging

```text
Can you check my DAX measures, fix any issues, and explain what I should change?
```

### Measure Generator

```text
Using only the uploaded context file, suggest 5 useful DAX measures I should add to this dashboard.
```

### Insight Writer

```text
Can you write the main business insights from this dashboard?
```

### README Writer

```text
Can you write a professional GitHub README for this Power BI dashboard project?
```

## Environment Variables

This project uses an OpenAI API key stored locally in a `.env` file.

Do not upload your `.env` file to GitHub.

Recommended `.gitignore`:

```text
.env
.venv/
__pycache__/
*.pyc
.streamlit/secrets.toml
```

## Data Privacy Notes

This app is designed for sample, anonymized, or non-sensitive dashboard context.

Before uploading files or screenshots, users should remove:

- Confidential company data
- Customer information
- Internal financial data
- Private business strategy
- Personally identifiable information

## Future Improvements

Potential future enhancements include:

- Direct Power BI metadata extraction
- More advanced chat-style follow-up behavior
- Project-level saved sessions
- PDF export for generated reports
- Improved support for larger model documentation files
- More advanced context parsing for schema and DAX files
- Streamlit Cloud deployment

## Disclaimer

This tool is intended to support Power BI workflow improvement, dashboard review, and BI documentation. AI-generated suggestions should be reviewed before being used in professional, academic, or business settings.
