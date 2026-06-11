"""
BI Report Assistant — First Run Setup Wizard

A self-contained tkinter window that:
  1. Collects the OpenAI API key
  2. Locates or validates the ADOMD.NET DLL
  3. Registers the External Tool with Power BI Desktop
  4. Writes config.json to the app data directory

Can be run standalone or called from launcher.py on first launch.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
from pathlib import Path
from tkinter import ttk

# Allow running standalone or as part of the package
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (
    APP_NAME,
    APP_VERSION,
    ADOMD_DLL_SEARCH_PATHS,
    CONFIG_FILE,
    POWERBI_EXTERNAL_TOOLS_DIR,
    get_install_dir,
    save_config,
)


# ── Colours matching the app's dark design system ─────────────────────────────
BG_BASE    = "#080C14"
BG_SURFACE = "#0E1420"
BG_RAISED  = "#141C2E"
BORDER     = "#1E2A40"
ACCENT     = "#4F8EF7"
TEXT_PRI   = "#F0F4FF"
TEXT_SEC   = "#7B8BAA"
TEXT_MUT   = "#4A566E"
GREEN      = "#34D399"
RED        = "#F87171"
AMBER      = "#FBBF24"


def find_pbitool_json() -> Path | None:
    """Find the .pbitool.json in the install directory."""
    candidates = [
        get_install_dir() / "BI Report Assistant.pbitool.json",
        Path(__file__).resolve().parent / "BI Report Assistant.pbitool.json",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def register_external_tool(install_dir: Path, log: callable) -> bool:
    """
    Write the .pbitool.json to Power BI's External Tools folder.
    Reads the pre-baked pbitool.json from the bundle (icon embedded at build time).
    Only updates path/arguments to point to the installed launcher.
    """
    # Find the bundled pbitool.json with icon already baked in
    # First check the External Tools folder where Inno Setup already copied it
    system_tools_dir = POWERBI_EXTERNAL_TOOLS_DIR
    user_tools_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Power BI Desktop" / "External Tools"
    
    bundled_json = None
    for candidate in [
        # Check External Tools folder first — Inno Setup copies it here with icon already baked in
        system_tools_dir / "BI Report Assistant.pbitool.json",
        user_tools_dir / "BI Report Assistant.pbitool.json",
        # Fall back to _internal bundle
        install_dir / "_internal" / "BI Report Assistant_bundled.pbitool.json",
        install_dir / "_internal" / "BI Report Assistant.pbitool.json",
        install_dir / "BI Report Assistant_bundled.pbitool.json",
        Path(sys.executable).parent / "_internal" / "BI Report Assistant_bundled.pbitool.json",
    ]:
        if candidate.exists():
            bundled_json = candidate
            log(f"Found bundled pbitool.json: {candidate.parent.name}\\{candidate.name}", TEXT_SEC)
            break

    # Load bundled data or start fresh
    data = {}
    if bundled_json:
        try:
            data = json.loads(bundled_json.read_text(encoding="utf-8"))
            icon_len = len(data.get("iconData", ""))
            if icon_len > 100 and "image/png;base64," in data.get("iconData", ""):
                log(f"✓ Icon data present ({icon_len} chars)", GREEN)
            else:
                log("Icon data missing or wrong format in bundle", AMBER)
        except Exception as e:
            log(f"Could not read bundled pbitool.json: {e}", AMBER)
    else:
        log("Bundled pbitool.json not found — building from scratch", AMBER)

    # Find the launcher exe — walk up if not at install_dir
    launcher_exe = install_dir / "bi_report_assistant.exe"
    if not launcher_exe.exists():
        for candidate_dir in [
            Path(sys.executable).parent,
            Path(sys.executable).parent.parent,
        ]:
            if (candidate_dir / "bi_report_assistant.exe").exists():
                install_dir = candidate_dir
                launcher_exe = install_dir / "bi_report_assistant.exe"
                break

    if launcher_exe.exists():
        tool_path = str(launcher_exe)
        tool_args = '--server "%server%" --database "%database%"'
    else:
        launcher_py = Path(sys.executable).parent / "_internal" / "launcher.py"
        tool_path   = str(sys.executable)
        tool_args   = f'"{launcher_py}" --server "%server%" --database "%database%"'
        log(f"Fallback to Python launcher", AMBER)

    log(f"Tool path: {tool_path}", TEXT_SEC)

    data.update({
        "version": "1.0.0",
        "name": "BI Report Assistant",
        "description": "AI-powered Power BI workflow assistant.",
        "path": tool_path,
        "arguments": tool_args,
    })
    if "iconData" not in data:
        data["iconData"] = ""

    json_content = json.dumps(data, indent=2)

    # Try system-level first (most reliable for Power BI), then user-level
    user_tools_dir   = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Power BI Desktop" / "External Tools"
    system_tools_dir = POWERBI_EXTERNAL_TOOLS_DIR

    for tools_dir, label in [
        (system_tools_dir, "system-level"),
        (user_tools_dir,   "user-level"),
    ]:
        try:
            tools_dir.mkdir(parents=True, exist_ok=True)
            dest = tools_dir / "BI Report Assistant.pbitool.json"
            dest.write_text(json_content, encoding="utf-8")
            log(f"✓ Registered ({label}):\n  {dest}", GREEN)
            return True
        except PermissionError as e:
            log(f"No permission for {label} — {e}", AMBER)
        except Exception as e:
            log(f"ERROR: {label} — {e}", RED)

    log("ERROR: Could not register External Tool.", RED)
    return False


class SetupWizard:
    def __init__(self, root: tk.Tk, on_complete: callable = None):
        self.root = root
        self.on_complete = on_complete
        self.root.title(f"{APP_NAME} — Setup")
        self.root.configure(bg=BG_BASE)
        self.root.resizable(False, False)

        # Centre on screen — tall enough to show all sections + buttons
        w, h = 580, 700
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        # Don't position off-screen on small displays
        x = (sw - w) // 2
        y = max(0, min((sh - h) // 2, sh - h - 40))
        root.geometry(f"{w}x{h}+{x}+{y}")

        self._build_ui()
        self._auto_detect_adomd()

    def _build_ui(self) -> None:
        pad = dict(padx=24, pady=0)

        # Header
        header = tk.Frame(self.root, bg=BG_SURFACE, height=72)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header,
            text="BI Report Assistant",
            font=("Segoe UI", 15, "bold"),
            fg=TEXT_PRI, bg=BG_SURFACE,
        ).place(x=24, y=14)
        tk.Label(
            header,
            text=f"First-time setup  ·  v{APP_VERSION}",
            font=("Segoe UI", 10),
            fg=TEXT_SEC, bg=BG_SURFACE,
        ).place(x=24, y=42)

        # Separator
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")

        body = tk.Frame(self.root, bg=BG_BASE)
        body.pack(fill="both", expand=True, padx=24, pady=20)

        # ── Step 1: API Key ───────────────────────────────────────────────────
        self._section(body, "1.  OpenAI API Key")

        tk.Label(
            body,
            text="Your API key is stored locally on this machine and never shared.",
            font=("Segoe UI", 9),
            fg=TEXT_SEC, bg=BG_BASE,
            wraplength=512, justify="left",
        ).pack(anchor="w", pady=(2, 6))

        key_frame = tk.Frame(body, bg=BG_SURFACE, highlightbackground=BORDER, highlightthickness=1)
        key_frame.pack(fill="x", pady=(0, 4))

        self.api_key_var = tk.StringVar()
        self.api_key_entry = tk.Entry(
            key_frame,
            textvariable=self.api_key_var,
            font=("Segoe UI", 10),
            fg=TEXT_PRI, bg=BG_SURFACE,
            insertbackground=TEXT_PRI,
            relief="flat",
            show="•",
            bd=8,
        )
        self.api_key_entry.pack(fill="x")

        self.show_key_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            body,
            text="Show key",
            variable=self.show_key_var,
            command=self._toggle_key_visibility,
            font=("Segoe UI", 9),
            fg=TEXT_SEC, bg=BG_BASE,
            activeforeground=TEXT_PRI,
            activebackground=BG_BASE,
            selectcolor=BG_RAISED,
            relief="flat", bd=0,
        ).pack(anchor="w", pady=(0, 16))

        tk.Label(
            body,
            text="Get a key at platform.openai.com/api-keys",
            font=("Segoe UI", 9, "underline"),
            fg=ACCENT, bg=BG_BASE,
            cursor="hand2",
        ).pack(anchor="w", pady=(0, 20))

        # ── Step 2: ADOMD.NET ────────────────────────────────────────────────
        self._section(body, "2.  ADOMD.NET Library")

        tk.Label(
            body,
            text="Required to connect to your Power BI model. Usually installed with SSMS.",
            font=("Segoe UI", 9),
            fg=TEXT_SEC, bg=BG_BASE,
            wraplength=512, justify="left",
        ).pack(anchor="w", pady=(2, 6))

        dll_row = tk.Frame(body, bg=BG_BASE)
        dll_row.pack(fill="x", pady=(0, 4))

        dll_inner = tk.Frame(dll_row, bg=BG_SURFACE, highlightbackground=BORDER, highlightthickness=1)
        dll_inner.pack(side="left", fill="x", expand=True)

        self.dll_path_var = tk.StringVar(value="Searching…")
        tk.Entry(
            dll_inner,
            textvariable=self.dll_path_var,
            font=("Segoe UI", 9),
            fg=TEXT_SEC, bg=BG_SURFACE,
            insertbackground=TEXT_PRI,
            relief="flat", bd=8,
        ).pack(fill="x")

        tk.Button(
            dll_row,
            text="Browse",
            font=("Segoe UI", 9),
            fg=TEXT_SEC, bg=BG_RAISED,
            activeforeground=TEXT_PRI,
            activebackground=BG_HOVER if hasattr(self, 'BG_HOVER') else BG_RAISED,
            relief="flat", bd=0,
            padx=12, pady=6,
            cursor="hand2",
            command=self._browse_dll,
        ).pack(side="left", padx=(6, 0))

        self.dll_status = tk.Label(
            body,
            text="",
            font=("Segoe UI", 9),
            fg=TEXT_SEC, bg=BG_BASE,
        )
        self.dll_status.pack(anchor="w", pady=(0, 20))

        # ── Step 3: External Tool registration ───────────────────────────────
        self._section(body, "3.  Register with Power BI Desktop")

        tk.Label(
            body,
            text="Adds BI Report Assistant to the External Tools ribbon. Close Power BI Desktop first.",
            font=("Segoe UI", 9),
            fg=TEXT_SEC, bg=BG_BASE,
            wraplength=512, justify="left",
        ).pack(anchor="w", pady=(2, 16))

        # ── Log output ───────────────────────────────────────────────────────
        log_frame = tk.Frame(body, bg=BG_SURFACE, highlightbackground=BORDER, highlightthickness=1)
        log_frame.pack(fill="x", pady=(0, 20))

        self.log_text = tk.Text(
            log_frame,
            font=("Consolas", 8),
            fg=TEXT_SEC, bg=BG_SURFACE,
            relief="flat", bd=8,
            height=5,
            state="disabled",
            wrap="word",
        )
        self.log_text.pack(fill="x")
        self.log_text.tag_configure("green", foreground=GREEN)
        self.log_text.tag_configure("red",   foreground=RED)
        self.log_text.tag_configure("amber", foreground=AMBER)

        # ── Bottom buttons ────────────────────────────────────────────────────
        btn_frame = tk.Frame(self.root, bg=BG_BASE)
        btn_frame.pack(fill="x", padx=24, pady=(0, 24))

        self.finish_btn = tk.Button(
            btn_frame,
            text="Set Up and Launch →",
            font=("Segoe UI", 10, "bold"),
            fg="#ffffff", bg=ACCENT,
            activeforeground="#ffffff",
            activebackground="#6B9FFF",
            relief="flat", bd=0,
            padx=20, pady=10,
            cursor="hand2",
            command=self._run_setup,
        )
        self.finish_btn.pack(side="right")

        tk.Button(
            btn_frame,
            text="Cancel",
            font=("Segoe UI", 10),
            fg=TEXT_SEC, bg=BG_RAISED,
            activeforeground=TEXT_PRI,
            activebackground=BG_RAISED,
            relief="flat", bd=0,
            padx=20, pady=10,
            cursor="hand2",
            command=self.root.destroy,
        ).pack(side="right", padx=(0, 8))

    def _section(self, parent, title: str) -> None:
        tk.Label(
            parent,
            text=title,
            font=("Segoe UI", 10, "bold"),
            fg=TEXT_PRI, bg=BG_BASE,
        ).pack(anchor="w", pady=(0, 4))

    def _toggle_key_visibility(self) -> None:
        self.api_key_entry.config(show="" if self.show_key_var.get() else "•")

    def _auto_detect_adomd(self) -> None:
        """Search known paths for the DLL in a background thread."""
        def search():
            for candidate in ADOMD_DLL_SEARCH_PATHS:
                if candidate.exists():
                    self.dll_path_var.set(str(candidate))
                    self.dll_status.config(
                        text=f"✓ Found automatically",
                        fg=GREEN,
                    )
                    return
            self.dll_path_var.set("")
            self.dll_status.config(
                text="Not found — browse to Microsoft.AnalysisServices.AdomdClient.dll, "
                     "or install SSMS from Microsoft.",
                fg=AMBER,
            )
        threading.Thread(target=search, daemon=True).start()

    def _browse_dll(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Microsoft.AnalysisServices.AdomdClient.dll",
            filetypes=[("DLL files", "*.dll"), ("All files", "*.*")],
            initialdir=r"C:\Program Files",
        )
        if path:
            self.dll_path_var.set(path)
            self.dll_status.config(text="✓ DLL path set manually", fg=GREEN)

    def _log(self, msg: str, color: str = TEXT_SEC) -> None:
        tag = {GREEN: "green", RED: "red", AMBER: "amber"}.get(color, "")
        self.log_text.config(state="normal")
        self.log_text.insert("end", msg + "\n", tag)
        self.log_text.see("end")
        self.log_text.config(state="disabled")
        self.root.update_idletasks()

    def _run_setup(self) -> None:
        self.finish_btn.config(state="disabled", text="Setting up…")
        self._log("Starting setup…")

        # Validate API key
        api_key = self.api_key_var.get().strip()
        if not api_key or not api_key.startswith("sk-"):
            messagebox.showerror(
                "Invalid API Key",
                "Please enter a valid OpenAI API key.\nIt should start with 'sk-'.",
            )
            self.finish_btn.config(state="normal", text="Set Up and Launch →")
            return

        # Validate DLL
        dll_path = self.dll_path_var.get().strip()
        if not dll_path or not Path(dll_path).exists():
            result = messagebox.askyesno(
                "ADOMD.NET Not Found",
                "The ADOMD.NET DLL was not found.\n\n"
                "You can still use the app with manually pasted schema and DAX,\n"
                "but the live model connection will not work.\n\n"
                "Continue without it?",
            )
            if not result:
                self.finish_btn.config(state="normal", text="Set Up and Launch →")
                return
            dll_path = ""

        # Save config
        self._log("Saving configuration…")
        config_data = {"openai_api_key": api_key}
        if dll_path:
            config_data["adomd_dll_path"] = dll_path
        save_config(config_data)
        self._log(f"✓ Config saved to {CONFIG_FILE}", GREEN)

        # Resolve install dir — try registry first, then exe location
        install_dir = get_install_dir()
        self._log(f"Install dir: {install_dir}", TEXT_SEC)

        # Verify the exe actually exists there — if not, walk up from sys.executable
        exe_path = install_dir / "bi_report_assistant.exe"
        if not exe_path.exists():
            # Try the directory containing this running process
            for candidate in [
                Path(sys.executable).parent,
                Path(sys.executable).parent.parent,
            ]:
                if (candidate / "bi_report_assistant.exe").exists():
                    install_dir = candidate
                    self._log(f"Corrected install dir: {install_dir}", AMBER)
                    break

        self._log(f"Exe exists: {(install_dir / 'bi_report_assistant.exe').exists()}", TEXT_SEC)

        # Register External Tool
        self._log("Registering Power BI External Tool…")
        success = register_external_tool(install_dir, self._log)

        if success:
            self._log("✓ Setup complete!", GREEN)
            self._log("Restart Power BI Desktop to see the External Tools button.", AMBER)
            self._log("Then click BI Report Assistant in the External Tools ribbon to launch the app.", AMBER)
        else:
            self._log("Setup completed with warnings — see above.", AMBER)

        # Done — just close the wizard, do NOT auto-launch the app
        # The app should only launch when triggered from Power BI External Tools
        self.finish_btn.config(text="✓ Done — Close")
        self.finish_btn.config(state="normal", command=self.root.destroy)

    def _complete(self) -> None:
        self.root.destroy()
        if self.on_complete:
            self.on_complete()


def run_wizard(on_complete: callable = None) -> None:
    """Launch the setup wizard. Calls on_complete() when the user finishes."""
    root = tk.Tk()
    app = SetupWizard(root, on_complete=on_complete)
    root.mainloop()


if __name__ == "__main__":
    run_wizard()
