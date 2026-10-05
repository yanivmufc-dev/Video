# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Build (or repair) the video studio, one resumable step at a time.

First run (from the skill, after uv was installed into <ws>/tools/uv):
    <ws>/tools/uv/uv run --python 3.12 <skill>/scripts/setup.py --workspace <ws>
Afterwards (from inside the studio):
    ./studio setup --resume          (Windows: .\\studio.cmd setup --resume)
    ./studio setup --step node       re-run a single step
    ./studio setup --status          show what is done

Steps (each is idempotent; progress lives in <ws>/.studio/state.json):
  workspace      folders, launchers, AGENTS.md/CLAUDE.md, agent permissions, tools + docs
  ffmpeg         portable full ffmpeg/ffprobe (Mac: Martin Riedl signed builds; Windows: Gyan)
  node           portable Node.js LTS from nodejs.org (checksum verified)
  remotion       Remotion project + animation kit, npm install, headless Chrome, Remotion agent skills
  transcription  hardware check -> local Hebrew model (downloaded + loaded) or a cloud engine
  effects        sound packs (CC0 + synthesized) and the starter emoji set
  demo           builds and renders a short demo through the whole pipeline -> output/demo.mp4

Nothing here needs admin rights, a password, Homebrew or winget. Anything that would
(e.g. macOS too old, Windows Smart App Control blocking a program) is reported with
status "needs_user" and a Hebrew explanation — the agent relays it and stops.
Output: one JSON line per step on stdout; progress on stderr.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _studio import KEYS_FILE, api_key  # noqa: E402

SKILL_VERSION = (HERE / "VERSION").read_text(encoding="utf-8").strip() if (HERE / "VERSION").exists() else "0"
SKILL_ASSETS = HERE / "assets" if (HERE / "assets").exists() else HERE.parent / "assets"
SKILL_REFS = HERE / "docs" if (HERE / "docs").exists() else HERE.parent / "references"
SYSTEM = platform.system()
IS_WIN, IS_MAC = SYSTEM == "Windows", SYSTEM == "Darwin"
EXE = ".exe" if IS_WIN else ""
STEPS = ["workspace", "ffmpeg", "node", "remotion", "transcription", "effects", "demo"]
REMOTION_VERSION = "4.0.530"  # tested; upgrade deliberately with: studio npx remotion upgrade
REMOTION_SKILLS_KEEP = {"remotion-best-practices", "remotion-captions", "remotion-create", "remotion-docs",
                        "remotion-markup", "remotion-multimedia", "remotion-render", "remotion-studio",
                        "remotion-upgrade", "remotion-interactivity"}
NEEDED_FILTERS = ["zscale", "tonemap", "loudnorm", "alimiter", "afade", "ebur128", "silencedetect",
                  "blackdetect", "freezedetect", "setparams", "fps", "aevalsrc", "anoisesrc", "ass"]

# The two launchers are written by setup (not shipped as files), so the skill package holds no
# .cmd/.sh executables — mail providers (Gmail) and antivirus block archives that contain them.
LAUNCHER_SH = r"""#!/bin/sh
# Video Studio launcher (Mac). Usage: ./studio help
# Everything the studio needs lives in this folder; this just points uv at it.
DIR="$(cd "$(dirname "$0")" && pwd)"
export UV_CACHE_DIR="$DIR/.cache/uv"
export UV_PYTHON_INSTALL_DIR="$DIR/tools/python"
export UV_MANAGED_PYTHON=1
export PYTHONUTF8=1
if [ ! -x "$DIR/tools/uv/uv" ]; then
  echo "[studio] tools/uv/uv is missing — the studio isn't installed yet (see the video-studio skill: setup)." >&2
  exit 3
fi
exec "$DIR/tools/uv/uv" run --quiet --no-project --python 3.12 "$DIR/tools/studio/studio.py" "$@"
"""

LAUNCHER_CMD = r"""@echo off
rem Video Studio launcher (Windows). Usage: .\studio.cmd help
rem Everything the studio needs lives in this folder; this just points uv at it.
setlocal
chcp 65001 >nul
set "DIR=%~dp0"
set "UV_CACHE_DIR=%DIR%.cache\uv"
set "UV_PYTHON_INSTALL_DIR=%DIR%tools\python"
set "UV_MANAGED_PYTHON=1"
set "PYTHONUTF8=1"
if not exist "%DIR%tools\uv\uv.exe" (
  echo [studio] tools\uv\uv.exe is missing - the studio is not installed yet. 1>&2
  exit /b 3
)
"%DIR%tools\uv\uv.exe" run --quiet --no-project --python 3.12 "%DIR%tools\studio\studio.py" %*
exit /b %ERRORLEVEL%
"""


