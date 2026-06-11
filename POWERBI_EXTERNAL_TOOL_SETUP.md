# Power BI External Tool — Setup Guide

> **Most users should use the Windows installer instead.**
> Download `BI-Report-Assistant-Setup-1.0.0.exe` from [Releases](https://github.com/MattQ05/bi-report-assistant/releases/latest) — it handles everything automatically.
>
> This guide is for developers building from source or advanced users who need to register the tool manually.

---

## How it works

When you click the **BI Report Assistant** button in Power BI's External Tools ribbon, Power BI Desktop calls:

```
bi_report_assistant.exe --server <server> --database <database>
```

Power BI passes the local Analysis Services server address and database ID as arguments. The launcher:

1. Writes the connection details to `powerbi_context.txt` in `%APPDATA%\BI Report Assistant\`
2. Runs `extract_powerbi_metadata.py` which connects via ADOMD.NET and extracts tables, columns, measures, and relationships to `powerbi_model_context.txt`
3. Starts the Streamlit app and opens your browser at `http://localhost:8501`
4. The app reads `powerbi_model_context.txt` and shows the connected model card automatically

---

## Building from source

### Prerequisites

- Python 3.10+
- [Inno Setup 6](https://jrsoftware.org/isinfo.php)
- [PyInstaller](https://pyinstaller.org) — installed automatically by `build.bat`
- ADOMD.NET 16.0 — install via [SSMS](https://learn.microsoft.com/en-us/sql/ssms/download-sql-server-management-studio-ssms)

### Build

```bash
git clone https://github.com/MattQ05/bi-report-assistant
cd bi-report-assistant
build.bat
```

The installer is output to `installer_output\BI-Report-Assistant-Setup-1.0.0.exe`.

---

## Manual External Tool registration

If you need to register the tool manually without the installer:

### 1 — Find the External Tools folder

```
C:\Program Files (x86)\Common Files\Microsoft Shared\Power BI Desktop\External Tools\
```

Create it if it doesn't exist.

### 2 — Create the registration file

Create `BI Report Assistant.pbitool.json` in that folder:

```json
{
  "version": "1.0.0",
  "name": "BI Report Assistant",
  "description": "AI-powered Power BI workflow assistant",
  "path": "C:\\Program Files (x86)\\BI Report Assistant\\bi_report_assistant.exe",
  "arguments": "--server \"%server%\" --database \"%database%\"",
  "iconData": ""
}
```

Update `path` to match your actual install location.

### 3 — Restart Power BI Desktop

The tool will appear in the External Tools ribbon on next launch.

---

## Re-running setup

To update your API key or re-register the External Tool at any time:

```
"C:\Program Files (x86)\BI Report Assistant\bi_report_assistant.exe" --setup
```

---

## Troubleshooting

**Tool doesn't appear in the ribbon**
- Confirm the `.pbitool.json` is in the correct External Tools folder
- Validate the JSON at [jsonlint.com](https://jsonlint.com)
- Fully close and reopen Power BI Desktop

**Model not connecting**
- Check `%APPDATA%\BI Report Assistant\` — `powerbi_context.txt` and `powerbi_model_context.txt` should appear after clicking the button
- ADOMD.NET must be installed — get it via [SSMS](https://learn.microsoft.com/en-us/sql/ssms/download-sql-server-management-studio-ssms)
- Run setup again: `bi_report_assistant.exe --setup` — verify the ADOMD DLL path is detected

**Port 8501 already in use**
- Another Streamlit instance is running. Close it or wait for it to stop.

**Switching between reports**
- Open the new report in Power BI Desktop and click the External Tools button again — the model context updates automatically
- Or click **↻ Refresh Model** inside the app while the correct file is open