# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Bring any raw footage into a project as clean, uniform editing copies ("proxies").

    uv run tools/ingest.py input/IMG_4412.MOV input/IMG_4413.MOV --project projects/my-reel
    uv run tools/ingest.py input/*.mp4 --project projects/my-reel --fps 25

Why: phones record variable frame rate, HEVC, 10-bit HDR, rotated, 4K. Remotion wants
constant frame rate, H.264, 8-bit SDR. Converting once up front makes every later step
(cutting on word timestamps, preview, render) fast and predictable.

For each file it writes projects/<p>/media/clipNN.mp4:
  * H.264 High, yuv420p, BT.709 SDR (HDR is tone-mapped), CFR at --fps
  * long side <= 1920 px (never upscaled), rotation baked in
  * AAC 48 kHz stereo, 1-second keyframes (fast, accurate seeking), faststart
and records the mapping (clip01 <- "IMG_4412.MOV", with its properties) in
projects/<p>/media/sources.json. Original files are never modified. Already-ingested
files are skipped, so re-running is safe.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _studio import (audio_stream, duration_of, ffmpeg, fraction, probe, read_json,  # noqa: E402
                     run, utf8_console, video_stream, write_json)

HDR_TRANSFERS = {"smpte2084", "arib-std-b67"}
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mts", ".m2ts", ".3gp"}
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}


def rotation_of(vs: dict) -> int:
    for sd in vs.get("side_data_list", []) or []:
        if "rotation" in sd:
            return int(round(float(sd["rotation"])))
    tag = (vs.get("tags") or {}).get("rotate")
    return int(tag) if tag else 0


def describe(src: Path) -> dict:
    info = probe(src)
    vs, aus = video_stream(info), audio_stream(info)
    d = {"original": src.name, "duration": round(duration_of(info), 3), "audio": bool(aus)}
    if vs:
        rot = rotation_of(vs)
        w, h = int(vs.get("width", 0)), int(vs.get("height", 0))
        if abs(rot) in (90, 270):
            w, h = h, w
        d.update({
            "width": w, "height": h, "rotation": rot,
            "codec": vs.get("codec_name"), "pix_fmt": vs.get("pix_fmt"),
            "fps_avg": round(fraction(vs.get("avg_frame_rate")), 3),
            "fps_nominal": round(fraction(vs.get("r_frame_rate")), 3),
            "hdr": vs.get("color_transfer") in HDR_TRANSFERS or vs.get("color_primaries") == "bt2020",
            "transfer": vs.get("color_transfer"),
        })
        d["vfr"] = abs(d["fps_avg"] - d["fps_nominal"]) > 0.05
    return d


def video_filter(d: dict, fps: int, max_side: int) -> str:
    chain = []
    if d.get("hdr"):
        # HDR (iPhone HLG / Dolby Vision, 10-bit) -> SDR BT.709. Without this, HDR footage
        # renders grey and washed out. zscale+tonemap exist in stock ffmpeg builds.
        chain.append("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
                     "tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv")
    w, h = d["width"], d["height"]
    scale = min(1.0, max_side / max(w, h))
    tw, th = int(w * scale) // 2 * 2, int(h * scale) // 2 * 2
    chain.append(f"scale={tw}:{th}:flags=lanczos")
    chain.append(f"fps={fps}")
    chain.append("format=yuv420p")
    return ",".join(chain)


def main() -> int:
    utf8_console()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--fps", type=int, default=30, help="project frame rate (30 for social; 25 for PAL cameras)")
    ap.add_argument("--max-side", type=int, default=1920)
    ap.add_argument("--crf", type=int, default=18)
    args = ap.parse_args()

    media = args.project / "media"
    media.mkdir(parents=True, exist_ok=True)
    manifest_path = media / "sources.json"
    manifest = read_json(manifest_path) if manifest_path.exists() else {"clips": []}
    by_original = {c["source_path"]: c for c in manifest["clips"]}

    for src in args.files:
        src = src.resolve()
        if not src.exists():
            print(f"[ingest] skip (missing): {src}", file=sys.stderr)
            continue
        if src.suffix.lower() not in VIDEO_EXT | AUDIO_EXT:
            print(f"[ingest] skip (not video/audio): {src.name}", file=sys.stderr)
            continue
        stat = src.stat()
        prev = by_original.get(str(src))
        if prev and prev.get("size") == stat.st_size and (media / f"{prev['clip']}.mp4").exists():
            print(f"[ingest] already ingested: {src.name} -> {prev['clip']}", file=sys.stderr)
            continue

        d = describe(src)
        clip = prev["clip"] if prev else f"clip{len(manifest['clips']) + 1:02d}"
        out = media / f"{clip}.mp4"
        cmd = [ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(src)]
        if "width" in d:
            cmd += ["-vf", video_filter(d, args.fps, args.max_side),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", str(args.crf),
                    "-profile:v", "high", "-g", str(args.fps), "-keyint_min", str(args.fps),
                    "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
                    "-color_range", "tv"]
        else:
            # audio-only source (voice-over): black 1080x1920 picture so it can be edited the same way
            cmd = [ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
                   "-f", "lavfi", "-i", f"color=c=black:s=1080x1920:r={args.fps}", "-i", str(src),
                   "-shortest", "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast",
                   "-crf", "28", "-pix_fmt", "yuv420p"]
            d.update({"width": 1080, "height": 1920, "audio_only": True})
        if d.get("audio"):
            cmd += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
        cmd += ["-map_metadata", "-1", "-movflags", "+faststart", str(out)]
        what = ", ".join(x for x in [
            f"{d.get('width')}x{d.get('height')}",
            "HDR→SDR" if d.get("hdr") else "",
            "VFR→CFR" if d.get("vfr") else "",
            f"rotated {d['rotation']}°" if d.get("rotation") else "",
            "no audio!" if not d.get("audio") else "",
        ] if x)
        print(f"[ingest] {src.name} -> {clip}.mp4  ({d['duration']:.1f}s, {what})", file=sys.stderr)
        run(cmd, quiet=True)

        out_info = probe(out)
        ovs = video_stream(out_info) or {}
        entry = {**d, "clip": clip, "source_path": str(src), "size": stat.st_size,
                 "proxy_width": ovs.get("width"), "proxy_height": ovs.get("height"),
                 "proxy_duration": round(duration_of(out_info), 3), "fps": args.fps}
        manifest["clips"] = [c for c in manifest["clips"] if c["clip"] != clip] + [entry]
        write_json(manifest_path, manifest)

    manifest["clips"].sort(key=lambda c: c["clip"])
    write_json(manifest_path, manifest)
    for c in manifest["clips"]:
        print(f"{c['clip']}\t{c['proxy_duration']:.1f}s\t{c['proxy_width']}x{c['proxy_height']}\t{c['original']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