class NeedsUser(Exception):
    """Something only the member can do (a click, a setting, a key). Message is Hebrew."""


def log(msg: str) -> None:
    print(f"[setup] {msg}", file=sys.stderr, flush=True)


# ------------------------------------------------------------------ state

class State:
    def __init__(self, ws: Path):
        self.path = ws / ".studio" / "state.json"
        self.data = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        self.data.setdefault("steps", {})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def mark(self, step: str, status: str, **extra) -> None:
        self.data["steps"][step] = {"status": status, "at": time.strftime("%Y-%m-%d %H:%M:%S"), **extra}
        self.save()

    def done(self, step: str) -> bool:
        return self.data["steps"].get(step, {}).get("status") == "done"


# ------------------------------------------------------------------ helpers

def download(url: str, dst: Path, what: str) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "video-studio-setup/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got, last = 0, 0.0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            got += len(chunk)
            if time.time() - last > 3:
                pct = f"{got * 100 // total}%" if total else f"{got >> 20} MB"
                log(f"downloading {what}: {pct}")
                last = time.time()
    tmp.replace(dst)
    return dst


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def env_for(ws: Path) -> dict:
    """Same environment the studio launcher builds (see studio.py)."""
    sys.path.insert(0, str(ws / "tools" / "studio"))
    import importlib
    studio = importlib.import_module("studio")
    return studio.studio_env()


def run(cmd: list[str], ws: Path, cwd: Path | None = None, check: bool = True, quiet: bool = False,
        timeout: int | None = None) -> subprocess.CompletedProcess:
    if not quiet:
        log("$ " + " ".join(str(c) for c in cmd))
    proc = subprocess.run([str(c) for c in cmd], cwd=str(cwd or ws), env=env_for(ws), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if check and proc.returncode != 0:
        tail = "\n".join((proc.stdout + "\n" + proc.stderr).strip().splitlines()[-25:])
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(map(str, cmd))}\n{tail}")
    return proc


def node_bin(ws: Path, name: str) -> Path:
    if IS_WIN:
        return ws / "tools" / "node" / (f"{name}.cmd" if name in ("npm", "npx") else f"{name}.exe")
    return ws / "tools" / "node" / "bin" / name


def mac_version() -> tuple[int, int]:
    v = platform.mac_ver()[0] or "0.0"
    parts = [int(x) for x in v.split(".")[:2]] + [0]
    return parts[0], parts[1]


def arch() -> str:
    m = platform.machine().lower()
    if IS_MAC:
        # under Rosetta platform.machine() says x86_64 — ask the kernel
        try:
            if subprocess.run(["sysctl", "-n", "hw.optional.arm64"], capture_output=True, text=True).stdout.strip() == "1":
                return "arm64"
        except Exception:
            pass
    return "arm64" if m in ("arm64", "aarch64") else "x64"


# ------------------------------------------------------------------ steps

