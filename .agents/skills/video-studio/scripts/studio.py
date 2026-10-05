# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""The studio's one front door. Every tool runs through here with the right environment.

Mac:      ./studio <command> [args]
Windows:  .\\studio.cmd <command> [args]

Commands (run `studio help` for this list):
  doctor                         health check of the whole studio (JSON + Hebrew summary)
  setup [--step S] [--resume]    (re)run installation steps
  new <name>                     create projects/<name>/
  ingest <project> <files...>    raw footage -> clean editing copies (media/clipNN.mp4)
  transcribe <project>           Hebrew word-level transcript of every clip (+ transcript.md)
  cuts <project> [--mode reel|youtube]   propose silence/filler/retake cuts (cuts.json + cuts.md)
  framing <project> [--apply]    where the face is in every clip (captions/overlays avoid it);
                                 landscape footage -> crop focus for vertical edits (alias: reframe)
  styles <project> [--styles a,b] the member's own footage in every style, side by side (style board)
  build <project>                plan.json -> timeline Remotion renders
  stills <project> <sec,sec,...> render single frames for review (fast)
  render <project> [--draft] [--replace]
                                 full render -> master audio -> verify -> output/<project>_vN.mp4
                                 (+ a lighter <project>_vN_share.mp4 for WhatsApp/upload);
                                 --replace overwrites the latest version instead of adding vN+1
  preview                        open Remotion Studio in the browser (keep it running)
  master <in> <out>              loudness master only (-14 LUFS)
  verify <video>                 delivery checks + contact sheet
  sheet <video> [...]            contact sheet of frames
  fetch <kind> ...               download assets (emoji, icons, broll, sfx) — see fetch_assets.py
  sfx-make                       regenerate the synthesized sound pack
  version                        the studio's installed version (compare with the skill's)
  npx|npm|node ...               run inside remotion/ with the studio's own Node
  ffmpeg|ffprobe ...             the studio's full ffmpeg (paths relative to where you are)
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent          # <ws>/tools/studio
WS = TOOLS.parent.parent                         # <ws>
IS_WIN = platform.system() == "Windows"
EXE = ".exe" if IS_WIN else ""


# Only these variables of the member's environment are passed on to the tools (the OS needs
# them to run programs); everything else the studio sets itself.
PASS_ENV = ["PATH", "SYSTEMROOT", "SystemRoot", "WINDIR", "COMSPEC", "PATHEXT", "HOME", "USERPROFILE",
            "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "ProgramFiles", "ProgramFiles(x86)", "HOMEDRIVE",
            "HOMEPATH", "USER", "USERNAME", "LOGNAME", "SHELL", "TERM", "LANG", "LC_ALL", "LC_CTYPE",
            "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "OS", "__CF_USER_TEXT_ENCODING",
            # proxies + custom certificates (office networks, filtered ISPs such as Netfree)
            "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "ALL_PROXY", "SSL_CERT_FILE", "SSL_CERT_DIR",
            "NODE_EXTRA_CA_CERTS", "REQUESTS_CA_BUNDLE", "UV_NATIVE_TLS"]
_PASS = {k.upper() for k in PASS_ENV}


def studio_env() -> dict:
    """Everything lives inside the workspace: no admin rights, no PATH edits, no surprises
    with Hebrew user names, OneDrive, or sandboxes that only allow writing to the workspace."""
    env: dict[str, str] = {}
    for name in PASS_ENV:  # look up only the listed names (Windows names are case-insensitive)
        if name in os.environ and name.upper() not in {k.upper() for k in env}:
            env[name] = os.environ[name]
    node_bin = WS / "tools" / "node" if IS_WIN else WS / "tools" / "node" / "bin"
    ffmpeg_bin = WS / "tools" / "ffmpeg"
    uv_bin = WS / "tools" / "uv"
    env["PATH"] = os.pathsep.join([str(node_bin), str(ffmpeg_bin), str(uv_bin), env.get("PATH", "")])
    cache, tmp = WS / ".cache", WS / ".tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    env.update({
        "STUDIO_WORKSPACE": str(WS),
        "STUDIO_FFMPEG": str(ffmpeg_bin / f"ffmpeg{EXE}"),
        "STUDIO_FFPROBE": str(ffmpeg_bin / f"ffprobe{EXE}"),
        "UV_CACHE_DIR": str(cache / "uv"),
        "UV_PYTHON_INSTALL_DIR": str(WS / "tools" / "python"),
        "UV_TOOL_DIR": str(WS / "tools" / "uv-tools"),
        "UV_MANAGED_PYTHON": "1",
        "HF_HOME": str(cache / "hf"),
        "HF_HUB_DISABLE_SYMLINKS_WARNING": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "npm_config_cache": str(cache / "npm"),
        "npm_config_update_notifier": "false",
        "npm_config_fund": "false",
        "npm_config_audit": "false",
        "DISABLE_TELEMETRY": "1",
        "REMOTION_DISABLE_TELEMETRY": "1",
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "TEMP": str(tmp), "TMP": str(tmp), "TMPDIR": str(tmp),
    })
    return env


