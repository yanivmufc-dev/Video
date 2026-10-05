# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Hardware + tools check for the video studio. Standard library only.

Run (Mac and Windows alike):
    uv run scripts/check_system.py                 # human summary (Hebrew) + JSON
    uv run scripts/check_system.py --json          # JSON only
    uv run scripts/check_system.py --save studio/system.json

It answers three questions:
  1. Which transcription path fits this computer (local GPU / local CPU / cloud)?
  2. Which tools are already installed, and which are missing?
  3. Are there environment traps (Hebrew username, OneDrive folder, low disk)?
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], timeout: int = 15) -> str:
    """Run a command, return stdout ('' on any failure). Never raises."""
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
        return (out.stdout or "").strip()
    except Exception:
        return ""


def powershell(script: str) -> str:
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        return ""
    return run([exe, "-NoProfile", "-NonInteractive", "-Command", script], timeout=30)


# ---------------------------------------------------------------- hardware

def detect_os() -> dict:
    system = platform.system()
    info = {"system": {"Darwin": "mac", "Windows": "windows"}.get(system, system.lower()),
            "release": platform.release(), "version": platform.version(),
            "arch": platform.machine()}
    if info["system"] == "mac":
        info["mac_version"] = platform.mac_ver()[0]
        # Under Rosetta, platform.machine() lies ("x86_64") — ask the kernel.
        translated = run(["sysctl", "-n", "sysctl.proc_translated"]) == "1"
        arm = run(["sysctl", "-n", "hw.optional.arm64"]) == "1"
        info["apple_silicon"] = arm or info["arch"] == "arm64"
        info["rosetta"] = translated
    if info["system"] == "windows":
        try:
            info["windows_build"] = int(platform.version().split(".")[-1])
        except ValueError:
            info["windows_build"] = None
        info["windows_11"] = (info.get("windows_build") or 0) >= 22000
    return info


def detect_cpu(os_name: str) -> dict:
    name = ""
    if os_name == "mac":
        name = run(["sysctl", "-n", "machdep.cpu.brand_string"])
    elif os_name == "windows":
        try:
            import winreg  # type: ignore
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            name = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
        except Exception:
            name = platform.processor()
    else:
        try:
            for line in Path("/proc/cpuinfo").read_text().splitlines():
                if line.startswith("model name"):
                    name = line.split(":", 1)[1].strip()
                    break
        except Exception:
            pass
    physical = 0
    if os_name == "mac":
        physical = int(run(["sysctl", "-n", "hw.physicalcpu"]) or 0)
    elif os_name == "windows":
        out = powershell("(Get-CimInstance Win32_Processor | Measure-Object -Property NumberOfCores -Sum).Sum")
        physical = int(out) if out.strip().isdigit() else 0
    else:
        try:
            physical = len({line for line in Path("/proc/cpuinfo").read_text().splitlines()
                            if line.startswith("core id")}) or 0
        except Exception:
            physical = 0
    logical = os.cpu_count() or 1
    return {"name": name or platform.processor() or "unknown",
            "logical_cores": logical, "physical_cores": physical or max(1, logical // 2)}


def detect_ram_gb(os_name: str) -> float:
    try:
        if os_name == "mac":
            return round(int(run(["sysctl", "-n", "hw.memsize"])) / 1024**3, 1)
        if os_name == "windows":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))  # type: ignore[attr-defined]
            return round(stat.ullTotalPhys / 1024**3, 1)
        pages = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
        return round(pages / 1024**3, 1)
    except Exception:
        return 0.0