def step_workspace(ws: Path, st: State, args) -> dict:
    s = str(ws)
    if not s.isascii():
        raise NeedsUser(f"נתיב הסטודיו ({s}) מכיל תווים שאינם באנגלית. בחרו נתיב באנגלית בלבד, "
                        r"למשל C:\VideoStudio או ~/VideoStudio.")
    if "onedrive" in s.lower() or "icloud" in s.lower() or "Mobile Documents" in s:
        raise NeedsUser("תיקיית הסטודיו נמצאת בתוך תיקייה מסונכרנת לענן (OneDrive/iCloud). "
                        "זה שובר התקנות וקבצים גדולים — בחרו תיקייה מקומית כמו C:\\VideoStudio.")
    for d in ["input", "projects", "output", "tools/studio", ".studio/logs", ".cache", ".tmp",
              ".claude", ".codex"]:
        (ws / d).mkdir(parents=True, exist_ok=True)
    # the studio's own tools + docs + assets (copied, so the studio works without the skill)
    tools = ws / "tools" / "studio"
    for f in [*HERE.glob("*.py"), *HERE.glob("*.json"), HERE / "VERSION"]:
        if f.resolve() != (tools / f.name).resolve():
            shutil.copy2(f, tools / f.name)
    if SKILL_ASSETS.resolve() != (tools / "assets").resolve():
        shutil.copytree(SKILL_ASSETS, tools / "assets", dirs_exist_ok=True)
    if SKILL_REFS.exists() and SKILL_REFS.resolve() != (tools / "docs").resolve():
        shutil.copytree(SKILL_REFS, tools / "docs", dirs_exist_ok=True)
    # workspace template: agent instructions and permissions. Files the member may have edited
    # (AGENTS.md, CLAUDE.md, the keys file) are only created when missing; --force refreshes them.
    tpl = SKILL_ASSETS / "workspace"
    always: set[str] = set()
    # an update refreshes the agent's instructions (they describe the new tools); the member's
    # previous copy is kept beside it. CLAUDE.md is never replaced: Claude Code saves memories there.
    refresh = {"AGENTS.md", "README.md"} if getattr(args, "update", False) else set()
    for src in tpl.rglob("*"):
        if src.is_dir():
            continue
        rel = src.relative_to(tpl)
        dst = ws / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if rel.name == "gitignore.txt":
            dst = ws / ".gitignore"
        if dst.exists() and rel.as_posix() in refresh and not args.force \
                and dst.read_bytes() != src.read_bytes():
            shutil.copy2(dst, dst.with_name(dst.stem + ".old" + dst.suffix))
            shutil.copy2(src, dst)
        elif not dst.exists() or rel.name in always or args.force:
            shutil.copy2(src, dst)
        elif rel.as_posix() == ".claude/settings.json":
            merge_permissions(src, dst)  # keep the member's own rules, add any new protections
    launcher = ws / "studio"
    launcher.write_text(LAUNCHER_SH, encoding="utf-8", newline="\n")
    launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    (ws / "studio.cmd").write_text(LAUNCHER_CMD, encoding="ascii", newline="\r\n")
    keys_file = ws / KEYS_FILE
    if not keys_file.exists():
        keys_file.write_text("# Service keys stay in this file on this computer (not in the chat).\n"
                             "# Remove the # at the start of a line and paste the key after the = sign.\n"
                             "# DEEPGRAM_API_KEY=\n# SONIOX_API_KEY=\n# GROQ_API_KEY=\n# OPENAI_API_KEY=\n"
                             "# PEXELS_API_KEY=\n# PIXABAY_API_KEY=\n", encoding="utf-8")
    if not IS_WIN:
        keys_file.chmod(0o600)  # readable by the member's own account only
    (ws / "tools" / "studio" / "VERSION").write_text(SKILL_VERSION + "\n", encoding="utf-8")
    st.data.update({"os": SYSTEM, "arch": arch(), "workspace": str(ws), "skill_version": args.version})
    return {"workspace": str(ws)}


