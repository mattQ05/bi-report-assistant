# Power BI External Tool Setup

This guide walks through registering BI Report Assistant as a Power BI External Tool so it appears in the **External Tools** ribbon in Power BI Desktop and launches with your model pre-loaded.

---

## Prerequisites

Before starting, make sure you have:

- **Python 3.10 or later** installed and on your system PATH
- **Power BI Desktop** installed (Microsoft Store or installer version)
- **ADOMD.NET 16.0** — the DLL that lets the app connect to Power BI's local Analysis Services instance

### Installing ADOMD.NET

The easiest way to get the right version is to install **SQL Server Management Studio (SSMS)**, which bundles it:

👉 [Download SSMS](https://learn.microsoft.com/en-us/sql/ssms/download-sql-server-management-studio-ssms)

After installation, confirm the DLL exists at:
```
C:\Program Files\Microsoft.NET\ADOMD.NET\160\Microsoft.AnalysisServices.AdomdClient.dll
```

If it's at a different path, set `ADOMD_DLL_PATH` in your `.env` file.

---

## Step 1 — Install the app

Clone or download the repository, then install local dependencies:

```bash
cd bi-report-assistant
pip install -r requirements-local.txt
```

---

## Step 2 — Add your API key

Copy `.env.example` to `.env`:

```bash
copy .env.example .env
```

Open `.env` and add your OpenAI API key:

```
OPENAI_API_KEY=sk-...
```

Leave `BI_ASSISTANT_CLOUD` unset or set to `false` for local use.

---

## Step 3 — Register the External Tool

Power BI Desktop discovers external tools by reading `.pbitool.json` files from a specific folder.

### Find the External Tools folder

The folder is typically:
```
C:\Program Files (x86)\Common Files\Microsoft Shared\Power BI Desktop\External Tools\
```

If the `External Tools` folder doesn't exist, create it.

### Copy the tool registration file

Copy `BI Report Assistant.pbitool.json` from the project folder into the External Tools folder:

```
C:\Program Files (x86)\Common Files\Microsoft Shared\Power BI Desktop\External Tools\BI Report Assistant.pbitool.json
```

### Update the file paths inside it

Open `BI Report Assistant.pbitool.json` in a text editor and update two values:

```json
{
  "version": "1.0.0",
  "name": "BI Report Assistant",
  "description": "AI-powered Power BI workflow assistant",
  "path": "C:\\path\\to\\your\\python.exe",
  "arguments": "\"C:\\path\\to\\bi-report-assistant\\launch_bi_assistant.py\" --server \"%server%\" --database \"%database%\"",
  "iconData": "..."
}
```

- **`path`** — the full path to your Python executable. Find it by running `where python` in a terminal.
- **`arguments`** — the full path to `launch_bi_assistant.py` in the project folder.

#### Example (adjust to your actual paths):

```json
"path": "C:\\Users\\Matthew\\Documents\\bi-report-assistant\\.venv\\Scripts\\python.exe",
"arguments": "\"C:\\Users\\Matthew\\Documents\\bi-report-assistant\\launch_bi_assistant.py\" --server \"%server%\" --database \"%database%\""
```

> **Tip:** Use the Python executable inside your virtual environment (`.venv\Scripts\python.exe`) rather than the system Python to ensure all dependencies are available.

---

## Step 4 — Restart Power BI Desktop

Close and reopen Power BI Desktop. Open any `.pbix` file.

You should now see **BI Report Assistant** in the **External Tools** ribbon:

![External Tools ribbon](images/external_tool.png)

---

## Step 5 — Launch the tool

1. Open the report you want to work with in Power BI Desktop
2. Click **BI Report Assistant** in the External Tools ribbon
3. The app will:
   - Write the model's server and database connection to `powerbi_context.txt`
   - Extract tables, columns, measures, and relationships to `powerbi_model_context.txt`
   - Launch the Streamlit app at `http://localhost:8501`
4. Your browser will open (or navigate to `http://localhost:8501` manually)
5. The connected model card will appear with your model's stats

---

## How it works

When you click the External Tool button, Power BI Desktop calls:

```
python launch_bi_assistant.py --server <server> --database <database>
```

Power BI passes the local Analysis Services server address and database name as arguments. `launch_bi_assistant.py` writes these to `powerbi_context.txt`, then runs `extract_powerbi_metadata.py` which connects via ADOMD.NET and extracts the full model schema to `powerbi_model_context.txt`. The Streamlit app reads this file and loads it as context automatically.

---

## Troubleshooting

**The tool doesn't appear in the ribbon**
- Confirm the `.pbitool.json` file is in the correct External Tools folder
- Check the JSON is valid (no trailing commas, correct quotes) — use [jsonlint.com](https://jsonlint.com)
- Restart Power BI Desktop after adding the file

**The app opens but the model isn't connected**
- Check that `powerbi_model_context.txt` was created in the project folder
- Open a terminal and run `python extract_powerbi_metadata.py` manually to see the error output
- Verify ADOMD.NET is installed and the DLL path is correct

**`ModuleNotFoundError: pythonnet`**
- Run `pip install -r requirements-local.txt` using the same Python that's referenced in the `.pbitool.json`

**Port 8501 already in use**
- Another Streamlit app is running. Stop it, or add `--server.port 8502` to the `arguments` in the `.pbitool.json`

**`FileNotFoundError` for the ADOMD DLL**
- Set `ADOMD_DLL_PATH` in your `.env` file to the actual path of `Microsoft.AnalysisServices.AdomdClient.dll` on your machine

---

## Switching between reports

The connected model context is tied to whichever PBIX file was open when you last clicked the External Tool button.

To switch to a different report:
1. Open the new report in Power BI Desktop
2. Click **BI Report Assistant** in the External Tools ribbon again
3. The app will re-extract the model and update the context automatically

You can also click **↻ Refresh Model** inside the app to re-extract without relaunching, as long as the same file is still open.