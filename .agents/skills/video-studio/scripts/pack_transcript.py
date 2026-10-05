# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Pack word-level transcripts into one readable file — the agent's main view of the footage.

    uv run tools/pack_transcript.py projects/my-reel

Reads   projects/<p>/transcripts/*.words.json   (written by transcribe.py)
Writes  projects/<p>/transcript.md

Each line is a phrase with its source time range. Lines break on a pause >= 0.5 s,
at the end of a sentence, or at a comma once a line passes ~14 words.
Marks that help editing decisions:
    ⏸ 1.4s        a pause — a clean cut candidate (>= 0.4 s is safe to cut)
    ~אה~          a hesitation word (safe to remove)
    (כאילו)       a soft filler — remove only if the sentence still flows
    ↺ L12         this phrase re-starts line 12 — probably a retake; keep the LATER take
Reading this file costs ~1/10 of the raw JSON, and word-accurate times stay one
lookup away in the .words.json files.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _studio import read_json, utf8_console  # noqa: E402

HESITATIONS = {"אה", "אהה", "אההה", "אמ", "אממ", "אםם", "אהם", "ממ", "מממ", "הממ", "אמממ", "uh", "um", "umm", "hmm"}
SOFT_FILLERS = {"כאילו", "יעני", "נו", "בקיצור", "סתם"}
PUNCT = re.compile(r"[\"'“”„.,!?;:־\-–—()\[\]]")


def norm(word: str) -> str:
    return PUNCT.sub("", word).strip().lower()


def phrases(words: list[dict], gap: float, max_words: int = 14) -> list[list[dict]]:
    """Break on a pause, after sentence-ending punctuation, or at a comma/short pause
    once the line gets long — so every line is a usable cut unit."""
    out: list[list[dict]] = []
    cur: list[dict] = []
    for w in words:
        if cur:
            pause = w["start"] - cur[-1]["end"]
            prev = cur[-1]["text"].rstrip()
            sentence_end = prev.endswith((".", "?", "!"))
            soft_break = len(cur) >= max_words and (prev.endswith(",") or pause >= 0.2)
            if pause >= gap or sentence_end or soft_break or len(cur) >= max_words * 2:
                out.append(cur)
                cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    return out


def join_words(ph: list[dict]) -> str:
    text = ""
    for w in ph:
        t = fmt_word(w)
        # "ה" + "-AI" -> "ה-AI": a leading hyphen/maqaf glues to the previous word
        text += t if (not text or t.startswith(("-", "־"))) else " " + t
    return text


def fmt_word(w: dict) -> str:
    n = norm(w["text"])
    if n in HESITATIONS:
        return f"~{w['text']}~"
    if n in SOFT_FILLERS:
        return f"({w['text']})"
    return w["text"]


def main() -> int:
    utf8_console()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", type=Path)
    ap.add_argument("--gap", type=float, default=0.5, help="pause (s) that starts a new phrase")
    args = ap.parse_args()

    files = sorted((args.project / "transcripts").glob("*.words.json"))
    if not files:
        sys.exit(f"[pack] no transcripts in {args.project / 'transcripts'} — run transcribe.py first")

    lines_out = [f"# Transcript — {args.project.name}", "",
                 "Times are SOURCE seconds per clip. ⏸ = pause (cut candidate), ~x~ = hesitation, "
                 "(x) = soft filler, ↺ Ln = restarts line n (retake — keep the later one).", ""]
    line_no = 0
    total_pause = 0.0
    for f in files:
        data = read_json(f)
        words = [w for w in data["words"] if w.get("text", "").strip()]
        clip = f.name.replace(".words.json", "")
        lines_out.append(f"## {clip}  ({data.get('duration', 0):.1f}s, {len(words)} words, "
                         f"engine: {data.get('engine', '?')})")
        seen: list[tuple[int, list[str]]] = []
        prev_end = 0.0
        for ph in phrases(words, args.gap):
            pause = ph[0]["start"] - prev_end
            if pause >= 0.4:
                lines_out.append(f"      ⏸ {pause:.1f}s")
                total_pause += pause
            line_no += 1
            key = [norm(w["text"]) for w in ph[:4]]
            retake = ""
            if len(key) >= 3:
                for n, k in reversed(seen[-8:]):
                    if k[:3] == key[:3]:
                        retake = f"   ↺ L{n}"
                        break
            seen.append((line_no, key))
            text = join_words(ph)
            lines_out.append(f"L{line_no:<3} [{ph[0]['start']:06.2f}-{ph[-1]['end']:06.2f}] {text}{retake}")
            prev_end = ph[-1]["end"]
        tail = data.get("duration", prev_end) - prev_end
        if tail >= 0.4:
            lines_out.append(f"      ⏸ {tail:.1f}s (end)")
        lines_out.append("")

    if total_pause >= 0.4:
        lines_out.append(f"Pauses visible in the word timing: {total_pause:.1f}s.")
    lines_out.append("Note: the local Hebrew model stretches words over silences, so pauses are often invisible "
                     "here — `studio cuts` finds the real pauses in the audio.")
    out = args.project / "transcript.md"
    out.write_text("\n".join(lines_out), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