def detect_gpus(os_name: str) -> dict:
    gpus: dict = {"nvidia": [], "other": []}
    smi = shutil.which("nvidia-smi")
    if not smi and os_name == "windows":
        candidate = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "nvidia-smi.exe"
        smi = str(candidate) if candidate.exists() else None
    if smi:
        out = run([smi, "--query-gpu=name,memory.total,driver_version",
                   "--format=csv,noheader,nounits"])
        for line in out.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2:
                try:
                    vram = round(float(parts[1]) / 1024, 1)
                except ValueError:
                    vram = 0.0
                gpus["nvidia"].append({"name": parts[0], "vram_gb": vram,
                                       "driver": parts[2] if len(parts) > 2 else ""})
    if os_name == "windows":
        out = powershell("Get-CimInstance Win32_VideoController | "
                         "ForEach-Object { $_.Name }")
        for name in out.splitlines():
            name = name.strip()
            if name and not any(name == g["name"] for g in gpus["nvidia"]):
                gpus["other"].append(name)
    elif os_name == "mac":
        out = run(["system_profiler", "SPDisplaysDataType"], timeout=30)
        for m in re.finditer(r"Chipset Model:\s*(.+)", out):
            gpus["other"].append(m.group(1).strip())
    return gpus


# ---------------------------------------------------------------- tools

def version_of(exe: str, args: list[str], pattern: str) -> str | None:
    path = shutil.which(exe)
    if not path:
        return None
    m = re.search(pattern, run([path, *args]))
    return m.group(1) if m else "installed"


def detect_tools(os_name: str) -> dict:
    tools = {
        "uv": version_of("uv", ["--version"], r"uv\s+([\d.]+)"),
        "ffmpeg": version_of("ffmpeg", ["-version"], r"ffmpeg version\s+(\S+)"),
        "ffprobe": version_of("ffprobe", ["-version"], r"ffprobe version\s+(\S+)"),
        "node": version_of("node", ["--version"], r"v([\d.]+)"),
        "npm": version_of("npm.cmd" if os_name == "windows" else "npm", ["--version"], r"([\d.]+)"),
        "git": version_of("git", ["--version"], r"git version\s+(\S+)"),
    }
    if os_name == "mac":
        tools["brew"] = version_of("brew", ["--version"], r"Homebrew\s+(\S+)")
        tools["xcode_clt"] = bool(run(["xcode-select", "-p"]))
    if os_name == "windows":
        tools["winget"] = version_of("winget", ["--version"], r"v?([\d.]+)")
    # ffmpeg capabilities the studio relies on
    if tools["ffmpeg"]:
        filters = run([shutil.which("ffmpeg") or "ffmpeg", "-hide_banner", "-filters"], timeout=20)
        tools["ffmpeg_filters"] = {f: bool(re.search(rf"\s{f}\s", filters))
                                   for f in ("loudnorm", "zscale", "tonemap", "libplacebo",
                                             "ass", "subtitles", "silencedetect", "ebur128")}
    node_major = int(tools["node"].split(".")[0]) if tools["node"] and tools["node"][0].isdigit() else 0
    tools["node_ok"] = node_major >= 20
    return tools


# ---------------------------------------------------------------- environment traps

def detect_env(workspace: Path | None) -> dict:
    home = Path.home()
    ws = workspace or home
    probe = ws if ws.exists() else ws.parent
    try:
        free_gb = round(shutil.disk_usage(probe).free / 1024**3, 1)
    except Exception:
        free_gb = -1
    home_str = str(home)
    return {
        "home": home_str,
        "home_non_ascii": not home_str.isascii(),
        "home_has_space": " " in home_str,
        "onedrive_active": bool(os.environ.get("OneDrive")),
        "workspace": str(ws),
        "workspace_non_ascii": not str(ws).isascii(),
        "workspace_in_onedrive": "onedrive" in str(ws).lower(),
        "disk_free_gb": free_gb,
    }


def suggest_workspace(os_info: dict, env: dict) -> str:
    """Where the studio should live. ASCII-only, outside OneDrive/iCloud sync."""
    if os_info["system"] == "windows":
        if env["home_non_ascii"] or env["home_has_space"]:
            return r"C:\VideoStudio"
        return str(Path.home() / "VideoStudio")
    return str(Path.home() / "VideoStudio")


# ---------------------------------------------------------------- decision

