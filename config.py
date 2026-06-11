"""
Shared configuration for BI Report Assistant.

Reads from config.json in the app data directory.
Falls back to environment variables for development use.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


# ── App identity ──────────────────────────────────────────────────────────────
APP_NAME    = "BI Report Assistant"
APP_VERSION = "1.0.0"
APP_AUTHOR  = "BI Report Assistant"


# ── Paths ─────────────────────────────────────────────────────────────────────
def get_app_data_dir() -> Path:
    """Return the user-writable config directory.
    %APPDATA%\\BI Report Assistant on Windows, ~/.bi-report-assistant elsewhere."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path.home()
    d = base / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_install_dir() -> Path:
    """Return the directory where the app is installed (or the project root in dev)."""
    if getattr(sys, "frozen", False):
        # When frozen by PyInstaller, sys.executable points to the temp extraction
        # directory (_MEIxxxxxx), NOT the actual install location.
        # Read the real install path from the Windows registry instead.
        # Inno Setup writes InstallLocation under the AppId GUID key.
        registry_keys = [
            # HKLM — system-wide install (most common with admin)
            (winreg_root("HKLM"), r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{A3F7C2B1-9E4D-4F8A-B2C5-1D6E3A7F0B9C}_is1"),
            (winreg_root("HKLM"), r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\{A3F7C2B1-9E4D-4F8A-B2C5-1D6E3A7F0B9C}_is1"),
            # HKCU — per-user install
            (winreg_root("HKCU"), r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{A3F7C2B1-9E4D-4F8A-B2C5-1D6E3A7F0B9C}_is1"),
        ]

        try:
            import winreg
            for hive, key_path in registry_keys:
                try:
                    key = winreg.OpenKey(hive, key_path)
                    install_location, _ = winreg.QueryValueEx(key, "InstallLocation")
                    winreg.CloseKey(key)
                    p = Path(install_location)
                    if p.exists():
                        return p
                except Exception:
                    continue
        except ImportError:
            pass  # Not on Windows

        # Last resort: use the exe's parent (correct when not temp-extracted)
        return Path(sys.executable).parent

    # Running in development
    return Path(__file__).resolve().parent


def winreg_root(name: str):
    """Return a winreg HKEY constant by name string."""
    try:
        import winreg
        return {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}[name]
    except ImportError:
        return None


CONFIG_FILE = get_app_data_dir() / "config.json"

# Default ADOMD.NET DLL path — checked in order
ADOMD_DLL_SEARCH_PATHS = [
    # Bundled DLL inside the install directory (preferred when packaged)
    get_install_dir() / "adomd" / "Microsoft.AnalysisServices.AdomdClient.dll",
    # Standard SSMS / SQL Server install location
    Path(r"C:\Program Files\Microsoft.NET\ADOMD.NET\160\Microsoft.AnalysisServices.AdomdClient.dll"),
    Path(r"C:\Program Files\Microsoft.NET\ADOMD.NET\150\Microsoft.AnalysisServices.AdomdClient.dll"),
    Path(r"C:\Program Files\Microsoft.NET\ADOMD.NET\140\Microsoft.AnalysisServices.AdomdClient.dll"),
    # Visual Studio / SSDT location
    Path(r"C:\Program Files (x86)\Microsoft SQL Server\160\SDK\Assemblies\Microsoft.AnalysisServices.AdomdClient.dll"),
]

POWERBI_EXTERNAL_TOOLS_DIR = Path(
    r"C:\Program Files (x86)\Common Files\Microsoft Shared\Power BI Desktop\External Tools"
)


# ── Config read / write ───────────────────────────────────────────────────────
def load_config() -> dict:
    """Load config from config.json. Returns empty dict if file doesn't exist."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_config(data: dict) -> None:
    """Save config to config.json, merging with any existing values."""
    existing = load_config()
    existing.update(data)
    CONFIG_FILE.write_text(json.dumps(existing, indent=2), encoding="utf-8")


# ── Individual getters ─────────────────────────────────────────────────────────
def get_api_key() -> str:
    """Return the OpenAI API key. Config file takes priority over env var."""
    cfg = load_config()
    return cfg.get("openai_api_key") or os.environ.get("OPENAI_API_KEY", "")


def get_adomd_dll_path() -> Path | None:
    """Return the ADOMD.NET DLL path. Checks config, then env var, then known locations."""
    cfg = load_config()
    configured = cfg.get("adomd_dll_path") or os.environ.get("ADOMD_DLL_PATH", "")
    if configured:
        p = Path(configured)
        if p.exists():
            return p

    for candidate in ADOMD_DLL_SEARCH_PATHS:
        if candidate.exists():
            return candidate

    return None


def is_configured() -> bool:
    """Return True if the app has been set up (has an API key)."""
    return bool(get_api_key())
