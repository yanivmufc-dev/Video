# /// script
# requires-python = ">=3.10,<3.14"
# dependencies = ["mediapipe==1.0.0", "numpy>=1.26"]
# ///
"""Find the speaker's face in every clip ("framing"), and for footage wider than the output
(landscape -> vertical) where the crop should sit.

    uv run tools/reframe.py projects/my-reel                 # analyze every clip -> reframe.json
    uv run tools/reframe.py projects/my-reel --apply         # also write `focus` into plan.json segments

Framing (every clip): where hair, brows and chin are, so build_edit.py can place captions
below the chin by default and WARN when a title/emoji/banner would cover the face.

Writes projects/<p>/reframe.json: per clip, a list of time ranges with a static `focus`
[x, y] (0–1, the value plan.json segments use with fit "cover"). The crop only moves when the
face really moves (> 12% of the crop width) — a static crop per shot reads as a cut, not a
camera pan, and never zooms on the speaker.

Warnings it gives: two faces that can't both fit (use fit "blur" for that part), no face found
(screen recording? keep fit "contain"/"blur"), face too close to the top edge.
mediapipe is pinned to 1.0.0 (1.0.1 crashes on macOS). No Intel-Mac build exists — there,
use fit "blur" or set focus by eye from a contact sheet.
"""
from __future__ import annotations

import argparse
import statistics
import subprocess
import sys
import urllib.request
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _studio import duration_of, ffmpeg, probe, read_json, utf8_console, video_stream, write_json  # noqa: E402

MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_full_range/"
             "float16/latest/blaze_face_full_range.tflite")


def model_path() -> Path:
    import os
    base = Path(os.environ.get("STUDIO_WORKSPACE", Path.home() / "VideoStudio")) / ".cache" / "models"
    base.mkdir(parents=True, exist_ok=True)
    p = base / "blaze_face_full_range.tflite"
    if not p.exists():
        urllib.request.urlretrieve(MODEL_URL, p)
    return p


def faces(clip: Path, fps: float) -> tuple[list[dict], int, int, float]:
    import mediapipe as mp
    info = probe(clip)
    vs = video_stream(info) or {}
    W, H = int(vs["width"]), int(vs["height"])
    SW = 640
    SH = int(round(H * SW / W / 2) * 2)
    k = W / SW
    proc = subprocess.Popen([ffmpeg(), "-v", "error", "-i", str(clip), "-vf", f"fps={fps},scale={SW}:{SH}",
                             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    opts = mp.tasks.vision.FaceDetectorOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path())),
        running_mode=mp.tasks.vision.RunningMode.VIDEO, min_detection_confidence=0.5)
    out = []
    with mp.tasks.vision.FaceDetector.create_from_options(opts) as det:
        i = 0
        while True:
            buf = proc.stdout.read(SW * SH * 3)  # type: ignore[union-attr]
            if len(buf) < SW * SH * 3:
                break
            img = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.frombuffer(buf, np.uint8).reshape(SH, SW, 3))
            t = i / fps
            res = det.detect_for_video(img, int(t * 1000))
            dets = sorted(res.detections, key=lambda d: -d.bounding_box.width * d.bounding_box.height)
            if dets:
                b = dets[0].bounding_box
                second = dets[1].bounding_box if len(dets) > 1 and \
                    dets[1].bounding_box.width > 0.6 * b.width else None
                out.append({"t": t, "cx": (b.origin_x + b.width / 2) * k, "cy": (b.origin_y + b.height / 2) * k,
                            "top": b.origin_y * k, "bot": (b.origin_y + b.height) * k,
                            "left": b.origin_x * k, "right": (b.origin_x + b.width) * k, "fw": b.width * k,
                            "cx2": (second.origin_x + second.width / 2) * k if second else None})
            else:
                out.append({"t": t, "cx": None})
            i += 1
    proc.wait()
    return out, W, H, duration_of(info)


def framing(samples: list[dict], W: int, H: int) -> dict | None:
    """Where the head sits in the SOURCE frame (0–1). The detector box runs roughly from the
    eyebrows to the chin; hair adds ~35% of the box height above it."""
    found = [s for s in samples if s["cx"] is not None]
    if not found:
        return None
    med = lambda key: statistics.median(s[key] for s in found)  # noqa: E731
    top, bot, left, right = med("top"), med("bot"), med("left"), med("right")
    h = bot - top
    return {"hair": round(max(0.0, (top - 0.35 * h) / H), 3), "brow": round(top / H, 3),
            "chin": round(min(1.0, bot / H), 3), "left": round(left / W, 3), "right": round(right / W, 3),
            "cx": round(med("cx") / W, 3), "found": round(len(found) / max(1, len(samples)), 2)}