def transcription_plan(os_info: dict, cpu: dict, ram: float, gpus: dict, disk_free: float) -> dict:
    """Pick the transcription path (rule validated in the 2026-09 research). Tiers:
      local-cuda  : NVIDIA GPU with >= 4 GB VRAM — fastest (15–60x realtime)
      local-apple : Apple Silicon — fast CPU path (~6x realtime on 16 GB+)
      local-cpu   : other PCs with enough RAM/cores — fine for reels, slow for long videos
      cloud       : weak machine, no disk space, or Windows on ARM
    """
    cores = cpu.get("physical_cores") or cpu["logical_cores"]
    best_nv = max(gpus["nvidia"], key=lambda g: g["vram_gb"], default=None)
    win_arm = os_info["system"] == "windows" and os_info["arch"].lower() in ("arm64", "aarch64")
    need_disk = 4 if best_nv else 3
    if 0 <= disk_free < need_disk:
        return {"tier": "cloud", "speed": "n/a", "why": f"only {disk_free} GB free disk (the model needs ~{need_disk} GB)"}
    if win_arm:
        return {"tier": "cloud", "speed": "n/a", "why": "Windows on ARM has no build of the local speech engine"}
    if best_nv and best_nv["vram_gb"] >= 4:
        return {"tier": "local-cuda", "speed": "very fast",
                "why": f"NVIDIA {best_nv['name']} with {best_nv['vram_gb']} GB VRAM"}
    if os_info["system"] == "mac" and os_info.get("apple_silicon"):
        if ram >= 15:
            return {"tier": "local-apple", "speed": "fast", "why": f"Apple Silicon with {ram} GB RAM (~6x realtime)"}
        if ram >= 7.5:
            return {"tier": "local-apple", "speed": "ok",
                    "why": f"Apple Silicon with {ram} GB RAM — works (~2x realtime); close heavy apps"}
        return {"tier": "cloud", "speed": "n/a", "why": f"only {ram} GB RAM"}
    if ram >= 7.5 and cores >= 6:
        return {"tier": "local-cpu", "speed": "ok",
                "why": f"{cores} cores + {ram} GB RAM — ~1–2x realtime: fine for reels, cloud for long videos"}
    if ram >= 7.5 and cores >= 4:
        return {"tier": "local-cpu", "speed": "slow",
                "why": f"{cores} cores + {ram} GB RAM — OK for short videos (< ~15 min of footage); cloud otherwise"}
    return {"tier": "cloud", "speed": "n/a", "why": f"{ram} GB RAM / {cores} cores is too weak for the local Hebrew model"}


def blockers(os_info: dict) -> list[str]:
    """Things that stop the studio entirely until the member fixes them (Hebrew)."""
    out = []
    if os_info["system"] == "mac":
        try:
            major = int((os_info.get("mac_version") or "0").split(".")[0])
        except ValueError:
            major = 0
        if 0 < major < 15:
            out.append(f"macOS {os_info.get('mac_version')} ישן מדי: מנוע הרינדור (Remotion) דורש macOS 15 ומעלה. "
                       "עדכנו דרך הגדרות המערכת > כללי > עדכון תוכנה.")
    if os_info["system"] == "windows" and (os_info.get("windows_build") or 99999) < 17763:
        out.append("גרסת Windows 10 ישנה מדי — עדכנו את Windows (נדרש 1809 ומעלה).")
    return out


def workspace_health(ws: Path) -> dict | None:
    """Only for an existing studio: which parts are installed and working."""
    if not (ws / ".studio" / "state.json").exists():
        return None
    exe = ".exe" if platform.system() == "Windows" else ""
    node = ws / "tools" / "node" / (f"node{exe}" if exe else "bin/node")
    try:
        state = json.loads((ws / ".studio" / "state.json").read_text(encoding="utf-8"))
    except Exception:
        state = {}
    hf = ws / ".cache" / "hf" / "hub" / "models--ivrit-ai--whisper-large-v3-turbo-ct2"
    checks = {
        "launcher": (ws / "tools" / "studio" / "studio.py").exists(),
        "uv": (ws / "tools" / "uv" / f"uv{exe}").exists(),
        "ffmpeg": (ws / "tools" / "ffmpeg" / f"ffmpeg{exe}").exists(),
        "node": node.exists(),
        "remotion_installed": (ws / "remotion" / "node_modules" / "remotion").exists(),
        "headless_chrome": (ws / "remotion" / "node_modules" / ".remotion").exists(),
        "hebrew_model": hf.exists(),
        "sound_library": any((ws / "remotion" / "public" / "library" / "sfx").rglob("*.wav"))
        if (ws / "remotion" / "public" / "library" / "sfx").exists() else False,
        "agent_permissions": (ws / ".claude" / "settings.json").exists() and (ws / ".codex" / "config.toml").exists(),
    }
    steps = {k: v.get("status") for k, v in state.get("steps", {}).items()}
    return {"checks": checks, "steps": steps, "transcription": state.get("transcription", {}),
            "projects": sorted(p.name for p in (ws / "projects").iterdir() if p.is_dir())
            if (ws / "projects").exists() else []}


