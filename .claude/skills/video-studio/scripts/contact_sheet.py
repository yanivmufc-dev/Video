# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow>=10.1"]
# ///
"""Contact sheet: many frames of a video on one labeled image, so the agent can LOOK.

    uv run tools/contact_sheet.py video.mp4 --every 1            # one frame per second
    uv run tools/contact_sheet.py video.mp4 --times 0.5,3.2,7.9  # exact moments (seconds)
    uv run tools/contact_sheet.py video.mp4 --count 12           # 12 frames spread evenly
    uv run tools/contact_sheet.py video.mp4 --every 0.5 --start 10 --end 20 -o sheet.png

Tip: sample effects at their MIDDLE, not their first frame — a frame taken 2% into
an animation shows a half-faded element and looks like a bug when it isn't.
"""
from __future__ import annotations

import argparse
import math
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _studio import duration_of, ffmpeg, probe, run, utf8_console  # noqa: E402


def grab(src: Path, t: float, width: int, out: Path) -> bool:
    proc = run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.3f}",
                "-i", str(src), "-frames:v", "1", "-vf", f"scale={width}:-2", str(out)],
               check=False, quiet=True)
    return proc.returncode == 0 and out.exists()


def main() -> int:
    utf8_console()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--every", type=float, help="seconds between frames")
    g.add_argument("--times", type=str, help="comma-separated seconds")
    g.add_argument("--count", type=int, help="N frames spread evenly (default 12)")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=None)
    ap.add_argument("--cols", type=int, default=0, help="columns (auto if 0)")
    ap.add_argument("--width", type=int, default=270, help="thumbnail width in px")
    ap.add_argument("--grid", action="store_true", help="draw 0.1 guide lines to measure positions (x/y 0–1)")
    ap.add_argument("-o", "--out", type=Path, default=None)
    args = ap.parse_args()

    dur = duration_of(probe(args.video))
    end = min(args.end if args.end is not None else dur, dur)
    if args.times:
        times = [float(t) for t in args.times.split(",") if t.strip()]
    elif args.every:
        n = int((end - args.start) / args.every) + 1
        times = [args.start + i * args.every for i in range(n)]
    else:
        n = args.count or 12
        span = end - args.start
        times = [args.start + span * (i + 0.5) / n for i in range(n)]
    times = [min(max(0.0, t), max(0.0, dur - 0.05)) for t in times]
    if len(times) > 120:
        sys.exit(f"[sheet] {len(times)} frames is too many for one sheet — narrow --start/--end")

    frames: list[tuple[float, Image.Image]] = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, t in enumerate(times):
            p = Path(tmp) / f"f{i:04d}.png"
            if grab(args.video, t, args.width, p):
                frames.append((t, Image.open(p).convert("RGB")))
    if not frames:
        sys.exit("[sheet] could not extract any frame")

    cols = args.cols or min(len(frames), 6 if frames[0][1].height > frames[0][1].width else 4)
    rows = math.ceil(len(frames) / cols)
    tw, th = frames[0][1].size
    label_h = 30
    sheet = Image.new("RGB", (cols * tw + (cols + 1) * 6, rows * (th + label_h) + (rows + 1) * 6), (20, 20, 20))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=20)
    for i, (t, img) in enumerate(frames):
        c, r = i % cols, i // cols
        x, y = 6 + c * (tw + 6), 6 + r * (th + label_h + 6)
        tile = img.resize((tw, th))
        if args.grid:
            g = ImageDraw.Draw(tile)
            for k in range(1, 10):
                col = (255, 60, 60) if k == 5 else (0, 255, 255)
                g.line([(0, th * k / 10), (tw, th * k / 10)], fill=col, width=1)
                g.line([(tw * k / 10, 0), (tw * k / 10, th)], fill=col, width=1)
                g.text((2, th * k / 10 - 11), f".{k}", fill=col, font=ImageFont.load_default(size=10))
        sheet.paste(tile, (x, y + label_h))
        draw.text((x + 4, y + 4), f"{int(t // 60)}:{t % 60:05.2f}", fill=(255, 220, 0), font=font)

    if args.out:
        out = args.out
    elif args.video.parent.name == "media" and (args.video.parent.parent / "sheets").is_dir():
        out = args.video.parent.parent / "sheets" / f"{args.video.stem}_sheet.png"  # keep media/ clean
    else:
        out = args.video.with_name(args.video.stem + "_sheet.png")
    sheet.save(out)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
