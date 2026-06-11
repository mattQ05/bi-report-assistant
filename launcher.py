"""
BI Report Assistant — Launcher
"""
from __future__ import annotations
import sys

# Hide the console window as early as possible on Windows.
# Must happen before argparse or any other output to prevent flash.
if getattr(sys, "frozen", False) and sys.platform == "win32":
    try:
        import ctypes
        _hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if _hwnd:
            ctypes.windll.user32.ShowWindow(_hwnd, 0)  # SW_HIDE
    except Exception:
        pass

import argparse
import os
import subprocess
import time
import webbrowser
from pathlib import Path

# Allow imports from the project root whether frozen or not
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    APP_NAME,
    get_api_key,
    get_app_data_dir,
    get_adomd_dll_path,
    get_install_dir,
    is_configured,
    save_config,
)


STREAMLIT_PORT = 8501


def write_powerbi_context(server: str, database: str) -> Path:
    context_file = get_app_data_dir() / "powerbi_context.txt"
    context_file.write_text(
        f"Power BI Desktop Context\n\nServer:\n{server}\n\nDatabase:\n{database}\n",
        encoding="utf-8",
    )
    return context_file


def extract_metadata(server: str, database: str) -> None:
    """Run extract_powerbi_metadata.py to pull tables/columns/measures."""
    install_dir = get_install_dir()
    data_dir = get_app_data_dir()

    # Write context file to app data dir where extractor will find it
    context_file = data_dir / "powerbi_context.txt"
    context_file.write_text(
        f"Power BI Desktop Context\n\nServer:\n{server}\n\nDatabase:\n{database}\n",
        encoding="utf-8",
    )

    # Look for extractor in _internal (frozen) or install dir (dev)
    extractor = install_dir / "_internal" / "extract_powerbi_metadata.py"
    if not extractor.exists():
        extractor = install_dir / "extract_powerbi_metadata.py"
    if not extractor.exists():
        print(f"[launcher] Extractor not found — skipping metadata extraction.")
        return

    dll = get_adomd_dll_path()
    env = os.environ.copy()
    if dll:
        env["ADOMD_DLL_PATH"] = str(dll)
    # Tell extractor where to find/write its files
    env["BI_ASSISTANT_DATA_DIR"] = str(data_dir)

    # Hide console window on Windows
    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0

    try:
        subprocess.run(
            [sys.executable, str(extractor)],
            cwd=str(data_dir),
            env=env,
            check=True,
            timeout=30,
            startupinfo=startupinfo,
        )
        print("[launcher] Metadata extraction complete.")
    except subprocess.TimeoutExpired:
        print("[launcher] Metadata extraction timed out — proceeding without model context.")
    except Exception as e:
        print(f"[launcher] Metadata extraction failed: {e}")


def get_python_exe() -> Path:
    """Return the correct Python executable to use for subprocesses.
    When frozen by PyInstaller, sys.executable is the launcher exe itself —
    we need the actual Python interpreter bundled inside _internal."""
    if getattr(sys, "frozen", False):
        install_dir = get_install_dir()
        # PyInstaller bundles Python as python.exe inside _internal/
        candidates = [
            install_dir / "_internal" / "python.exe",
            Path(sys.executable).parent / "_internal" / "python.exe",
            # Some PyInstaller versions put it at the root
            install_dir / "python.exe",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        # Last resort — try to find python in PATH
        import shutil
        found = shutil.which("python")
        if found:
            return Path(found)
    return Path(sys.executable)


def start_streamlit(install_dir: Path) -> subprocess.Popen:
    """Start the Streamlit server and return the process handle."""
    # When frozen, app.py lives inside _internal/
    app_py = install_dir / "_internal" / "app.py"
    if not app_py.exists():
        app_py = install_dir / "app.py"
    if not app_py.exists():
        raise FileNotFoundError(f"app.py not found in {install_dir}")

    python_exe = get_python_exe()
    print(f"[launcher] Using Python: {python_exe}")
    print(f"[launcher] Running app: {app_py}")

    env = os.environ.copy()
    api_key = get_api_key()
    if api_key:
        env["OPENAI_API_KEY"] = api_key

    dll = get_adomd_dll_path()
    if dll:
        env["ADOMD_DLL_PATH"] = str(dll)

    data_dir = get_app_data_dir()
    env["BI_ASSISTANT_DATA_DIR"] = str(data_dir)

    # Suppress Streamlit's own browser open and dev mode
    env["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
    env["STREAMLIT_SERVER_RUN_ON_SAVE"] = "false"
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    env["STREAMLIT_SERVER_HEADLESS"] = "true"

    # On Windows, hide the console window for the Streamlit subprocess
    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE

    proc = subprocess.Popen(
        [
            str(python_exe), "-m", "streamlit", "run",
            str(app_py),
            "--server.port", str(STREAMLIT_PORT),
            "--server.headless", "true",
            "--server.runOnSave", "false",
            "--global.developmentMode", "false",
            "--browser.gatherUsageStats", "false",
            "--server.enableCORS", "false",
            "--server.enableXsrfProtection", "false",
        ],
        cwd=str(data_dir),
        env=env,
        startupinfo=startupinfo,
    )
    return proc


def wait_for_streamlit(timeout: int = 20) -> bool:
    """Poll until Streamlit is accepting connections, then return True."""
    import socket
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("localhost", STREAMLIT_PORT), timeout=1):
                return True
        except OSError:
            time.sleep(0.4)
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description=f"{APP_NAME} Launcher")
    parser.add_argument("--server",   default="", help="Power BI AS server address")
    parser.add_argument("--database", default="", help="Power BI database name")
    parser.add_argument("--setup",    action="store_true", help="Force re-run of setup wizard")
    args = parser.parse_args()

    install_dir = get_install_dir()

    # ── First run / forced setup ───────────────────────────────────────────────
    if not is_configured() or args.setup:
        try:
            from setup_wizard import run_wizard
            run_wizard()
        except ImportError:
            print(f"[{APP_NAME}] First-time setup required.")
            key = input("Enter your OpenAI API key: ").strip()
            if key:
                save_config({"openai_api_key": key})
            else:
                print("No API key provided — exiting.")
                sys.exit(1)

        # After setup wizard closes, exit cleanly without triggering
        # Python cleanup handlers which can cause a console window flash.
        # Small delay lets tkinter finish destroying its window first.
        time.sleep(0.3)
        os._exit(0)

    if not is_configured():
        print("Setup was not completed. Exiting.")
        sys.exit(1)

    # ── Extract model if launched from Power BI ────────────────────────────────
    if args.server and args.database:
        print(f"[launcher] Extracting model: {args.database} @ {args.server}")
        extract_metadata(args.server, args.database)
    else:
        print("[launcher] No server/database args — skipping extraction.")

    # ── Start Streamlit ────────────────────────────────────────────────────────
    print("[launcher] Starting Streamlit…")
    try:
        proc = start_streamlit(install_dir)
    except FileNotFoundError as e:
        print(f"[launcher] ERROR: {e}")
        sys.exit(1)

    # Wait for the server to be ready, then open the browser
    url = f"http://localhost:{STREAMLIT_PORT}"
    if wait_for_streamlit(timeout=25):
        print(f"[launcher] App ready at {url}")
        webbrowser.open(url)
    else:
        print(f"[launcher] Timed out waiting for Streamlit — opening anyway.")
        webbrowser.open(url)

    # Keep the launcher alive while Streamlit runs
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()


if __name__ == "__main__":
    main()