def missing_tools(tools: dict) -> list[str]:
    """System-wide tools (informational — the studio installs its own copies inside itself)."""
    need = []
    for t in ("uv", "ffmpeg", "ffprobe", "git"):
        if not tools.get(t):
            need.append(t)
    if not tools.get("node_ok"):
        need.append("node (20+)")
    return need


def hebrew_summary(r: dict) -> str:
    o, c, t, e, plan = r["os"], r["cpu"], r["tools"], r["env"], r["transcription"]
    os_label = {"mac": "Mac", "windows": "Windows"}.get(o["system"], o["system"])
    lines = [f"מחשב: {os_label} · {c['name']} · {c.get('physical_cores')} ליבות · {r['ram_gb']}GB זיכרון"]
    nv = r["gpus"]["nvidia"]
    if nv:
        lines.append("כרטיס מסך: " + ", ".join(f"{g['name']} ({g['vram_gb']}GB)" for g in nv))
    tier_he = {"local-apple": "מקומי על המק (מהיר, חינם, פרטי)",
               "local-cuda": "מקומי על כרטיס המסך (מהיר מאוד, חינם, פרטי)",
               "local-cpu": "מקומי על המעבד (חינם ופרטי, איטי יותר)",
               "cloud": "בענן (סנטים לדקה, או קרדיט חינם)"}
    lines.append(f"תמלול מומלץ: {tier_he[plan['tier']]} — {plan['why']}")
    for b in r.get("blockers", []):
        lines.append("⛔ " + b)
    studio = r.get("studio")
    if studio:
        bad = [k for k, v in studio["checks"].items() if not v]
        lines.append("מצב הסטודיו: " + ("הכול תקין ✓" if not bad else "חסר/תקול: " + ", ".join(bad)))
    warn = []
    if e["home_non_ascii"]:
        warn.append("שם המשתמש במחשב בעברית — נשים את הסטודיו בנתיב באנגלית")
    if e["disk_free_gb"] != -1 and e["disk_free_gb"] < 15:
        warn.append(f"נשאר רק {e['disk_free_gb']}GB פנוי בדיסק — מומלץ לפנות לפחות 15GB")
    if o.get("rosetta"):
        warn.append("הטרמינל רץ במצב Rosetta — כדאי לפתוח אותו במצב רגיל (Apple Silicon)")
    if warn:
        lines.append("שימו לב: " + " · ".join(warn))
    lines.append(f"מיקום מומלץ לסטודיו: {r['suggested_workspace']}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace", type=Path, default=None)
    ap.add_argument("--json", action="store_true", help="print JSON only")
    ap.add_argument("--save", type=Path, default=None, help="also write the JSON report here")
    args = ap.parse_args()

    os_info = detect_os()
    cpu = detect_cpu(os_info["system"])
    ram = detect_ram_gb(os_info["system"])
    gpus = detect_gpus(os_info["system"])
    tools = detect_tools(os_info["system"])
    env = detect_env(args.workspace)
    report = {
        "os": os_info, "cpu": cpu, "ram_gb": ram, "gpus": gpus, "tools": tools, "env": env,
        "transcription": transcription_plan(os_info, cpu, ram, gpus, env["disk_free_gb"]),
        "suggested_workspace": suggest_workspace(os_info, env),
        "blockers": blockers(os_info),
    }
    report["missing"] = missing_tools(tools)
    if args.workspace:
        report["studio"] = workspace_health(args.workspace)

    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1255/cp437
        except Exception:
            pass
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(hebrew_summary(report))
        print("\n--- JSON ---")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