def plan_clip(samples: list[dict], W: int, H: int, dur: float, out_w: int, out_h: int) -> dict:
    scale = max(out_w / W, out_h / H)
    rw, rh = W * scale, H * scale
    crop_w_src = out_w / scale  # visible width in source pixels
    warnings = []
    xs = [s["cx"] for s in samples]
    misses = sum(1 for x in xs if x is None)
    if misses == len(xs):
        return {"ranges": [{"from": 0.0, "to": round(dur, 3), "focus": [0.5, 0.5]}],
                "warnings": ["no face found — screen recording or wide shot? use fit 'contain' or 'blur'"]}
    last = next(x for x in xs if x is not None)
    filled = []
    for x in xs:
        last = x if x is not None else last
        filled.append(last)
    med = [statistics.median(filled[max(0, j - 2): j + 3]) for j in range(len(filled))]
    cam, path = med[0], []
    for x in med:
        if abs(x - cam) > 0.12 * crop_w_src:
            cam = x
        path.append(cam)
    cys = [s["cy"] for s in samples if s["cx"] is not None]
    cy = statistics.median(cys)

    def focus_for(cx: float) -> list[float]:
        fx = 0.5 if rw <= out_w else (out_w / 2 - cx * scale) / (out_w - rw)
        fy = 0.5 if rh <= out_h else (out_h * 0.4 - cy * scale) / (out_h - rh)  # face ~40% from top
        return [round(min(1.0, max(0.0, fx)), 3), round(min(1.0, max(0.0, fy)), 3)]

    ranges: list[dict] = []
    for s, x in zip(samples, path):
        f = focus_for(x)
        if not ranges or ranges[-1]["focus"] != f:
            ranges.append({"from": round(s["t"], 3), "focus": f})
    for j, r in enumerate(ranges):
        r["to"] = ranges[j + 1]["from"] if j + 1 < len(ranges) else round(dur, 3)
    two = sum(1 for s in samples if s.get("cx2") is not None and abs(s["cx2"] - s["cx"]) > 0.8 * crop_w_src)
    if two > 0.2 * len(samples):
        warnings.append("two people far apart for much of the clip — they can't both fit a vertical crop: "
                        "use fit 'blur' there, or alternate focus per speaker turn")
    if misses > 0.3 * len(samples):
        warnings.append(f"face missing in {misses}/{len(samples)} samples — check a contact sheet")
    if any(s["cx"] is not None and s["top"] < 0.04 * H for s in samples):
        warnings.append("the face touches the top edge in the source — keep zoom at 1.0 here")
    return {"ranges": ranges, "warnings": warnings}


def main() -> int:
    utf8_console()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", type=Path)
    ap.add_argument("--width", type=int, default=None, help="output width (default: plan.json format or 1080)")
    ap.add_argument("--height", type=int, default=None)
    ap.add_argument("--fps", type=float, default=2.0, help="face samples per second")
    ap.add_argument("--apply", action="store_true", help="write focus into plan.json segments that have none")
    args = ap.parse_args()

    plan_path = args.project / "plan.json"
    plan = read_json(plan_path) if plan_path.exists() else {}
    fmt = plan.get("format", {})
    out_w = args.width or int(fmt.get("width", 1080))
    out_h = args.height or int(fmt.get("height", 1920))
    result = {"output": [out_w, out_h], "clips": {}}
    for clip in sorted((args.project / "media").glob("clip*.mp4")):
        vs = video_stream(probe(clip)) or {}
        W, H = int(vs.get("width", 0)), int(vs.get("height", 0))
        wider = W * out_h > H * out_w * 1.02
        print(f"[reframe] {clip.stem}: {W}x{H} -> {out_w}x{out_h}, finding the face…", file=sys.stderr)
        samples, W, H, dur = faces(clip, args.fps if wider else 1.0)
        info = plan_clip(samples, W, H, dur, out_w, out_h) if wider else {"warnings": []}
        info["framing"] = framing(samples, W, H)
        if info["framing"] is None and not wider:
            info["warnings"].append("no face found — captions/overlays can't be checked against the face")
        result["clips"][clip.stem] = info
        fr = info["framing"]
        if fr:
            print(f"[reframe] {clip.stem}: head from y {fr['hair']:.2f} (hair) to {fr['chin']:.2f} (chin), "
                  f"x {fr['left']:.2f}–{fr['right']:.2f}", file=sys.stderr)
        for w in info["warnings"]:
            print(f"[reframe] {clip.stem}: WARNING {w}", file=sys.stderr)
    write_json(args.project / "reframe.json", result)

    if args.apply and plan.get("segments"):
        changed = 0
        for seg in plan["segments"]:
            info = result["clips"].get(seg["clip"])
            if not info or "ranges" not in info or seg.get("focus") or seg.get("fit") in ("blur", "contain"):
                continue
            mid = (float(seg["from"]) + float(seg["to"])) / 2
            rng = next((r for r in info["ranges"] if r["from"] <= mid < r["to"]), info["ranges"][-1])
            seg["focus"] = rng["focus"]
            changed += 1
        write_json(plan_path, plan)
        print(f"[reframe] focus written into {changed} segment(s) of plan.json", file=sys.stderr)
    print(args.project / "reframe.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
