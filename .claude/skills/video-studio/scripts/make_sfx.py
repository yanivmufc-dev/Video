# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Synthesize a starter sound-effects pack with ffmpeg — no downloads, no licenses.

    uv run tools/make_sfx.py remotion/public/library/sfx/synth
    uv run tools/make_sfx.py remotion/public/library/sfx/synth --preview   # also writes _preview.wav

Every sound is generated from math (noise + sine waves), so it belongs to whoever
made it — safe for commercial use, no attribution. They're deliberately short and
clean: a reel needs punctuation, not cinema. Real recorded packs (CC0) are added by
fetch_assets.py on top of these.

Sounds (name -> typical use):
  whoosh        transitions, B-roll entering           whoosh-short  fast swipe, text slide
  riser         build-up before a reveal (0.9 s)       boom          big reveal / drama hit
  pop           element / emoji pops in                 bubble        softer pop, chat bubbles
  click         UI click, cursor                        tick          counters, list items
  typing        typing text on screen (1 s)            ding          a number / fact lands
  chime         magic / idea moment                     success       done / checkmark
  error         mistake / wrong / warning               glitch        digital glitch cut
  shutter       screenshot / photo moment               swipe-up      CTA / 'follow' moment
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _studio import ffmpeg, run, utf8_console  # noqa: E402

SR = 48000

# name: (filtergraph producing mono audio, duration seconds)
SOUNDS: dict[str, tuple[str, float]] = {
    "whoosh": ("anoisesrc=d=0.55:c=pink:a=0.9,"
               "bandpass=f=1400:t=h:w=1800,"
               "volume='0.9*pow(sin(PI*t/0.55),2)':eval=frame,"
               "afade=t=out:st=0.42:d=0.13", 0.55),
    "whoosh-short": ("anoisesrc=d=0.28:c=pink:a=0.9,highpass=f=500,lowpass=f=7000,"
                     "volume='0.9*pow(sin(PI*t/0.28),2)':eval=frame", 0.28),
    "riser": ("aevalsrc='0.35*sin(2*PI*(180*t+260*t*t))*(t/0.9)+0.25*(random(0)*2-1)*pow(t/0.9,2)':d=0.9,"
              "highpass=f=150,afade=t=out:st=0.85:d=0.05", 0.9),
    "boom": ("aevalsrc='0.9*sin(2*PI*(45+60*exp(-8*t))*t)*exp(-4.5*t)':d=0.9,"
             "lowpass=f=400,afade=t=in:st=0:d=0.005", 0.9),
    "pop": ("aevalsrc='0.8*sin(2*PI*(300+900*exp(-40*t))*t)*exp(-30*t)':d=0.14,"
            "afade=t=in:st=0:d=0.003", 0.14),
    "bubble": ("aevalsrc='0.6*sin(2*PI*(500+700*(1-exp(-35*t)))*t)*exp(-22*t)':d=0.16,"
               "afade=t=in:st=0:d=0.004", 0.16),
    "click": ("anoisesrc=d=0.025:c=white:a=0.9,bandpass=f=2500:t=h:w=1500,"
              "volume='exp(-120*t)':eval=frame", 0.025),
    "tick": ("anoisesrc=d=0.03:c=white:a=0.8,bandpass=f=3800:t=h:w=900,"
             "volume='exp(-70*t)':eval=frame", 0.03),
    "typing": ("anoisesrc=d=1.0:c=white:a=0.7,bandpass=f=3000:t=h:w=1600,"
               "volume='exp(-90*mod(t,0.09+0.03*sin(7*t)))*lt(mod(t*11,1),0.5)':eval=frame", 1.0),
    "ding": ("aevalsrc='0.55*sin(2*PI*1318*t)*exp(-5*t)+0.2*sin(2*PI*2636*t)*exp(-8*t)':d=0.8", 0.8),
    "chime": ("aevalsrc='0.45*sin(2*PI*1046*t)*exp(-4*t)+0.4*sin(2*PI*1568*t)*exp(-4*(t-0.12))*gte(t,0.12)':d=1.0", 1.0),
    "success": ("aevalsrc='0.4*(sin(2*PI*523*t)*between(t,0,0.12)+sin(2*PI*659*t)*between(t,0.1,0.22)"
                "+sin(2*PI*784*t)*gte(t,0.2)*exp(-5*(t-0.2)))':d=0.8,afade=t=out:st=0.7:d=0.1", 0.8),
    "error": ("aevalsrc='0.35*(sgn(sin(2*PI*150*t))*0.5+sin(2*PI*155*t))*(between(t,0,0.16)+between(t,0.22,0.4))':d=0.42,"
              "lowpass=f=1800,afade=t=out:st=0.36:d=0.06", 0.42),
    "glitch": ("aevalsrc='0.5*sgn(sin(2*PI*(80+900*random(1))*t))*lt(random(2),0.55)':d=0.35,"
               "bandpass=f=2000:t=h:w=3000,afade=t=out:st=0.3:d=0.05", 0.35),
    "shutter": ("anoisesrc=d=0.18:c=white:a=0.9,bandpass=f=2200:t=h:w=2500,"
                "volume='exp(-60*t)+0.8*exp(-60*(t-0.07))*gte(t,0.07)':eval=frame", 0.18),
    "swipe-up": ("aevalsrc='0.4*sin(2*PI*(300*t+900*t*t))*pow(sin(PI*t/0.4),2)':d=0.4", 0.4),
}


