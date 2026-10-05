# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Final audio master: two-pass EBU R128 loudness to social-media level.

    uv run tools/master_audio.py render.mp4 final.mp4            # -14 LUFS, TP -1.5
    uv run tools/master_audio.py render.mp4 final.mp4 --lufs -16 # quieter (podcast/YouTube long-form)

The video stream is copied untouched; only the audio is re-encoded (AAC 48 kHz).

Pitfalls this script already handles (each one bit us in production):
  * loudnorm silently resamples to 192 kHz  -> we force 48 kHz at the end.
  * AAC encoding after loudnorm re-creates true peaks -> target TP -1.5 and add a
    limiter 0.5 dB under it with level=disabled (otherwise alimiter
    auto-normalizes and undoes the work). Platforms want <= -1 dBTP.
  * linear=true silently degrades to dynamic mode when the gain would clip (peaky speech,
    very quiet sources) -> we pre-gain + limit first, so the real pass stays linear, and
    report normalization_type.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _studio import ffmpeg, run, utf8_console  # noqa: E402


def last_json_block(text: str) -> dict:
    blocks = re.findall(r"\{[^{}]*\}", text, flags=re.S)
    if not blocks:
        sys.exit("[master] could not read loudnorm measurements from ffmpeg output")
    return json.loads(blocks[-1])


def measure(src: Path, lufs: float, tp: float, lra: float) -> dict:
    af = f"loudnorm=I={lufs}:TP={tp}:LRA={lra}:print_format=json"
    proc = run([ffmpeg(), "-hide_banner", "-nostats", "-i", str(src), "-vn", "-af", af,
                "-f", "null", "-"])
    return last_json_block(proc.stderr)


def main() -> int:
    utf8_console()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", type=Path)
    ap.add_argument("dst", type=Path)
    ap.add_argument("--lufs", type=float, default=-14.0, help="integrated loudness target")
    ap.add_argument("--tp", type=float, default=-1.5, help="true-peak ceiling (dBTP)")
    ap.add_argument("--lra", type=float, default=11.0)
    ap.add_argument("--bitrate", default="192k")
    args = ap.parse_args()

    if not args.src.exists():
        sys.exit(f"[master] missing input: {args.src}")
    if args.src.resolve() == args.dst.resolve():
        sys.exit("[master] output must be a different file than the input")

    m = measure(args.src, args.lufs, args.tp, args.lra)
    print(f"[master] measured: {m['input_i']} LUFS, TP {m['input_tp']} dBTP", file=sys.stderr)

    # Robust recipe (keeps loudnorm in LINEAR mode, i.e. no pumping):
    #   1) gain the whole mix to the target and catch the peaks with a limiter -> 24-bit WAV
    #   2) measure that, then a linear loudnorm pass + a final limiter -> AAC
    # AAC encoding overshoots peaks by ~0.5 dB, so the limiters sit 0.5 dB under the target.
    limit = round(10 ** ((args.tp - 0.5) / 20), 3)  # -1.5 dBTP target -> -2.0 dBFS -> 0.794
    gain = args.lufs - float(m["input_i"])
    with tempfile.TemporaryDirectory() as tmp:
        pre = Path(tmp) / "pre.wav"
        run([ffmpeg(), "-hide_banner", "-nostats", "-y", "-i", str(args.src), "-vn", "-af",
             f"volume={gain:.2f}dB,alimiter=limit={limit}:level=disabled:attack=1:release=60,aresample=48000",
             "-ar", "48000", "-c:a", "pcm_s24le", str(pre)])
        m2 = measure(pre, args.lufs, args.tp, args.lra)
        loudnorm = (f"loudnorm=I={args.lufs}:TP={args.tp}:LRA={max(args.lra, float(m2['input_lra']) + 1):.1f}"
                    f":measured_I={m2['input_i']}:measured_TP={m2['input_tp']}"
                    f":measured_LRA={m2['input_lra']}:measured_thresh={m2['input_thresh']}"
                    f":offset={m2['target_offset']}:linear=true:print_format=json")
        chain = f"{loudnorm},alimiter=limit={limit}:level=disabled,aresample=48000"
        args.dst.parent.mkdir(parents=True, exist_ok=True)
        proc = run([ffmpeg(), "-hide_banner", "-nostats", "-y", "-i", str(args.src), "-i", str(pre),
                    "-map", "0:v?", "-map", "1:a", "-c:v", "copy",
                    "-af", chain, "-ar", "48000", "-c:a", "aac", "-b:a", args.bitrate,
                    "-movflags", "+faststart", str(args.dst)])
    second = last_json_block(proc.stderr)

    final = measure(args.dst, args.lufs, args.tp, args.lra)
    ok_i = abs(float(final["input_i"]) - args.lufs) <= 1.0
    ok_tp = float(final["input_tp"]) <= -1.0
    print(json.dumps({
        "output": str(args.dst),
        "integrated_lufs": float(final["input_i"]),
        "true_peak_dbtp": float(final["input_tp"]),
        "normalization_type": second.get("normalization_type"),
        "pass": ok_i and ok_tp,
    }, ensure_ascii=False, indent=2))
    return 0 if (ok_i and ok_tp) else 2


if __name__ == "__main__":
    sys.exit(main())
