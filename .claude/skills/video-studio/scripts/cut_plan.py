# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy>=1.26"]
# ///
"""Propose the tightening cuts for every clip: pauses, hesitations, stutters, retakes.

    uv run tools/cut_plan.py projects/my-reel                 # reel pacing (tight)
    uv run tools/cut_plan.py projects/my-reel --mode youtube  # natural pacing
    uv run tools/cut_plan.py projects/my-reel --apply P2,P5   # also apply approved proposals

Writes projects/<p>/cuts.json (machine) and projects/<p>/cuts.md (the list to review with
the member, in Hebrew). cuts.json "segments" can be pasted straight into plan.json.

What is cut automatically (safe):  pauses, head/tail silence, hesitation sounds (אה/אממ)
What is only PROPOSED (needs a yes): retakes (keeps the LAST take), repeated words ("זה זה" is a
                                     stutter, "מלא מלא" is emphasis), discourse fillers
                                     (כאילו/בעצם/יעני) — they carry meaning in other contexts.

Pauses come from the AUDIO, not the transcript: the Hebrew model's word timestamps are
contiguous (no gaps) and start ~0.1 s early, so gaps between words don't show the silences.
Every cut edge is moved to the quietest 10 ms nearby and keeps are rounded OUTWARD to
whole frames, so no word is clipped and audio and video stay the same length.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _studio import ffmpeg, read_json, utf8_console, write_json  # noqa: E402

MODES = {
    #          min pause   keep after word  keep before word  head   tail
    "reel":    dict(gap=0.30, post=0.10, pre=0.08, head=0.12, tail=0.25),
    "youtube": dict(gap=0.55, post=0.16, pre=0.10, head=0.20, tail=0.35),
}
NIQQUD = re.compile(r"[֑-ׇ]")
FINALS = str.maketrans("ךםןףץ", "כמנפצ")
# Hesitation SOUNDS only. Matched on the raw letters (final forms kept) with a doubled mem for
# the humming forms, so real words are never hit: "אם" (if), "הם" (they), "אמ", "המ" stay.
HESITATION = re.compile(r"^(א+ה+|א+מ{2,}ם?|א+מ+ם|ה+מ{2,}ם?|ה+מ+ם|מ{2,}ם?|מ+ם|ah+|uh+|um+|umm+|erm|hmm+)$")


def raw(s: str) -> str:
    return NIQQUD.sub("", s).strip(" ,.?!:;\"'׳״-–—()").lower()
DISCOURSE = {"כאילו", "בעצם", "יעני", "נו", "בקיצור", "כזה", "כזאת", "סתם", "תכלס", "אוקיי", "רגע", "וואלה"}


def norm(s: str) -> str:
    return NIQQUD.sub("", s).translate(FINALS).strip(" ,.?!:;\"'׳״-–—()").lower()


def envelope(clip: Path) -> tuple[np.ndarray, float]:
    """10 ms RMS in dB of a 16 kHz mono decode, and the noise floor (10th percentile)."""
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "a.wav"
        subprocess.run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(clip),
                        "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav)],
                       check=True)
        with wave.open(str(wav)) as f:
            sr = f.getframerate()
            x = np.frombuffer(f.readframes(f.getnframes()), np.int16).astype(np.float32) / 32768
    hop = sr // 100
    n = len(x) // hop
    frames = x[: n * hop].reshape(n, hop)
    db = 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-9)
    return db, float(np.percentile(db, 10))


def silent_runs(db: np.ndarray, floor: float, min_len: float) -> list[tuple[float, float]]:
    """Stretches quieter than floor+8 dB for at least min_len seconds."""
    quiet = db < floor + 8
    runs, start = [], None
    for i, q in enumerate(np.append(quiet, False)):
        if q and start is None:
            start = i
        elif not q and start is not None:
            if (i - start) / 100 >= min_len:
                runs.append((start / 100, i / 100))
            start = None
    return runs


def snap(t: float, db: np.ndarray, win: float = 0.08) -> float:
    i0, i1 = max(0, int((t - win) * 100)), min(len(db) - 1, int((t + win) * 100))
    return (i0 + int(np.argmin(db[i0:i1 + 1]))) / 100 if i1 > i0 else t


def phrases(words: list[dict]) -> list[dict]:
    out, s = [], 0
    for i in range(1, len(words) + 1):
        if i == len(words) or re.search(r"[.?!]$", words[i - 1]["text"]) or \
                words[i]["start"] - words[i - 1]["end"] >= 0.5:
            toks = [norm(w["text"]) for w in words[s:i] if not HESITATION.match(raw(w["text"]))]
            out.append({"start": words[s]["start"], "end": words[i - 1]["end"], "i0": s, "i1": i,
                        "norm": " ".join(t for t in toks if t),
                        "text": " ".join(w["text"] for w in words[s:i])})
            s = i
    return out


def trigrams(t: str) -> set[str]:
    t = f"  {t} "
    return {t[k:k + 3] for k in range(len(t) - 2)}


def plan_clip(clip: str, words: list[dict], duration: float, db: np.ndarray, floor: float,
              p: dict, fps: int, approved: set[str], pid_start: int) -> dict:
    remove: list[tuple[float, float, str]] = []
    proposals: list[dict] = []

    # 1) pauses, found in the audio
    for s, e in silent_runs(db, floor, p["gap"]):
        if s <= 0.01:
            remove.append((0.0, max(0.0, e - p["head"]), "silence at start"))
        elif e >= duration - 0.02:
            remove.append((s + p["tail"], duration, "silence at end"))
        else:
            remove.append((s + p["post"], e - p["pre"], f"pause {e - s:.1f}s"))

    def context(i0: int, i1: int) -> str:
        before = " ".join(x["text"] for x in words[max(0, i0 - 5):i0])
        cut = " ".join(x["text"] for x in words[i0:i1])
        after = " ".join(x["text"] for x in words[i1:i1 + 5])
        return f"{before} [[{cut}]] {after}".strip()

    # 2) hesitation sounds are cut automatically; a repeated word is only PROPOSED, because
    #    emphasis ("מלא מלא טוקנים") looks exactly like a stutter ("זה זה")
    pid = pid_start
    for i, w in enumerate(words):
        n = norm(w["text"])
        if HESITATION.match(raw(w["text"])):
            remove.append((w["start"], w["end"], f"hesitation '{w['text']}'"))
        if i + 1 < len(words) and len(n) > 1 and n == norm(words[i + 1]["text"]) \
                and words[i + 1]["start"] - w["end"] < 0.5:
            pid += 1
            proposals.append({"id": f"P{pid}", "type": "repeat", "clip": clip,
                              "start": w["start"], "end": words[i + 1]["start"], "context": context(i, i + 1)})

    # 3) discourse fillers — only when isolated by pauses on both sides (proposal)
    for i, w in enumerate(words):
        if norm(w["text"]) in DISCOURSE:
            s_i, e_i = int(w["start"] * 100), int(w["end"] * 100)
            before = db[max(0, s_i - 15):s_i]
            after = db[e_i:e_i + 15]
            if len(before) and len(after) and before.min() < floor + 8 and after.min() < floor + 8:
                pid += 1
                proposals.append({"id": f"P{pid}", "type": "filler", "clip": clip,
                                  "start": w["start"], "end": w["end"], "context": context(i, i + 1)})

    # 4) retakes: a later phrase that restarts an earlier one -> drop the earlier take
    ph = phrases(words)
    for a in range(len(ph)):
        for b in range(a + 1, min(len(ph), a + 8)):
            if ph[b]["start"] - ph[a]["end"] > 60 or not ph[a]["norm"] or not ph[b]["norm"]:
                continue
            A, B = trigrams(ph[a]["norm"]), trigrams(ph[b]["norm"])
            sim = len(A & B) / max(1.0, (len(A) * len(B)) ** 0.5)
            same_open = ph[a]["norm"].split()[:2] == ph[b]["norm"].split()[:2] and len(ph[a]["norm"].split()) >= 2
            if sim >= 0.55 or (same_open and sim >= 0.35):
                pid += 1
                proposals.append({"id": f"P{pid}", "type": "retake", "clip": clip, "similarity": round(sim, 2),
                                  "start": ph[a]["start"], "end": ph[b]["start"],
                                  "drop": ph[a]["text"], "keep": ph[b]["text"]})
                break

    for pr in proposals:
        if pr["id"] in approved:
            remove.append((pr["start"], pr["end"], f"approved {pr['id']} ({pr['type']})"))

    # 5) merge, snap to quiet points, keep = complement, frame-snap outward, drop slivers
    rem = sorted((max(0.0, s), min(duration, e), r) for s, e, r in remove if e - s >= 0.08)
    merged: list[list] = []
    for s, e, r in rem:
        if merged and s <= merged[-1][1] + 0.02:
            merged[-1][1] = max(merged[-1][1], e)
            merged[-1][2] += " + " + r
        else:
            merged.append([s, e, r])
    keeps, t = [], 0.0
    for s, e, _ in merged:
        s2 = 0.0 if s <= 0.01 else snap(s, db)
        e2 = duration if e >= duration - 0.01 else snap(e, db)
        if s2 > t:
            keeps.append([t, s2])
        t = max(t, e2)
    if t < duration:
        keeps.append([t, duration])
    fl = lambda v: np.floor(v * fps + 1e-6) / fps  # noqa: E731
    ce = lambda v: np.ceil(v * fps - 1e-6) / fps  # noqa: E731
    keeps = [[round(float(fl(s)), 3), round(float(min(duration, ce(e))), 3)] for s, e in keeps]
    # rounding outward can make two keeps touch/overlap when the cut between them was
    # shorter than ~2 frames: such a cut is inaudible anyway — merge instead of overlapping
    joined: list[list[float]] = []
    for k in keeps:
        if joined and k[0] <= joined[-1][1] + 1.5 / fps:
            joined[-1][1] = max(joined[-1][1], k[1])
        else:
            joined.append(k)
    keeps = [k for k in joined if k[1] - k[0] >= 0.4]
    # report only cuts that really happen (a keep can swallow a sub-frame cut)
    real = [[round(s, 3), round(e, 3), r] for s, e, r in merged
            if not any(k[0] <= s + 0.02 and k[1] >= e - 0.02 for k in keeps)]
    return {"duration": duration, "keeps": keeps,
            "removed": real,
            "proposals": proposals, "pid": pid}


def main() -> int:
    utf8_console()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", type=Path)
    ap.add_argument("--mode", choices=list(MODES), default="reel")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--clips", default=None, help="comma list; default: every transcribed clip")
    ap.add_argument("--apply", default="", help="proposal ids the member approved, e.g. P2,P5")
    args = ap.parse_args()

    p = MODES[args.mode]
    approved = {x.strip().upper() for x in args.apply.split(",") if x.strip()}
    files = sorted((args.project / "transcripts").glob("*.words.json"))
    if args.clips:
        wanted = set(args.clips.split(","))
        files = [f for f in files if f.name.split(".")[0] in wanted]
    if not files:
        raise SystemExit("[cuts] no transcripts — run transcribe first")

    result = {"mode": args.mode, "fps": args.fps, "clips": {}, "segments": []}
    pid = 0
    src_total = out_total = 0.0
    for f in files:
        clip = f.name.split(".")[0]
        data = read_json(f)
        words = [w for w in data["words"] if w.get("text", "").strip()]
        media = args.project / "media" / f"{clip}.mp4"
        db, floor = envelope(media)
        duration = min(float(data.get("duration") or len(db) / 100), len(db) / 100)
        r = plan_clip(clip, words, duration, db, floor, p, args.fps, approved, pid)
        pid = r.pop("pid")
        result["clips"][clip] = r
        result["segments"] += [{"clip": clip, "from": s, "to": e} for s, e in r["keeps"]]
        src_total += duration
        out_total += sum(e - s for s, e in r["keeps"])
    result["summary"] = {"source_s": round(src_total, 2), "output_s": round(out_total, 2),
                         "saved_s": round(src_total - out_total, 2)}
    write_json(args.project / "cuts.json", result)

    md = [f"# הצעת חיתוך — {args.project.name} ({args.mode})", "",
          f"לפני: {src_total:.1f} שנ' · אחרי חיתוכים אוטומטיים: {out_total:.1f} שנ' "
          f"(נחסכו {src_total - out_total:.1f} שנ')", "",
          "## חתכתי אוטומטית (שקטים והיסוסים)"]
    for clip, r in result["clips"].items():
        for s, e, why in r["removed"]:
            md.append(f"- {clip} {s:.2f}–{e:.2f} ({e - s:.1f} שנ') — {why}")
    md += ["", "## מחכה לאישור שלך (לא נחתך עדיין)"]
    any_prop = False
    for clip, r in result["clips"].items():
        for pr in r["proposals"]:
            any_prop = True
            status = " ✅ אושר" if pr["id"] in approved else ""
            if pr["type"] == "retake":
                md.append(f"- **{pr['id']}** טייק כפול ב-{clip} ({pr['start']:.1f}–{pr['end']:.1f}): "
                          f"להוריד \"{pr['drop']}\" ולהשאיר \"{pr['keep']}\"{status}")
            elif pr["type"] == "repeat":
                md.append(f"- **{pr['id']}** מילה כפולה ב-{clip} ({pr['start']:.2f}) — גמגום או הדגשה? "
                          f"{pr['context']}{status}")
            else:
                md.append(f"- **{pr['id']}** מילת מילוי ב-{clip} ({pr['start']:.2f}): {pr['context']}{status}")
    if not any_prop:
        md.append("- אין — הדיבור נקי.")
    (args.project / "cuts.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"[cuts] {src_total:.1f}s -> {out_total:.1f}s; {pid} proposals. "
          f"Review: {args.project / 'cuts.md'}", file=sys.stderr)
    print(args.project / "cuts.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