def merge_permissions(template: Path, current: Path) -> None:
    """Add the template's allow/deny rules that an existing settings.json is missing."""
    try:
        cur = json.loads(current.read_text(encoding="utf-8"))
        tpl = json.loads(template.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return  # a hand-edited file we can't parse is left alone
    perms = cur.setdefault("permissions", {})
    changed = False
    for key in ("allow", "deny"):
        have = perms.setdefault(key, [])
        for rule in tpl.get("permissions", {}).get(key, []):
            if rule not in have:
                have.append(rule)
                changed = True
    if changed:
        current.write_text(json.dumps(cur, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def step_ffmpeg(ws: Path, st: State, args) -> dict:
    dest = ws / "tools" / "ffmpeg"
    ff, fp = dest / f"ffmpeg{EXE}", dest / f"ffprobe{EXE}"
    if not (ff.exists() and fp.exists()):
        dest.mkdir(parents=True, exist_ok=True)
        dl = ws / ".tmp" / "downloads"
        if IS_MAC:
            a = "arm64" if arch() == "arm64" else "amd64"
            for name in ("ffmpeg", "ffprobe"):
                # The "latest" link redirects to a versioned file; the publisher puts its SHA-256
                # next to it (<file>.sha256). Verify before unpacking, so only the genuine build runs.
                latest = f"https://ffmpeg.martin-riedl.de/redirect/latest/macos/{a}/release/{name}.zip"
                req = urllib.request.Request(latest, method="HEAD", headers={"User-Agent": "video-studio-setup/1.1"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    real = r.geturl()
                z = download(real, dl / f"{name}.zip", name)
                with urllib.request.urlopen(urllib.request.Request(
                        real + ".sha256", headers={"User-Agent": "video-studio-setup/1.1"}), timeout=60) as r:
                    expected = r.read().decode("ascii", "replace").split()[0].strip().lower()
                if not re.fullmatch(r"[0-9a-f]{64}", expected) or sha256(z) != expected:
                    z.unlink(missing_ok=True)
                    raise RuntimeError(f"{name}.zip failed its SHA-256 check (download corrupted or not the "
                                       "publisher's file) - run the step again: studio setup --step ffmpeg")
                with zipfile.ZipFile(z) as zf:
                    zf.extractall(dest)
            for p in (ff, fp):
                p.chmod(0o755)
                # Verified above against the publisher's checksum; without removing the quarantine
                # flag macOS refuses to run a program that a script downloaded.
                subprocess.run(["xattr", "-dr", "com.apple.quarantine", str(p)], capture_output=True)
        elif IS_WIN:
            api = json.loads(urllib.request.urlopen(urllib.request.Request(
                "https://api.github.com/repos/GyanD/codexffmpeg/releases/latest",
                headers={"User-Agent": "video-studio-setup/1.0"}), timeout=60).read())
            asset = next(a for a in api["assets"] if a["name"].endswith("-essentials_build.zip"))
            z = download(asset["browser_download_url"], dl / asset["name"], "ffmpeg")
            with zipfile.ZipFile(z) as zf:
                for m in zf.namelist():
                    if m.endswith(("/bin/ffmpeg.exe", "/bin/ffprobe.exe")):
                        (dest / Path(m).name).write_bytes(zf.read(m))
        else:
            raise NeedsUser("מערכת ההפעלה הזו לא נתמכת בהתקנה האוטומטית (רק Mac ו-Windows).")
        shutil.rmtree(dl, ignore_errors=True)
    try:
        ver = subprocess.run([str(ff), "-hide_banner", "-version"], capture_output=True, text=True, timeout=60)
    except OSError as e:
        raise NeedsUser("Windows חסם את ffmpeg (כנראה Smart App Control). פתחו את 'אבטחת Windows' > "
                        "'בקרת אפליקציות ודפדפן' ובדקו אם ffmpeg נחסם — או ספרו לי ונחליף גרסה. "
                        f"(שגיאה: {e})")
    if ver.returncode != 0:
        raise RuntimeError(f"ffmpeg does not start: {ver.stderr[-400:]}")
    filters = subprocess.run([str(ff), "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    missing = [f for f in NEEDED_FILTERS if not re.search(rf"\s{f}\s", filters)]
    if missing:
        raise RuntimeError(f"this ffmpeg build lacks filters: {missing}")
    return {"ffmpeg": ver.stdout.split("\n")[0][:80]}


def step_node(ws: Path, st: State, args) -> dict:
    dest = ws / "tools" / "node"
    node = node_bin(ws, "node")
    if node.exists():
        v = subprocess.run([str(node), "--version"], capture_output=True, text=True).stdout.strip()
        if v and int(v.lstrip("v").split(".")[0]) >= 22:
            return {"node": v}
    index = json.loads(urllib.request.urlopen("https://nodejs.org/dist/index.json", timeout=60).read())
    lts = next(r for r in index if r.get("lts"))
    ver = lts["version"]
    if IS_MAC:
        name = f"node-{ver}-darwin-{'arm64' if arch() == 'arm64' else 'x64'}.tar.gz"
    elif IS_WIN:
        name = f"node-{ver}-win-x64.zip"  # also runs (emulated) on Windows ARM
    else:
        raise NeedsUser("מערכת ההפעלה הזו לא נתמכת בהתקנה האוטומטית.")
    base = f"https://nodejs.org/dist/{ver}/"
    dl = ws / ".tmp" / "downloads"
    archive = download(base + name, dl / name, f"Node.js {ver}")
    sums = urllib.request.urlopen(base + "SHASUMS256.txt", timeout=60).read().decode()
    expected = next(line.split()[0] for line in sums.splitlines() if line.endswith(name))
    if sha256(archive) != expected:
        raise RuntimeError("Node.js download is corrupted (checksum mismatch) — run the step again")
    shutil.rmtree(dest, ignore_errors=True)
    tmp = dl / "node-extract"
    shutil.rmtree(tmp, ignore_errors=True)
    if name.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(tmp)
    else:
        with tarfile.open(archive) as tf:
            tf.extractall(tmp, filter="tar") if hasattr(tarfile, "data_filter") else tf.extractall(tmp)
    inner = next(tmp.iterdir())
    shutil.move(str(inner), str(dest))
    shutil.rmtree(dl, ignore_errors=True)
    v = subprocess.run([str(node_bin(ws, "node")), "--version"], capture_output=True, text=True).stdout.strip()
    return {"node": v}


def step_remotion(ws: Path, st: State, args) -> dict:
    if IS_MAC and mac_version() < (15, 0):
        raise NeedsUser(f"Remotion (מנוע הרינדור) דורש macOS 15 (Sequoia) ומעלה, ובמחשב הזה מותקן "
                        f"macOS {'.'.join(map(str, mac_version()))}. עדכנו את macOS דרך הגדרות המערכת > "
                        "כללי > עדכון תוכנה, ואז אמרו לי 'המשך התקנה'.")
    if IS_WIN and platform.machine().lower() in ("arm64", "aarch64"):
        log("Windows on ARM: Remotion has no native build; trying x64 emulation (unverified)")
    rem = ws / "remotion"
    kit = SKILL_ASSETS / "remotion-kit"
    rem.mkdir(exist_ok=True)
    # kit files are ours and get refreshed; the member's own work (custom/, projects/) is never touched
    for src in kit.rglob("*"):
        if src.is_dir():
            continue
        rel = src.relative_to(kit)
        dst = rem / rel
        protected = rel.parts[:2] in (("src", "custom"), ("src", "projects"))
        if protected and dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    pkg = json.loads((rem / "package.json").read_text(encoding="utf-8"))
    for dep in list(pkg["dependencies"]):
        if dep == "remotion" or dep.startswith("@remotion/"):
            pkg["dependencies"][dep] = REMOTION_VERSION
    (rem / "package.json").write_text(json.dumps(pkg, indent=2) + "\n", encoding="utf-8")
    npm = node_bin(ws, "npm")
    log("installing Remotion (first time: 1–5 minutes; Windows Defender can make it slower)")
    run([npm, "install", "--no-audit", "--no-fund", "--loglevel=error"], ws, cwd=rem, timeout=1800)
    npx = node_bin(ws, "npx")
    log("downloading the headless browser Remotion renders with (~95 MB)")
    run([npx, "remotion", "browser", "ensure"], ws, cwd=rem, timeout=900)
    # Remotion's official agent skills -> workspace root, as real copies (no symlinks: Windows-safe)
    try:
        run([npx, "remotion", "skills", "add"], ws, cwd=rem, timeout=600)
        src_root = rem / ".agents" / "skills"
        for target in (ws / ".agents" / "skills", ws / ".claude" / "skills"):
            target.mkdir(parents=True, exist_ok=True)
            for sk in src_root.iterdir() if src_root.exists() else []:
                if sk.name in REMOTION_SKILLS_KEEP:
                    shutil.copytree(sk, target / sk.name, dirs_exist_ok=True, symlinks=False)
        shutil.rmtree(rem / ".agents", ignore_errors=True)
        shutil.rmtree(rem / ".claude", ignore_errors=True)
        skills = "installed"
    except Exception as e:  # nice to have, not required
        log(f"Remotion agent skills skipped: {e}")
        skills = "skipped"
    # type-check the kit so a broken install is caught now, not at the first render
    run([npx, "tsc", "--noEmit", "-p", "."], ws, cwd=rem, timeout=600)
    return {"remotion": REMOTION_VERSION, "agent_skills": skills}


def step_transcription(ws: Path, st: State, args) -> dict:
    report = json.loads(run([sys.executable, HERE / "check_system.py", "--json", "--workspace", ws], ws,
                            quiet=True).stdout)
    plan = report["transcription"]
    engine = args.engine or st.data.get("transcription", {}).get("engine")
    if not engine:
        engine = "local" if plan["tier"] != "cloud" else "cloud?"
    cuda = plan["tier"] == "local-cuda"
    info = {"tier": plan["tier"], "why": plan["why"], "engine": engine, "cuda": cuda}
    st.data["transcription"] = info
    st.save()
    if engine == "cloud?":
        raise NeedsUser("המחשב הזה חלש מדי למודל העברית המקומי, אז התמלול ירוץ בענן. "
                        "בחרו ספק (ההמלצה: Deepgram — יש קרדיט חינם בלי כרטיס אשראי), צרו מפתח API "
                        f"והדביקו אותו בקובץ {KEYS_FILE} שבתיקיית הסטודיו. ואז: setup --step transcription --engine deepgram")
    if engine != "local":
        key = {"deepgram": "DEEPGRAM_API_KEY", "soniox": "SONIOX_API_KEY", "groq": "GROQ_API_KEY",
               "openai": "OPENAI_API_KEY"}[engine]
        os.environ["STUDIO_WORKSPACE"] = str(ws)
        if not api_key(key):
            raise NeedsUser(f"חסר המפתח {key}. צרו אותו באתר של הספק, פתחו את הקובץ {KEYS_FILE} בתיקיית "
                            f"הסטודיו והוסיפו שורה: {key}=המפתח שלכם — ואז אמרו לי 'המשך התקנה'.")
        return info
    log("downloading + loading the Hebrew speech model (ivrit.ai, ~1.7 GB — once)")
    cmd = [ws / "tools" / "uv" / f"uv{EXE}", "run", "--quiet", "--python", "3.12"]
    if cuda:
        cmd += ["--with", "nvidia-cublas-cu12"]
    out = run(cmd + [ws / "tools" / "studio" / "transcribe.py", ws / "projects", "--test-model"], ws,
              timeout=3600).stdout
    info["model_check"] = json.loads(out.strip().splitlines()[-1])
    st.data["transcription"] = info
    return info


def step_effects(ws: Path, st: State, args) -> dict:
    uvx = ws / "tools" / "uv" / f"uv{EXE}"
    run([uvx, "run", "--quiet", "--python", "3.12", ws / "tools" / "studio" / "fetch_assets.py",
         "--workspace", ws, "starter"], ws, timeout=900)
    lib = ws / "remotion" / "public" / "library"
    return {"sounds": len(list((lib / "sfx").rglob("*.wav"))), "emoji": len(list((lib / "emoji").iterdir()))}


def step_demo(ws: Path, st: State, args) -> dict:
    """A 6-second synthetic 'talking head' through the whole chain: ingest -> words -> plan ->
    build -> render -> master -> verify. Proves every piece works on THIS computer."""
    proj = ws / "projects" / "demo"
    shutil.rmtree(proj, ignore_errors=True)
    (proj / "transcripts").mkdir(parents=True, exist_ok=True)
    src = ws / ".tmp" / "demo_source.mp4"
    ff = ws / "tools" / "ffmpeg" / f"ffmpeg{EXE}"
    run([ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
         "gradients=s=1080x1920:r=30:d=6:c0=0x1d2671:c1=0xc33764:speed=0.02", "-f", "lavfi", "-i",
         "sine=f=220:d=6,volume=0.2", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", src],
        ws, quiet=True)
    uvx = ws / "tools" / "uv" / f"uv{EXE}"
    tools = ws / "tools" / "studio"
    run([uvx, "run", "--quiet", "--python", "3.12", tools / "ingest.py", src, "--project", proj], ws)
    words = [("הסטודיו", 0.3), ("שלכם", 0.8), ("מוכן", 1.3), ("לעבודה!", 1.8), ("Claude", 2.8), ("Code", 3.3),
             ("עורך", 3.8), ("בשבילכם", 4.3)]
    (proj / "transcripts" / "clip01.words.json").write_text(json.dumps({
        "duration": 6.0, "engine": "demo", "words": [{"text": t, "start": s, "end": s + 0.45, "prob": 1} for t, s in words]
    }, ensure_ascii=False), encoding="utf-8")
    (proj / "plan.json").write_text(json.dumps({
        "format": {"width": 1080, "height": 1920, "fps": 30},
        "theme": {"accent": "#FFD400", "font": "Heebo", "displayFont": "Secular One"},
        "segments": [{"clip": "clip01", "from": 0, "to": 2.5},
                     {"clip": "clip01", "from": 2.5, "to": 6.0, "zoom": 1.15, "transition": "whip"}],
        "captions": {"style": "karaoke", "keywords": ["מוכן", "Claude"], "y": 0.62},
        "overlays": [
            {"type": "hook", "at": 0, "dur": 2.3, "text": "סטודיו עריכה\nעם AI"},
            {"type": "emoji", "at": {"word": "מוכן"}, "dur": 1.2, "emoji": "🚀", "sfx": "pop"},
            {"type": "counter", "at": {"word": "עורך"}, "dur": 1.6, "from": 0, "to": 100, "suffix": "%", "sfx": "ding"},
            {"type": "lightleak", "at": 4.8, "dur": 1.0},
        ]}, ensure_ascii=False, indent=1), encoding="utf-8")
    run([uvx, "run", "--quiet", "--python", "3.12", tools / "build_edit.py", proj, "--workspace", ws], ws)
    out = run([uvx, "run", "--quiet", "--python", "3.12", tools / "studio.py", "render", "demo"], ws,
              check=False, timeout=1800)
    final = sorted((ws / "output").glob("demo_v*.mp4"))
    if not final or out.returncode != 0:
        raise RuntimeError("demo render failed:\n" + "\n".join((out.stdout + out.stderr).splitlines()[-30:]))
    return {"demo": str(final[-1]), "sheet": str(final[-1].with_name(final[-1].stem + "_sheet.png"))}


RUNNERS = {"workspace": step_workspace, "ffmpeg": step_ffmpeg, "node": step_node, "remotion": step_remotion,
           "transcription": step_transcription, "effects": step_effects, "demo": step_demo}


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace", type=Path, required=True)
    ap.add_argument("--step", choices=STEPS, help="run only this step (even if done)")
    ap.add_argument("--resume", action="store_true", help="run every step that is not done yet (default)")
    ap.add_argument("--status", action="store_true", help="print progress and exit")
    ap.add_argument("--engine", choices=["local", "soniox", "deepgram", "groq", "openai"],
                    help="transcription engine (default: decided from the hardware check)")
    ap.add_argument("--update", action="store_true",
                    help="refresh an existing studio to this skill's version (tools, kit, sounds); "
                         "projects, outputs, keys and the member's own edits stay")
    ap.add_argument("--force", action="store_true", help="also overwrite AGENTS.md and settings from the template")
    ap.add_argument("--version", default=SKILL_VERSION)
    args = ap.parse_args()
    ws = args.workspace.expanduser().resolve()
    ws.mkdir(parents=True, exist_ok=True)
    st = State(ws)

    if args.status:
        print(json.dumps({s: st.data["steps"].get(s, {"status": "pending"}) for s in STEPS}, ensure_ascii=False, indent=2))
        return 0

    if args.update:
        todo = ["workspace"] + [s for s in ("remotion", "effects") if st.done(s)]
    else:
        todo = [args.step] if args.step else [s for s in STEPS if not st.done(s)]
    if "workspace" not in todo and not (ws / "tools" / "studio" / "studio.py").exists():
        todo.insert(0, "workspace")
    exit_code = 0
    for step in todo:
        log(f"--- {step} ---")
        t0 = time.time()
        try:
            result = RUNNERS[step](ws, st, args)
            st.mark(step, "done", seconds=round(time.time() - t0), **result)
            print(json.dumps({"step": step, "status": "done", **result}, ensure_ascii=False), flush=True)
        except NeedsUser as e:
            st.mark(step, "needs_user", hint_he=str(e))
            print(json.dumps({"step": step, "status": "needs_user", "hint_he": str(e)}, ensure_ascii=False), flush=True)
            exit_code = 3
            break
        except Exception as e:  # noqa: BLE001 — report every failure the same way
            (ws / ".studio" / "logs").mkdir(parents=True, exist_ok=True)
            (ws / ".studio" / "logs" / f"{step}.log").write_text(str(e), encoding="utf-8")
            st.mark(step, "failed", error=str(e)[-1500:])
            print(json.dumps({"step": step, "status": "failed", "error": str(e)[-1500:]}, ensure_ascii=False), flush=True)
            exit_code = 1
            break
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
