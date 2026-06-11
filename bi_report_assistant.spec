# bi_report_assistant.spec
#
# PyInstaller build spec for BI Report Assistant.
#
# Usage:
#   pip install pyinstaller
#   pyinstaller bi_report_assistant.spec
#
# Output: dist/bi_report_assistant/bi_report_assistant.exe
#
# Notes:
#   - Streamlit requires special handling because it relies on file-system
#     discovery of its own package data (templates, static files, etc.)
#   - We use collect_all("streamlit") to bundle everything Streamlit needs.
#   - The ADOMD DLL is collected separately and placed in an "adomd/" subfolder.
#   - Set ADOMD_DLL_SOURCE below to the DLL path on your build machine.

import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files

# ── Configuration ─────────────────────────────────────────────────────────────
# Path to the ADOMD.NET DLL on the BUILD machine.
# This DLL is bundled inside the package so end users don't need to install it.
ADOMD_DLL_SOURCE = os.environ.get(
    "ADOMD_DLL_PATH",
    r"C:\Program Files\Microsoft.NET\ADOMD.NET\160\Microsoft.AnalysisServices.AdomdClient.dll",
)

PROJECT_ROOT = Path(SPECPATH)  # SPECPATH is set by PyInstaller to the spec file's directory

# ── Collect Streamlit package data ────────────────────────────────────────────
st_datas, st_binaries, st_hiddenimports = collect_all("streamlit")

# ── Collect other package data ────────────────────────────────────────────────
pil_datas, _, pil_hidden = collect_all("PIL")
openai_datas, _, openai_hidden = collect_all("openai")
dotenv_datas, _, _ = collect_all("dotenv")
altair_datas, _, altair_hidden = collect_all("altair")
pydeck_datas, _, pydeck_hidden = collect_all("pydeck")

# ── App source files to bundle ────────────────────────────────────────────────
# ── Embed icon into pbitool.json at build time ───────────────────────────────
# This bakes the correct base64 icon directly into the bundled pbitool.json
# so the setup wizard doesn't need to find icon.png at runtime.
import base64 as _base64
import json as _json
import tempfile as _tempfile

_pbitool_src = PROJECT_ROOT / "BI Report Assistant.pbitool.json"
_icon_src = PROJECT_ROOT / "icon.png"
# Write to a temp file with the EXACT target filename so it lands correctly in _internal/
_pbitool_with_icon = PROJECT_ROOT / "BI Report Assistant_bundled.pbitool.json"

if _pbitool_src.exists() and _icon_src.exists():
    try:
        _data = _json.loads(_pbitool_src.read_text(encoding="utf-8"))
        _icon_b64 = _base64.b64encode(_icon_src.read_bytes()).decode("utf-8")
        _data["iconData"] = "image/png;base64," + _icon_b64
        _pbitool_with_icon.write_text(_json.dumps(_data, indent=2), encoding="utf-8")
        print(f"[spec] Embedded icon into pbitool.json ({len(_icon_b64)} chars)")
        _pbitool_bundled = _pbitool_with_icon
    except Exception as e:
        print(f"[spec] WARNING: Could not embed icon: {e}")
        _pbitool_bundled = _pbitool_src
else:
    print(f"[spec] WARNING: icon.png or pbitool.json not found — icon will be empty")
    _pbitool_bundled = _pbitool_src

app_datas = [
    # Python source files
    (str(PROJECT_ROOT / "app.py"),                       "."),
    (str(PROJECT_ROOT / "config.py"),                    "."),
    (str(PROJECT_ROOT / "launcher.py"),                  "."),
    (str(PROJECT_ROOT / "setup_wizard.py"),              "."),
    (str(PROJECT_ROOT / "extract_powerbi_metadata.py"),  "."),

    # Bundled pbitool.json with icon already baked in
    # Destination must be "." (root of _internal) not a filename — PyInstaller
    # tuple is (source, dest_dir) not (source, dest_filename)
    (str(_pbitool_bundled), "."),
]

# Bundle images folder if it exists
images_dir = PROJECT_ROOT / "images"
if images_dir.exists():
    app_datas.append((str(images_dir), "images"))

# ── Bundle ADOMD DLL ──────────────────────────────────────────────────────────
adomd_datas = []
if Path(ADOMD_DLL_SOURCE).exists():
    adomd_datas.append((ADOMD_DLL_SOURCE, "adomd"))
    print(f"[spec] Bundling ADOMD DLL from: {ADOMD_DLL_SOURCE}")
else:
    print(f"[spec] WARNING: ADOMD DLL not found at {ADOMD_DLL_SOURCE}")
    print("[spec] The bundled app will require the user to have ADOMD installed separately.")

# ── Combined collections ──────────────────────────────────────────────────────
all_datas = (
    app_datas
    + st_datas
    + pil_datas
    + openai_datas
    + dotenv_datas
    + altair_datas
    + pydeck_datas
    + adomd_datas
)

all_binaries = st_binaries

all_hidden = (
    st_hiddenimports
    + pil_hidden
    + openai_hidden
    + altair_hidden
    + pydeck_hidden
    + [
        "streamlit",
        "streamlit.web.cli",
        "streamlit.runtime.scriptrunner.magic_funcs",
        "PIL._tkinter_finder",
        "tkinter",
        "tkinter.ttk",
        "tkinter.filedialog",
        "tkinter.messagebox",
        "winreg",
        "openai",
        "dotenv",
        "pythonnet",
        "clr",
        "altair",
        "pydeck",
        "pyarrow",
        "pandas",
        "numpy",
        "click",
        "toml",
        "tomli",
        "packaging",
        "importlib_metadata",
        "zipp",
        "attr",
        "attrs",
        "json5",
        "validators",
        "gitpython",
        "watchdog",
        "pyzmq",
        "zmq",
    ]
)

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    [str(PROJECT_ROOT / "launcher.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=all_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "scipy",
        "sklearn",
        "tensorflow",
        "torch",
        "cv2",
        "IPython",
        "notebook",
        "pytest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="bi_report_assistant",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,           # Must be True so Power BI can spawn it — window hidden via ctypes
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(PROJECT_ROOT / "icon.ico") if (PROJECT_ROOT / "icon.ico").exists() else None,
    version_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="bi_report_assistant",
)