def make(name: str, graph: str, dur: float, out_dir: Path) -> Path:
    raw = out_dir / f"_{name}.raw.wav"
    dst = out_dir / f"{name}.wav"
    run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-filter_complex",
         f"{graph},aresample={SR},aformat=channel_layouts=stereo", "-t", f"{dur}", "-ar", str(SR), str(raw)], quiet=True)
    level(raw, dst, fade_at=max(0.0, dur - 0.01))
    raw.unlink(missing_ok=True)
    return dst


# Every sound is leveled by how LOUD it sounds (its loudest 50 ms), not by its highest sample:
# peak-normalizing makes a soft click and a dense whoosh 15 dB apart, so the same "sfxGain"
# meant very different things. The peak is still kept under -1 dBFS.
TARGET_RMS = -16.0
MAX_PEAK = -1.0


def level(src: Path, dst: Path, fade_at: float | None = None) -> float:
    """Write src to dst at the common loudness; returns the gain used (dB)."""
    stats = run([ffmpeg(), "-hide_banner", "-nostats", "-i", str(src), "-af",
                 "astats=metadata=0:measure_perchannel=none:measure_overall=Peak_level+RMS_peak",
                 "-f", "null", "-"], quiet=True).stderr
    peak = re.search(r"Peak level dB:\s*(-?[\d.]+|-inf)", stats)
    rms = re.search(r"RMS peak dB:\s*(-?[\d.]+|-inf)", stats)
    if not (peak and rms) or "inf" in peak.group(1) or "inf" in rms.group(1):
        gain = 0.0
    else:
        gain = min(TARGET_RMS - float(rms.group(1)), MAX_PEAK - float(peak.group(1)))
    af = f"volume={gain:.2f}dB" + (f",afade=t=out:st={fade_at:.3f}:d=0.01" if fade_at is not None else "")
    tmp = dst.with_name("_lvl_" + dst.name)
    run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-af", af,
         "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le", str(tmp)], quiet=True)
    tmp.replace(dst)
    return gain


def main() -> int:
    utf8_console()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--preview", action="store_true", help="also write _preview.wav with all sounds in a row")
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    made = [make(n, g, d, args.out_dir) for n, (g, d) in SOUNDS.items()]
    print(f"[sfx] {len(made)} sounds -> {args.out_dir}")
    if args.preview:
        inputs: list[str] = []
        for p in made:
            inputs += ["-i", str(p)]
        pads = "".join(f"[{i}:a]apad=pad_dur=0.5[a{i}];" for i in range(len(made)))
        cat = "".join(f"[a{i}]" for i in range(len(made)))
        run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", *inputs, "-filter_complex",
             f"{pads}{cat}concat=n={len(made)}:v=0:a=1", str(args.out_dir / "_preview.wav")], quiet=True)
        print(f"[sfx] preview: {args.out_dir / '_preview.wav'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
