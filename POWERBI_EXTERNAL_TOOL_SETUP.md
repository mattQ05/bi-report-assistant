# Power BI External Tool Setup

This guide explains how to use **BI Report Assistant** directly from **Power BI Desktop** through the **External Tools** ribbon.

When set up correctly, you can open a PBIX file, click **BI Report Assistant**, and the app will automatically extract model context such as:

- Tables
- Columns
- Measures
- DAX expressions
- Relationships

This local setup is different from the hosted Streamlit app. The hosted app supports manual uploads, but direct Power BI Desktop model extraction must run locally on your computer.

---

## Requirements

Before starting, make sure you have:

- Windows
- Power BI Desktop
- Python 3.10 or newer
- Git
- Microsoft ADOMD.NET / Analysis Services client libraries
- An OpenAI API key

---

## 1. Clone the repository

Open PowerShell or VS Code terminal and run:

```powershell
git clone https://github.com/YOUR-USERNAME/bi-report-assistant.git
cd bi-report-assistant
```

Replace `YOUR-USERNAME` with your GitHub username.

---

## 2. Create a virtual environment

```powershell
python -m venv .venv
```

Activate it:

```powershell
.venv\Scripts\activate
```

You should see `(.venv)` at the beginning of your terminal line.

---

## 3. Install local dependencies

```powershell
pip install -r requirements-local.txt
```

The local requirements include the normal Streamlit app dependencies plus the Python package needed for Power BI Desktop model extraction.

---

## 4. Install Microsoft ADOMD.NET

BI Report Assistant connects to the local Power BI Desktop model through Microsoft ADOMD.NET.

Install the Microsoft Analysis Services client libraries.

After installing, confirm that this file exists or find your installed version:

```text
C:\Program Files\Microsoft.NET\ADOMD.NET\160\Microsoft.AnalysisServices.AdomdClient.dll
```

Your version folder may be different, such as `150` or `160`.

To search for it in PowerShell:

```powershell
Get-ChildItem "C:\Program Files" -Recurse -Filter "Microsoft.AnalysisServices.AdomdClient.dll" -ErrorAction SilentlyContinue
```

Copy the full path if it is different from the default path.

---

## 5. Create your `.env` file

Create a file named `.env` in the project root.

Add:

```text
OPENAI_API_KEY=your_openai_api_key_here
ADOMD_DLL_PATH=C:\Program Files\Microsoft.NET\ADOMD.NET\160\Microsoft.AnalysisServices.AdomdClient.dll
```

If your ADOMD.NET DLL is in a different location, update `ADOMD_DLL_PATH`.

Do not upload your `.env` file to GitHub.

---

## 6. Update the External Tool JSON file

Open:

```text
BI Report Assistant.pbitool.json
```

Make sure the paths point to your local project folder.

Example:

```json
{
  "version": "1.0.0",
  "name": "BI Report Assistant",
  "description": "Launches BI Report Assistant from Power BI Desktop.",
  "path": "C:\\Users\\YOUR-NAME\\Documents\\bi-report-assistant\\.venv\\Scripts\\python.exe",
  "arguments": "C:\\Users\\YOUR-NAME\\Documents\\bi-report-assistant\\launch_bi_assistant.py --server \"%server%\" --database \"%database%\"",
  "iconData": ""
}
```

Update this project path:

```text
C:\Users\YOUR-NAME\Documents\bi-report-assistant
```

to match your actual project location.

For example:

```text
C:\Users\matt0\OneDrive\Documents\bi-report-assistant
```

---

## 7. Register the External Tool with Power BI Desktop

Copy:

```text
BI Report Assistant.pbitool.json
```

to this folder:

```text
C:\Program Files (x86)\Common Files\Microsoft Shared\Power BI Desktop\External Tools
```

If the folder does not exist, create it.

You may need administrator permission to copy the file there.

---

## 8. Restart Power BI Desktop

Fully close Power BI Desktop.

Reopen Power BI Desktop.

Open a PBIX file.

You should now see:

```text
External Tools → BI Report Assistant
```

---

## 9. Launch BI Report Assistant

In Power BI Desktop:

```text
External Tools → BI Report Assistant
```

When clicked, the launcher should:

1. Capture the current Power BI server and database connection.
2. Save `powerbi_context.txt`.
3. Run `extract_powerbi_metadata.py`.
4. Save `powerbi_model_context.txt`.
5. Launch the Streamlit app locally.
6. Auto-load the connected Power BI model context.

The Streamlit app should open at:

```text
http://localhost:8501
```

---

## 10. Confirm it worked

In the app, look for the connected model card:

```text
Connected Power BI Model
Tables
Columns
Measures
Relationships
```

If the card appears, the external tool integration is working.

You can now ask questions like:

```text
Review my connected Power BI model and tell me what looks good, what needs improvement, and whether the model structure is clean.
```

or:

```text
Based on the connected model context, what useful DAX measures should I add?
```

---

## Refreshing the connected model

If you change your PBIX model while Power BI Desktop is still open, click:

```text
Refresh Connected Model
```

inside the Streamlit app.

This reruns the metadata extractor and updates the connected model context.

If you close Power BI Desktop or open a different PBIX file, launch BI Report Assistant again from the Power BI External Tools ribbon so the server and database connection are refreshed.

---

## Generated local files

The external tool may generate these files:

```text
powerbi_context.txt
powerbi_model_context.txt
```

These files are created locally and should not be committed to GitHub.

Make sure your `.gitignore` includes:

```text
powerbi_context.txt
powerbi_model_context.txt
.env
.venv/
__pycache__/
*.pyc
.streamlit/secrets.toml
```

---

## Troubleshooting

### BI Report Assistant does not show in Power BI Desktop

Check that the `.pbitool.json` file is copied to:

```text
C:\Program Files (x86)\Common Files\Microsoft Shared\Power BI Desktop\External Tools
```

Then restart Power BI Desktop.

---

### The app opens, but no model context appears

Make sure:

- A PBIX file is open.
- You launched the app from Power BI Desktop External Tools.
- `powerbi_context.txt` was created.
- `powerbi_model_context.txt` was created.
- Power BI Desktop is still open.

---

### ADOMD.NET error

If you see an error about `Microsoft.AnalysisServices.AdomdClient.dll`, check your `.env` file:

```text
ADOMD_DLL_PATH=C:\Program Files\Microsoft.NET\ADOMD.NET\160\Microsoft.AnalysisServices.AdomdClient.dll
```

If your DLL is somewhere else, update the path.

To find it:

```powershell
Get-ChildItem "C:\Program Files" -Recurse -Filter "Microsoft.AnalysisServices.AdomdClient.dll" -ErrorAction SilentlyContinue
```

---

### OpenAI API key error

Make sure `.env` contains:

```text
OPENAI_API_KEY=your_openai_api_key_here
```

Then restart the app.

---

### Power BI connection fails

Make sure Power BI Desktop is open and the PBIX file is still loaded.

Power BI Desktop creates a temporary local Analysis Services connection. If Power BI Desktop closes, the connection disappears.

---

## Notes

The Power BI External Tool workflow is intended for local use on Windows with Power BI Desktop.

The hosted Streamlit version cannot directly connect to a user’s local PBIX model. For direct Power BI model extraction, users must run this local setup.
