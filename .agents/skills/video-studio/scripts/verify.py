# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow>=10.1"]
# ///
"""Delivery gate: checks a finished video before anyone sees it.

    uv run tools/verify.py exports/my-reel_v1.mp4
    uv run tools/verify.py exports/my-reel_v1.mp4 --expect-duration 58.4 --sheet

Checks (each prints PASS / FAIL / WARN — a WARN never blocks delivery, it says what to look at):
  format     H.264 + yuv420p video, AAC audio, 48 kHz, faststart-friendly MP4
  size       resolution matches --expect-size (default: whatever the edit declared, else skip)
  duration   within 0.15 s of --expect-duration (if given)
  loudness   integrated -14 LUFS (+-1) and true peak <= -1 dBTP (use --lufs to change)
  black      no black stretch >= 0.5 s (blackdetect)
  frozen     WARN on a still picture >= 2 s (freezedetect) — often an intentional title card
  silence    no silence >= 2.5 s (silencedetect) — usually a broken audio track
Exit code 0 = all passed, 2 = something failed (the report says what).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _studio import (audio_stream, duration_of, ffmpeg, fraction, probe, run,  # noqa: E402
                     utf8_console, video_stream)


def analyze(src: Path) -> str:
    """One decoding pass collecting loudness, black, freeze and silence events."""
    vf = "blackdetect=d=0.5:pix_th=0.10,freezedetect=n=0.003:d=2"
    af = "ebur128=peak=true,silencedetect=n=-45dB:d=2.5"
    proc = run([ffmpeg(), "-hide_banner", "-nostats", "-i", str(src),
                "-vf", vf, "-af", af, "-f", "null", "-"], check=False, quiet=True)
    return proc.stderr


def main() -> int:
    utf8_console()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path)
    ap.add_argument("--expect-duration", type=float, default=None)
    ap.add_argument("--expect-size", type=str, default=None, help="e.g. 1080x1920")
    ap.add_argument("--lufs", type=float, default=-14.0)
    ap.add_argument("--sheet", action="store_true", help="also write a 12-frame contact sheet")
    args = ap.parse_args()

    info = probe(args.video)
    v, a = video_stream(info), audio_stream(info)
    results: list[tuple[str, bool, str]] = []

    if v:
        # yuvj420p = full-range 4:2:0; platforms accept it, but yuv420p is the safer default.
        fmt_ok = v.get("codec_name") == "h264" and v.get("pix_fmt") in ("yuv420p", "yuvj420p")
        results.append(("format-video", fmt_ok, f"{v.get('codec_name')} {v.get('pix_fmt')} "
                        f"{v.get('width')}x{v.get('height')} @ {fraction(v.get('avg_frame_rate')):.2f}fps"))
        if args.expect_size:
            w, h = (int(x) for x in args.expect_size.lower().split("x"))
            results.append(("size", (v.get("width"), v.get("height")) == (w, h),
                            f"{v.get('width')}x{v.get('height')} (expected {w}x{h})"))
    else:
        results.append(("format-video", False, "no video stream"))
    if a:
        a_ok = a.get("codec_name") == "aac" and int(a.get("sample_rate", 0)) == 48000
        results.append(("format-audio", a_ok, f"{a.get('codec_name')} {a.get('sample_rate')}Hz "
                        f"{a.get('channels')}ch"))
    else:
        results.append(("format-audio", False, "no audio stream"))

    dur = duration_of(info)
    if args.expect_duration is not None:
        results.append(("duration", abs(dur - args.expect_duration) <= 0.15,
                        f"{dur:.2f}s (expected {args.expect_duration:.2f}s)"))
    else:
        results.append(("duration", dur > 0, f"{dur:.2f}s"))

    log = analyze(args.video)
    m_i = re.findall(r"I:\s+(-?[\d.]+) LUFS", log)
    m_tp = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", log)
    if m_i:
        lufs = float(m_i[-1])
        tp = float(m_tp[-1]) if m_tp else 0.0
        results.append(("loudness", abs(lufs - args.lufs) <= 1.0 and tp <= -1.0,
                        f"{lufs:.1f} LUFS, true peak {tp:.1f} dBTP (target {args.lufs} / <= -1)"))
    else:
        results.append(("loudness", False, "could not measure"))

    blacks = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", log)
    results.append(("black", not blacks,
                    "none" if not blacks else ", ".join(f"{float(s):.1f}-{float(e):.1f}s" for s, e in blacks)))
    freezes = re.findall(r"freeze_start: ([\d.]+)", log)
    results.append(("frozen", not freezes,
                    "none" if not freezes else "frozen picture at " + ", ".join(f"{float(s):.1f}s" for s in freezes)
                    + " (fine if it is an intentional still)"))
    silences = re.findall(r"silence_start: ([\d.]+)", log)
    results.append(("silence", not silences,
                    "none" if not silences else "silence from " + ", ".join(f"{float(s):.1f}s" for s in silences)))

    advisory = {"frozen"}  # a still title card is legitimate; look at those moments, don't fail
    all_ok = all(ok for name, ok, _ in results if name not in advisory)
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'WARN' if name in advisory else 'FAIL'}  {name:<13} {detail}")

    if args.sheet:
        sheet = args.video.with_name(args.video.stem + "_sheet.png")
        subprocess.run([sys.executable, str(Path(__file__).with_name("contact_sheet.py")),
                        str(args.video), "--count", "12", "-o", str(sheet)], check=False)
        print(f"sheet: {sheet}  <- open it and LOOK before delivering")

    print(json.dumps({"video": str(args.video), "pass": all_ok,
                      "checks": {n: {"pass": ok, "detail": d, **({"warn": True} if n in advisory and not ok else {})}
                                 for n, ok, d in results}},
                     ensure_ascii=False))
    return 0 if all_ok else 2


if __name__ == "__main__":
    sys.exit(main())
