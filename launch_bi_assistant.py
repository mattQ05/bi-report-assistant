import argparse
import os
import subprocess
import sys
import webbrowser
from pathlib import Path


def write_powerbi_context(server: str, database: str) -> Path:
    context_folder = Path(__file__).resolve().parent
    context_folder.mkdir(parents=True, exist_ok=True)

    context_file = context_folder / "powerbi_context.txt"

    context_file.write_text(
        f"""Power BI Desktop Context

Server:
{server}

Database:
{database}

Notes:
This file was generated from the Power BI External Tools ribbon.
The next phase will use this server and database connection to extract tables, columns, measures, and relationships automatically.
""",
        encoding="utf-8",
    )

    return context_file



def start_streamlit_app(project_folder: Path) -> None:
    app_path = project_folder / "app.py"

    if not app_path.exists():
        raise FileNotFoundError(f"Could not find app.py at: {app_path}")

    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(app_path),
        ],
        cwd=str(project_folder),
        shell=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", required=False, default="")
    parser.add_argument("--database", required=False, default="")
    args = parser.parse_args()

    project_folder = Path(__file__).resolve().parent

    context_file = write_powerbi_context(args.server, args.database)

    print(f"Power BI context written to: {context_file}")

    extractor_script = project_folder / "extract_powerbi_metadata.py"

    if extractor_script.exists():
        try:
            subprocess.run(
                [sys.executable, str(extractor_script)],
                cwd=str(project_folder),
                check=True,
            )
            print("Power BI metadata extraction completed.")
        except Exception as e:
            print(f"Power BI metadata extraction failed: {e}")
            
    start_streamlit_app(project_folder)

    # webbrowser.open("http://localhost:8501")


if __name__ == "__main__":
    main()