def uv() -> str:
    return str(WS / "tools" / "uv" / f"uv{EXE}")


def node_tool(name: str) -> str:
    if IS_WIN:
        return str(WS / "tools" / "node" / (f"{name}.cmd" if name in ("npm", "npx") else f"{name}.exe"))
    return str(WS / "tools" / "node" / "bin" / name)


def run(cmd: list[str], cwd: Path | None = None) -> int:
    return subprocess.call(cmd, cwd=str(cwd or WS), env=studio_env())


def state() -> dict:
    try:
        return json.loads((WS / ".studio" / "state.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def here() -> Path:
    """The caller's folder: relative file paths are resolved from where the command was typed."""
    return Path.cwd()


def py(script: str, *args: str) -> int:
    """Run one of the studio's Python tools with its inline dependencies (uv installs them)."""
    extra: list[str] = []
    if script == "transcribe.py" and state().get("transcription", {}).get("cuda"):
        extra = ["--with", "nvidia-cublas-cu12"]  # NVIDIA GPU: the CUDA math library (Windows)
    return run([uv(), "run", "--quiet", "--python", "3.12", *extra, str(TOOLS / script), *args], cwd=here())


def project_dir(name: str) -> Path:
    p = Path(name)
    if not p.is_absolute() and not str(name).startswith(("projects/", "projects\\")):
        p = WS / "projects" / name
    elif not p.is_absolute():
        p = WS / p
    return p


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:48] or "project"


def next_version(slug: str, replace: bool = False) -> int:
    out = WS / "output"
    nums = [int(m.group(1)) for f in out.glob(f"{slug}_v*.mp4")
            if (m := re.search(r"_v(\d+)(?:_draft)?\.mp4$", f.name))]
    latest = max(nums, default=0)
    return max(latest, 1) if replace else latest + 1


def share_copy(final: Path) -> Path | None:
    """A lighter copy for WhatsApp / e-mail / upload — same picture and sound, about a third of the size.
    The master stays the file to archive; platforms re-encode anyway."""
    share = final.with_name(final.stem + "_share.mp4")
    ff = str(WS / "tools" / "ffmpeg" / f"ffmpeg{EXE}")
    cmd = [ff if Path(ff).exists() else "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(final),
           "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-maxrate", "6M", "-bufsize", "12M",
           "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
           "-c:a", "copy", "-movflags", "+faststart", str(share)]
    if run(cmd, cwd=WS) != 0 or not share.exists():
        print("[studio] could not make the lighter share copy (the master is fine)", file=sys.stderr)
        return None
    return share


def render(project: Path, draft: bool, extra: list[str], replace: bool = False) -> int:
    slug = project.name
    edit = project / "edit.json"
    if not edit.exists():
        print("[studio] no edit.json yet — run: studio build " + slug, file=sys.stderr)
        return 2
    data = json.loads(edit.read_text(encoding="utf-8"))
    renders = project / "renders"
    renders.mkdir(parents=True, exist_ok=True)
    version = next_version(slug, replace)
    raw = renders / f"{slug}_v{version}{'_draft' if draft else ''}_raw.mp4"
    cmd = [node_tool("npx"), "remotion", "render", "src/index.ts", slug, str(raw),
           "--codec=h264", "--color-space=bt709", "--concurrency=50%", "--log=warn"]
    cmd += ["--scale=0.5", "--x264-preset=veryfast", "--crf=26"] if draft else ["--crf=18"]
    cmd += extra
    print(f"[studio] rendering {slug} v{version}{' (draft)' if draft else ''} …", file=sys.stderr)
    code = run(cmd, cwd=WS / "remotion")
    if code != 0 or not raw.exists():
        print("[studio] render failed — see the error above (troubleshooting.md has the usual fixes)",
              file=sys.stderr)
        return code or 2
    final = WS / "output" / f"{slug}_v{version}{'_draft' if draft else ''}.mp4"
    code = py("master_audio.py", str(raw), str(final))
    if code not in (0, 2):
        return code
    expect = data["durationInFrames"] / data["fps"]
    size = f"{data['width'] // (2 if draft else 1)}x{data['height'] // (2 if draft else 1)}"
    code = py("verify.py", str(final), "--expect-duration", f"{expect:.3f}", "--expect-size", size, "--sheet")
    print(f"[studio] output: {final}  ({final.stat().st_size / 1e6:.0f} MB)")
    if not draft:
        share = share_copy(final)
        if share:
            print(f"[studio] share:  {share}  ({share.stat().st_size / 1e6:.0f} MB)")
    return code


def stills(project: Path, times: str, comp: str | None = None) -> int:
    """Single frames for review — one bundle for all of them (fast)."""
    edit_file = WS / "remotion" / "src" / "projects" / f"{comp}.json" if comp else project / "edit.json"
    data = json.loads(edit_file.read_text(encoding="utf-8"))
    sheets = project / "sheets"
    jobs = []
    for t in [float(x) for x in times.split(",") if x.strip()]:
        frame = min(data["durationInFrames"] - 1, max(0, round(t * data["fps"])))
        jobs.append(f"{comp or project.name}@{frame}")
    return run([node_tool("node"), "scripts/stills.mjs", str(sheets), "0.5", *jobs], cwd=WS / "remotion")


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass
    if not argv or argv[0] in ("help", "-h", "--help"):
        print(__doc__)
        return 0
    cmd, args = argv[0], argv[1:]

    if cmd == "doctor":
        return py("check_system.py", "--workspace", str(WS), *args)
    if cmd == "setup":
        return py("setup.py", "--workspace", str(WS), *args)
    if cmd == "new":
        if not args:
            print("usage: studio new <name>", file=sys.stderr)
            return 2
        slug = slugify(" ".join(args))
        p = WS / "projects" / slug
        for sub in ("media", "transcripts", "assets", "renders", "sheets"):
            (p / sub).mkdir(parents=True, exist_ok=True)
        notes = p / "notes.md"
        if not notes.exists():
            notes.write_text(f"# {' '.join(args)}\n\n(brief, decisions and feedback — the agent appends here)\n",
                             encoding="utf-8")
        print(p)
        return 0
    if cmd == "ingest":
        if len(args) < 2:
            print("usage: studio ingest <project> <files...>", file=sys.stderr)
            return 2
        return py("ingest.py", *args[1:], "--project", str(project_dir(args[0])))
    if cmd == "transcribe":
        code = py("transcribe.py", str(project_dir(args[0])), *args[1:])
        return code or py("pack_transcript.py", str(project_dir(args[0])))
    if cmd == "cuts":
        return py("cut_plan.py", str(project_dir(args[0])), *args[1:])
    if cmd in ("reframe", "framing"):
        return py("reframe.py", str(project_dir(args[0])), *args[1:])
    if cmd == "styles":
        return py("style_board.py", str(project_dir(args[0])), "--workspace", str(WS), *args[1:])
    if cmd == "build":
        return py("build_edit.py", str(project_dir(args[0])), "--workspace", str(WS), *args[1:])
    if cmd == "stills":
        name = Path(args[0]).name
        if "--" in name:  # a variant (style board / --variant build): <project>--<variant>
            return stills(project_dir(name.split("--", 1)[0]), args[1], comp=name)
        return stills(project_dir(args[0]), args[1])
    if cmd == "render":
        draft = "--draft" in args
        replace = "--replace" in args
        extra = [a for a in args[1:] if a not in ("--draft", "--replace")]
        return render(project_dir(args[0]), draft, extra, replace)
    if cmd == "version":
        v = TOOLS / "VERSION"
        print(v.read_text(encoding="utf-8").strip() if v.exists() else "unknown (installed before 1.1)")
        return 0
    if cmd == "preview":
        return run([node_tool("npx"), "remotion", "studio", *args], cwd=WS / "remotion")
    if cmd == "master":
        return py("master_audio.py", *args)
    if cmd == "verify":
        return py("verify.py", *args)
    if cmd == "sheet":
        return py("contact_sheet.py", *args)
    if cmd == "fetch":
        return py("fetch_assets.py", "--workspace", str(WS), *args)
    if cmd == "sfx-make":
        return py("make_sfx.py", str(WS / "remotion" / "public" / "library" / "sfx" / "synth"), *args)
    if cmd in ("npx", "npm", "node"):
        cwd = WS / "remotion" if (WS / "remotion" / "package.json").exists() else WS
        return run([node_tool(cmd), *args], cwd=cwd)
    if cmd in ("ffmpeg", "ffprobe"):
        return run([str(WS / "tools" / "ffmpeg" / f"{cmd}{EXE}"), *args], cwd=here())
    print(f"[studio] unknown command '{cmd}'. Run: studio help", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
