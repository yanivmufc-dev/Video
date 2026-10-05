# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow>=10.1"]
# ///
"""Style board: the member's OWN footage rendered in several styles, side by side, so they
choose with their eyes instead of guessing from words.

    uv run tools/style_board.py projects/my-reel                       # all styles
    uv run tools/style_board.py projects/my-reel --styles punch,neon,cinematic
    uv run tools/style_board.py projects/my-reel --at 12.5             # which moment to show

Needs: ingest + transcribe done (plan.json optional). For every style it builds a variant
(`<project>--style-<name>`), renders two frames — the speaker with captions + hook, and a
full-screen scene in that style — and tiles them into projects/<p>/sheets/style_board.png,
numbered. Variants are removed from the Remotion Studio list afterwards.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _studio import read_json, utf8_console, write_json  # noqa: E402

HERE = Path(__file__).resolve().parent


def base_plan(project: Path) -> dict:
    plan_file = project / "plan.json"
    if plan_file.exists():
        plan = read_json(plan_file)
    else:
        cuts = project / "cuts.json"
        if cuts.exists():
            segs = read_json(cuts)["segments"]
        else:
            first = sorted((project / "transcripts").glob("*.words.json"))[0]
            d = read_json(first)
            segs = [{"clip": first.name.split(".")[0], "from": 0, "to": d["duration"]}]
        plan = {"segments": segs, "captions": {}}
    keep = {k: plan[k] for k in ("format", "segments", "fixes") if k in plan}
    keep["captions"] = {k: v for k, v in plan.get("captions", {}).items() if k in ("keywords", "emojis", "y")}
    return keep


def sentence_at(project: Path, t_hint: float) -> tuple[str, str]:
    """A short hook text and a statement from the transcript (first sentence / a later one)."""
    text = ""
    for f in sorted((project / "transcripts").glob("*.words.json")):
        for w in read_json(f)["words"]:
            t = w["text"].strip()
            # Whisper splits "סטארט-אפים" into "סטארט" + "-אפים": glue, never "סטארט -אפים"
            text += t if (not text or t.startswith(("-", "־"))) else " " + t
    sentences = [s.strip() for s in text.replace("?", ".").replace("!", ".").split(".") if len(s.split()) >= 3]
    hook = " ".join((sentences[0] if sentences else text).split()[:6])
    stmt = " ".join((sentences[1] if len(sentences) > 1 else hook).split()[:7])
    return hook, stmt


def main() -> int:
    utf8_console()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", type=Path)
    ap.add_argument("--workspace", type=Path, default=None)
    ap.add_argument("--styles", default=None, help="comma list (default: all)")
    ap.add_argument("--at", type=float, default=None, help="second of the final cut to show (default: ~30%)")
    args = ap.parse_args()
    project = args.project.resolve()
    ws = (args.workspace or project.parent.parent).resolve()
    styles = {k: v for k, v in read_json(HERE / "styles.json").items() if not k.startswith("_")}
    aliases = {"hormozi": "punch"}  # 1.0 name
    names = [aliases.get(s.strip(), s.strip()) for s in args.styles.split(",")] if args.styles else list(styles)
    base = base_plan(project)
    hook, stmt = sentence_at(project, 0)
    fps = int(base.get("format", {}).get("fps", 30))
    total = sum(float(s["to"]) - float(s["from"]) for s in base["segments"])
    t_speaker = args.at if args.at is not None else round(total * 0.3, 2)
    t_scene = round(min(total - 1.5, t_speaker + 2.5), 2)

    jobs, ids = [], []
    for name in names:
        if name not in styles:
            print(f"[styles] unknown style {name}", file=sys.stderr)
            continue
        st = styles[name]
        plan = {**base, "style": name}
        plan["overlays"] = [
            {"type": "hook", "at": max(0.0, t_speaker - 0.6), "dur": 1.4, "text": st["name_he"]},
            {"type": "scene", "kind": "statement", "at": t_scene - 0.4, "dur": 1.6, "text": stmt,
             "kicker": st["name_he"], "sfx": "none", "enter": "cut"},
        ]
        vdir = project / "styles" / f"style-{name}"
        write_json(vdir / "plan.json", plan)
        cmd = [sys.executable, str(HERE / "build_edit.py"), str(project), "--workspace", str(ws),
               "--plan", str(vdir / "plan.json"), "--variant", f"style-{name}"]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            print(f"[styles] {name}: build failed: {r.stderr[-400:]}", file=sys.stderr)
            continue
        cid = f"{project.name}--style-{name}"
        ids.append((name, cid))
        jobs += [f"{cid}@{round(t_speaker * fps)}", f"{cid}@{round(t_scene * fps)}"]

    out_dir = project / "sheets" / "styles"
    node = ws / "tools" / "node" / ("node.exe" if sys.platform == "win32" else "bin/node")
    r = subprocess.run([str(node), "scripts/stills.mjs", str(out_dir), "0.35", *jobs], cwd=ws / "remotion",
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(r.stderr[-1500:], file=sys.stderr)
        return 1
    paths = [Path(p) for p in r.stdout.split("\n") if p.strip().endswith(".png")]

    # tile: one column per style (speaker frame over scene frame), numbered
    tiles = [(ids[i // 2][0], Image.open(paths[i]).convert("RGB"), Image.open(paths[i + 1]).convert("RGB"))
             for i in range(0, len(paths) - 1, 2)]
    if not tiles:
        return 1
    tw, th = tiles[0][1].size
    cols = min(4, len(tiles))
    rows = math.ceil(len(tiles) / cols)
    pad, lab = 10, 46
    board = Image.new("RGB", (cols * (tw + pad) + pad, rows * (2 * th + lab + 2 * pad) + pad), (18, 18, 18))
    d = ImageDraw.Draw(board)
    font = ImageFont.load_default(size=34)
    legend = {}
    for i, (name, a, b) in enumerate(tiles):
        c, r_ = i % cols, i // cols
        x = pad + c * (tw + pad)
        y = pad + r_ * (2 * th + lab + 2 * pad)
        d.text((x + 8, y + 4), f"{i + 1}. {name}", fill=(255, 214, 0), font=font)
        board.paste(a, (x, y + lab))
        board.paste(b, (x, y + lab + th + pad))
        legend[i + 1] = {"style": name, "he": styles[name]["name_he"], "desc": styles[name]["desc_he"]}
    out = project / "sheets" / "style_board.png"
    board.save(out)
    write_json(project / "sheets" / "style_board.json", legend)

    # remove the temporary variants from the Studio list
    pdir = ws / "remotion" / "src" / "projects"
    for _, cid in ids:
        (pdir / f"{cid}.json").unlink(missing_ok=True)
    real = project / "edit.json"
    if real.exists():
        subprocess.run([sys.executable, str(HERE / "build_edit.py"), str(project), "--workspace", str(ws)],
                       capture_output=True)
    else:
        entries = sorted(p.stem for p in pdir.glob("*.json"))
        lines = ["// AUTO-GENERATED by tools/build_edit.py — do not edit by hand.",
                 "import type {EditData} from '../kit/types';"]
        lines += [f"import p{i} from './{n}.json';" for i, n in enumerate(entries)]
        lines += ["", "export const projects: EditData[] = [" + ", ".join(f"p{i} as unknown as EditData" for i in range(len(entries))) + "];"]
        (pdir / "index.ts").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out)
    print(json.dumps(legend, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
