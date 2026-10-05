"""Shared helpers for the studio tools (imported by the other scripts).

Everything here is standard library and works the same on Mac and Windows.
"""
from __future__ import annotations

import glob
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

IS_WINDOWS = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"


KEYS_FILE = "api-keys.txt"  # the member pastes service keys here (never in the chat)


def workspace_root() -> Path:
    """The studio folder: set by the launcher, else found from this file (tools/studio/…)."""
    env = os.environ.get("STUDIO_WORKSPACE")
    if env:
        return Path(env)
    here = Path(__file__).resolve().parent
    return here.parent.parent if here.parent.name == "tools" else Path.home() / "VideoStudio"


def api_key(name: str) -> str:
    """The ONE place that reads service keys. Returns '' when the key isn't there."""
    f = workspace_root() / KEYS_FILE
    if not f.exists():
        return ""
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            if k.strip() == name:
                return v.strip().strip('"').strip("'")
    return ""


def utf8_console() -> None:
    """Windows consoles default to a legacy code page; Hebrew output needs UTF-8."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass


def _extra_bin_dirs() -> list[str]:
    home = Path.home()
    dirs = [str(home / "VideoStudio" / ".tools" / "bin"), r"C:\VideoStudio\.tools\bin"]
    if IS_MAC:
        dirs += ["/opt/homebrew/bin", "/usr/local/bin"]
    if IS_WINDOWS:
        local = os.environ.get("LOCALAPPDATA", "")
        dirs += [os.path.join(local, "Microsoft", "WinGet", "Links")]
        dirs += glob.glob(os.path.join(local, "Microsoft", "WinGet", "Packages", "Gyan.FFmpeg*", "*", "bin"))
        dirs += [r"C:\ffmpeg\bin", r"C:\Program Files\ffmpeg\bin"]
    return [d for d in dirs if d and os.path.isdir(d)]


def find_tool(name: str) -> str:
    """Locate ffmpeg/ffprobe even when PATH was not refreshed after an install."""
    env_override = os.environ.get(f"STUDIO_{name.upper()}")
    if env_override and os.path.exists(env_override):
        return env_override
    found = shutil.which(name)
    if found:
        return found
    exe = name + (".exe" if IS_WINDOWS else "")
    for d in _extra_bin_dirs():
        candidate = os.path.join(d, exe)
        if os.path.exists(candidate):
            return candidate
    sys.exit(f"[studio] '{name}' not found. Run the setup stage 'foundation' again "
             f"(ffmpeg is installed there), then open a new terminal.")


def ffmpeg() -> str:
    return find_tool("ffmpeg")


def ffprobe() -> str:
    return find_tool("ffprobe")


def run(cmd: list[str], check: bool = True, quiet: bool = False) -> subprocess.CompletedProcess:
    """Run a command with UTF-8 decoding (ffmpeg writes Hebrew filenames in its logs)."""
    if not quiet:
        print("  $ " + " ".join(_short(c) for c in cmd), file=sys.stderr)
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and proc.returncode != 0:
        tail = "\n".join((proc.stderr or "").strip().splitlines()[-15:])
        sys.exit(f"[studio] command failed ({proc.returncode}):\n{tail}")
    return proc


def _short(arg: str) -> str:
    return arg if len(arg) < 120 else arg[:117] + "..."


def probe(path: str | Path) -> dict:
    out = run([ffprobe(), "-v", "error", "-print_format", "json", "-show_format",
               "-show_streams", str(path)], quiet=True).stdout
    return json.loads(out)


def video_stream(info: dict) -> dict | None:
    return next((s for s in info.get("streams", []) if s.get("codec_type") == "video"
                 and not s.get("disposition", {}).get("attached_pic")), None)


def audio_stream(info: dict) -> dict | None:
    return next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)


def fraction(value: str | None) -> float:
    if not value or value in ("0/0", "N/A"):
        return 0.0
    if "/" in value:
        num, den = value.split("/", 1)
        return float(num) / float(den) if float(den) else 0.0
    return float(value)


def duration_of(info: dict) -> float:
    try:
        return float(info["format"]["duration"])
    except (KeyError, ValueError, TypeError):
        vs = video_stream(info) or audio_stream(info) or {}
        return float(vs.get("duration", 0) or 0)


def read_json(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
