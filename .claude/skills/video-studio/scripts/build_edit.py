# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Compile an edit plan (plan.json, in human terms) into the timeline Remotion renders.

    uv run tools/build_edit.py projects/my-reel            # writes edit.json + registers it in Remotion
    uv run tools/build_edit.py projects/my-reel --check    # validate + print the anchor table only

Why this exists: every effect must land ON its spoken word, and captions must follow
the cut. Doing that math by hand in each session is where timing bugs come from.
Here it's done once, deterministically:
  * segments (source in/out per clip)  -> output frames, with trim offsets
  * words of the kept segments        -> caption pages (never crossing a cut)
  * anchors {"word": "חינם", "n": 2}   -> the frame where that word is spoken in the FINAL cut
  * "sfx": "pop" on any overlay        -> a sound cue on the overlay's first frame

Input  projects/<p>/plan.json, projects/<p>/transcripts/<clip>.words.json, projects/<p>/media/<clip>.mp4
Output projects/<p>/edit.json  and  remotion/src/projects/<p>.json (+ regenerated index.ts)
       media is hard-linked (copied if linking fails) into remotion/public/p/<p>/
See references/edit-plan.md for the full plan.json format.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _studio import ffmpeg, read_json, utf8_console, write_json  # noqa: E402

PUNCT = re.compile(r"[\"'“”„.,!?;:()\[\]…]")
HEB_PREFIXES = ("ו", "ה", "ב", "ל", "ש", "כ", "מ", "וה", "וב", "ול", "וש", "שה", "וכ", "ומ", "כש", "לכ", "מה", "שב", "של")
SENTENCE_END = (".", "?", "!", ":", "…")

# Transitions INTO a segment. OVERLAP ones crossfade two clips (the edit gets shorter by
# their duration); CUT ones happen on the cut itself and never move the timeline.
SCENE_KINDS = ["kinetic", "statement", "number", "list", "compare", "steps", "icons", "media", "chat",
               "terminal", "device", "chart"]
OVERLAP_TRANSITIONS = {"fade", "slide", "wipe", "flip", "clock", "iris", "push"}
CUT_TRANSITIONS = {"flash", "whip", "zoom", "blur", "glitch", "shake", "lightleak"}
CUT_OVERLAY = {"flash": "flash", "lightleak": "lightleak", "glitch": "glitch", "zoom": "flash"}
# Default sound per transition (first one found in library/sfx wins). "none" = silent.
TRANSITION_SFX = {
    "fade": [], "slide": ["whoosh"], "wipe": ["whoosh-short", "whoosh"], "flip": ["whoosh"],
    "clock": ["whoosh-short", "tick"], "iris": ["pop"], "push": ["whoosh", "boom"],
    "flash": ["shutter", "whoosh-short"], "whip": ["whip", "whoosh-short"], "zoom": ["whoosh"],
    "blur": ["whoosh"], "glitch": ["glitch"], "shake": ["boom"], "lightleak": ["whoosh"],
}
DEFAULT_TRANSITION_DUR = {"fade": 0.5, "slide": 0.45, "wipe": 0.45, "flip": 0.6, "clock": 0.6, "iris": 0.5,
                          "push": 0.4, "flash": 0.3, "whip": 0.35, "zoom": 0.4, "blur": 0.4,
                          "glitch": 0.3, "shake": 0.35, "lightleak": 0.9}


class PlanError(Exception):
    pass


def norm(text: str) -> str:
    return PUNCT.sub("", text).replace("־", "-").strip().lower()


def word_matches(token: str, target: str) -> bool:
    """Hebrew-aware match: 'בחינם' matches 'חינם', 'והקובץ' matches 'קובץ'. A merged name
    token ('Claude Code') matches its full text or its first word."""
    t, g = norm(token), norm(target)
    if not g:
        return False
    if t == g or t.split(" ")[0] == g:
        return True
    return any(t == p + g or t.split(" ")[0] == p + g for p in HEB_PREFIXES)


# ------------------------------------------------------------------ segments

def load_words(project: Path, clip: str) -> list[dict]:
    f = project / "transcripts" / f"{clip}.words.json"
    if not f.exists():
        return []
    return [w for w in read_json(f)["words"] if w.get("text", "").strip()]


def build_segments(plan: dict, project: Path, fps: int) -> list[dict]:
    sources = {}
    manifest = project / "media" / "sources.json"
    if manifest.exists():
        sources = {c["clip"]: c for c in read_json(manifest).get("clips", [])}
    segs = []
    out_frame = 0
    for i, s in enumerate(plan.get("segments", [])):
        clip = s["clip"]
        media = project / "media" / f"{clip}.mp4"
        if not media.exists():
            raise PlanError(f"segment {i}: media/{clip}.mp4 not found (run ingest.py first)")
        src_in = round(float(s["from"]) * fps)
        src_out = round(float(s["to"]) * fps)
        if src_out <= src_in:
            raise PlanError(f"segment {i}: 'to' ({s['to']}) must be after 'from' ({s['from']})")
        dur = src_out - src_in
        trans = None
        if i > 0 and s.get("transition"):
            t = s["transition"] if isinstance(s["transition"], dict) else {"type": s["transition"]}
            if t.get("type") in (None, "default", True):
                t = {**t, "type": plan.get("_transition") or "whip"}
            ttype = t.get("type", "fade")
            if ttype not in OVERLAP_TRANSITIONS | CUT_TRANSITIONS:
                raise PlanError(f"segment {i}: unknown transition '{ttype}'. Overlap: "
                                f"{', '.join(sorted(OVERLAP_TRANSITIONS))}; cut: {', '.join(sorted(CUT_TRANSITIONS))}")
            tdur = max(2, round(float(t.get("dur", DEFAULT_TRANSITION_DUR[ttype])) * fps))
            overlap = ttype in OVERLAP_TRANSITIONS
            if overlap:
                limit = min(dur, segs[-1]["durationInFrames"]) - 1
                if tdur > limit:
                    raise PlanError(f"segment {i}: {ttype} lasts {tdur} frames but a neighbouring segment "
                                    f"is only {limit + 1} frames long")
                out_frame -= tdur
            trans = {"type": ttype, "durationInFrames": tdur, "overlap": overlap,
                     "direction": t.get("direction", "from-left"),
                     "sfx": t.get("sfx"), "sfxGain": t.get("sfxGain")}
        src_meta = sources.get(clip, {})
        seg = {
            "index": i, "clip": clip, "src": f"p/{project.name}/{clip}.mp4",
            "from": float(s["from"]), "to": float(s["to"]),
            "startFrame": out_frame, "durationInFrames": dur, "trimBefore": src_in,
            "zoom": float(s.get("zoom", 1.0)),
            "zoomOrigin": s.get("zoomOrigin", "50% 30%"),  # top-weighted: punch-ins never crop the forehead
            "volume": float(s.get("volume", 1.0)),
            "fit": s.get("fit", "cover"),
        }
        if s.get("focus"):
            seg["focus"] = s["focus"]
        if src_meta.get("proxy_width"):
            seg["srcWidth"], seg["srcHeight"] = src_meta["proxy_width"], src_meta["proxy_height"]
        if trans:
            seg["transitionIn"] = trans
        segs.append(seg)
        out_frame += dur
    if not segs:
        raise PlanError("plan has no segments")
    return segs


def transition_effects(segs: list[dict], public: Path, fps: int, warnings: list) -> tuple[list, list]:
    """Overlays + sound cues that belong to transitions."""
    overlays, sfx = [], []
    for seg in segs:
        t = seg.get("transitionIn")
        if not t:
            continue
        cut = seg["startFrame"]  # for overlap: where the transition begins
        d = t["durationInFrames"]
        if not t["overlap"] and t["type"] in CUT_OVERLAY:
            overlays.append({"type": CUT_OVERLAY[t["type"]], "startFrame": max(0, cut - d // 2),
                             "durationInFrames": d, "z": 60, "fromTransition": True,
                             **({"peak": 0.55} if t["type"] == "zoom" else {})})
        choice = t.get("sfx")
        if choice == "none":
            continue
        names = [choice] if choice else TRANSITION_SFX.get(t["type"], [])
        path = None
        for name in names:
            try:
                path = find_sound(name, public)
                break
            except PlanError:
                continue
        if names and not path:
            warnings.append(f"no sound for transition '{t['type']}' (wanted {', '.join(names)}) — "
                            "run the effects setup step")
            continue
        if path:
            # whooshes peak ~0.1 s after they start, so start them slightly before the cut
            lead = round(0.1 * fps) if not t["overlap"] else 0
            sfx.append({"src": path, "startFrame": max(0, cut - lead),
                        "volume": float(t.get("sfxGain") or 0.6)})
    return overlays, sfx


def output_words(segs: list[dict], project: Path, fps: int, report: list | None = None) -> list[dict]:
    """Words that survive the cut, placed on the OUTPUT timeline (frames).
    Whisper stretches words over the pauses next to them, and cuts come from the audio, so a
    word is kept in the segment it overlaps MOST (not by its midpoint) as long as at least
    ~0.12 s of it survives — otherwise real spoken words vanish from the captions."""
    cache: dict[str, list[dict]] = {}
    by_clip: dict[str, list[dict]] = {}
    for seg in segs:
        by_clip.setdefault(seg["clip"], []).append(seg)
    placed: list[tuple[dict, dict]] = []
    dropped = 0
    for clip, clip_segs in by_clip.items():
        words = cache.setdefault(clip, load_words(project, clip))
        for w in words:
            best, best_ov = None, 0.0
            for seg in clip_segs:
                ov = min(w["end"], seg["to"]) - max(w["start"], seg["from"])
                if ov > best_ov:
                    best, best_ov = seg, ov
            if best is None or best_ov < min(0.12, 0.5 * max(0.01, w["end"] - w["start"])):
                dropped += 1
                continue
            placed.append((w, best))
    out = []
    for w, seg in sorted(placed, key=lambda x: (x[1]["startFrame"], x[0]["start"])):
        s = max(w["start"], seg["from"])
        e = min(w["end"], seg["to"])
        out.append({
            "text": w["text"].strip(), "seg": seg["index"],
            "startFrame": seg["startFrame"] + round(s * fps) - seg["trimBefore"],
            "endFrame": seg["startFrame"] + round(e * fps) - seg["trimBefore"],
            "srcStart": w["start"], "clip": seg["clip"],
        })
    if report is not None:
        report.append(dropped)
    # Whisper splits "ה-AI" into "ה" + "-AI"; glue them back so a caption never breaks inside.
    merged: list[dict] = []
    for w in out:
        if merged and w["text"].startswith(("-", "־")) and merged[-1]["seg"] == w["seg"]:
            merged[-1]["text"] += w["text"]
            merged[-1]["endFrame"] = w["endFrame"]
        else:
            merged.append(w)
    return merged


# ------------------------------------------------------------------ fixes + captions

def split_prefix(token: str, target: str) -> str | None:
    """'' if token == target, the Hebrew prefix if token == prefix+target, else None."""
    t, g = norm(token), norm(target)
    if t == g:
        return ""
    return next((p for p in HEB_PREFIXES if t == p + g), None)


def apply_fixes(words: list[dict], fixes: dict[str, str]) -> None:
    """ASR corrections for DISPLAY only (timing untouched). Keys may span several words:
    {"Cloud Code": "Claude Code", "קלוד": "Claude"}. A multi-word result is kept as ONE caption
    word, so a name never splits across caption pages. A Hebrew prefix is kept: 'לקלוד' -> 'ל-Claude'."""
    for wrong, right in sorted(fixes.items(), key=lambda kv: -len(kv[0].split())):
        wrong_toks = wrong.split()
        n = len(wrong_toks)
        i = 0
        while i <= len(words) - n:
            window = words[i:i + n]
            prefix = split_prefix(window[0]["text"], wrong_toks[0])
            same_seg = all(w["seg"] == window[0]["seg"] for w in window)
            if prefix is None or not same_seg or any(
                    norm(window[k]["text"]) != norm(wrong_toks[k]) for k in range(1, n)):
                i += 1
                continue
            trail = re.search(r"[.,!?;:…]+$", window[-1]["text"])
            words[i]["text"] = right
            words[i]["endFrame"] = window[-1]["endFrame"]
            del words[i + 1:i + n]
            if prefix:
                glue = "-" if re.match(r"[A-Za-z0-9]", right) else ""
                words[i]["text"] = prefix + glue + words[i]["text"]
            if trail and not words[i]["text"].endswith(trail.group(0)):
                words[i]["text"] += trail.group(0)
            i += 1


def build_pages(words: list[dict], cfg: dict, fps: int, total: int) -> list[dict]:
    max_words = int(cfg.get("maxWords", 3))
    gap_break = round(float(cfg.get("gapBreak", 0.26)) * fps)
    hold = round(float(cfg.get("hold", 0.4)) * fps)
    keywords = cfg.get("keywords", [])
    emojis = cfg.get("emojis", {})  # {"חינם": "🎁"} -> the emoji pops above that word
    pages: list[list[dict]] = []
    cur: list[dict] = []
    for w in words:
        if cur:
            prev = cur[-1]
            if (w["seg"] != prev["seg"] or len(cur) >= max_words
                    or w["startFrame"] - prev["endFrame"] >= gap_break
                    or prev["text"].endswith(SENTENCE_END + (",",))):
                pages.append(cur)
                cur = []
        cur.append(w)
    if cur:
        pages.append(cur)

    out = []
    for i, page in enumerate(pages):
        start = page[0]["startFrame"]
        end = page[-1]["endFrame"] + hold
        if i + 1 < len(pages):
            end = min(end, pages[i + 1][0]["startFrame"])
        end = max(end, start + 2)
        end = min(end, total)
        out.append({
            "startFrame": start, "endFrame": end,
            "tokens": [{"text": w["text"], "startFrame": w["startFrame"], "endFrame": w["endFrame"],
                        "keyword": any(word_matches(w["text"], k) for k in keywords),
                        **({"emoji": next(e for k, e in emojis.items() if word_matches(w["text"], k))}
                           if any(word_matches(w["text"], k) for k in emojis) else {})} for w in page],
        })
    return out


# ------------------------------------------------------------------ anchors

def resolve_at(at, words: list[dict], segs: list[dict], fps: int, label: str, table: list) -> int:
    if isinstance(at, (int, float)):
        frame = round(float(at) * fps)
        table.append((label, f"{at}s", frame, ""))
        return frame
    if not isinstance(at, dict):
        raise PlanError(f"{label}: 'at' must be seconds or an object, got {at!r}")
    offset = round(float(at.get("offset", 0)) * fps)
    if "word" in at:
        target = at["word"]
        n = int(at.get("n", 1))
        after = at.get("after")
        start_idx = 0
        if after is not None:
            after_f = round(float(after) * fps)
            start_idx = next((i for i, w in enumerate(words) if w["startFrame"] >= after_f), len(words))
        target_toks = target.split()
        hits = []
        for i in range(start_idx, len(words)):
            if len(target_toks) > 1 and norm(words[i]["text"]) == norm(target):
                hits.append(i)  # a merged name token, e.g. "Claude Code"
            elif i <= len(words) - len(target_toks) and word_matches(words[i]["text"], target_toks[0]) and all(
                    norm(words[i + k]["text"]) == norm(target_toks[k]) for k in range(1, len(target_toks))):
                hits.append(i)
        if len(hits) < n:
            near = sorted({w["text"] for w in words if norm(target_toks[0])[:2] in norm(w["text"])})[:8]
            raise PlanError(f"{label}: word '{target}' occurrence {n} not found in the final cut "
                            f"(found {len(hits)}). Similar words: {', '.join(near) or '—'}")
        w = words[hits[n - 1]]
        edge = w["endFrame"] if at.get("edge") == "end" else w["startFrame"]
        table.append((label, f"'{target}' #{n}" + (f" ({len(hits)} total)" if len(hits) > 1 else ""),
                      edge + offset, w["text"]))
        return edge + offset
    if "clip" in at and "t" in at:
        t = float(at["t"])
        for seg in segs:
            if seg["clip"] == at["clip"] and seg["from"] <= t < seg["to"]:
                frame = seg["startFrame"] + round(t * fps) - seg["trimBefore"] + offset
                table.append((label, f"{at['clip']}@{t}", frame, ""))
                return frame
        raise PlanError(f"{label}: {at['clip']}@{t}s was cut out of the edit")
    raise PlanError(f"{label}: 'at' needs a number, {{'word': ...}} or {{'clip': ..., 't': ...}}")


# ------------------------------------------------------------------ assets

def find_sound(name: str, public: Path) -> str:
    if "/" in name or "." in name:
        return name
    lib = public / "library" / "sfx"
    cands = sorted(p for p in lib.rglob("*") if p.suffix.lower() in (".mp3", ".wav", ".ogg", ".m4a"))
    for p in cands:
        if p.stem.lower() == name.lower():
            return p.relative_to(public).as_posix()
    for p in cands:
        if p.stem.lower().startswith(name.lower()):
            return p.relative_to(public).as_posix()
    avail = ", ".join(sorted({p.stem for p in cands})[:40]) or "none — run the effects stage"
    raise PlanError(f"sound '{name}' not in library/sfx. Available: {avail}")


def link_or_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        if dst.stat().st_size == src.stat().st_size and dst.stat().st_mtime >= src.stat().st_mtime:
            return
        dst.unlink()
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def stage_asset(value: str, project: Path, public: Path) -> str:
    """Overlay media: 'library/...' is already public; project-relative paths get staged."""
    if value.startswith(("http://", "https://", "library/", "p/")):
        return value
    src = (project / value).resolve()
    if not src.exists():
        raise PlanError(f"asset not found: {value} (looked in {project})")
    dst = public / "p" / project.name / "assets" / src.name
    link_or_copy(src, dst)
    return f"p/{project.name}/assets/{src.name}"


def emoji_code(emoji: str) -> str:
    """Noto/Fluent file key: lowercase hex codepoints joined by '_' (👍🏽 -> 1f44d_1f3fd)."""
    return "_".join(f"{ord(c):x}" for c in emoji)


def resolve_emoji(emoji: str, style: str, public: Path, warnings: list) -> dict:
    """Pick the local asset for an emoji: fluent (Microsoft, MIT — default), animated (Noto
    Lottie, CC BY 4.0 — needs a credit line in the caption), or flat (Noto, Apache 2.0).
    Without an asset the system emoji font is used, which looks different on Mac and Windows."""
    code = emoji_code(emoji)
    base = public / "library" / "emoji" / code
    options = {
        "animated": [("lottie", base / "noto-animated.json")],
        "fluent": [("image", base / "fluent.svg")],
        "flat": [("image", base / "noto.svg")],
    }
    style = "fluent" if style in ("3d", "fluent") else style
    order = options.get(style, []) + options["fluent"] + options["flat"] + options["animated"]
    for key, path in order:
        if path.exists():
            return {key: path.relative_to(public).as_posix()}
    warnings.append(f"emoji {emoji} has no downloaded asset — run: studio fetch emoji {emoji}"
                    + (" --style animated" if style == "animated" else ""))
    return {}


def register(remotion: Path, slug: str, edit: dict) -> None:
    pdir = remotion / "src" / "projects"
    write_json(pdir / f"{slug}.json", edit)
    entries = sorted(p.stem for p in pdir.glob("*.json"))
    lines = ["// AUTO-GENERATED by tools/build_edit.py — do not edit by hand.",
             "import type {EditData} from '../kit/types';"]
    for i, name in enumerate(entries):
        lines.append(f"import p{i} from './{name}.json';")
    lines.append("")
    lines.append("export const projects: EditData[] = [" + ", ".join(
        f"p{i} as unknown as EditData" for i in range(len(entries))) + "];")
    (pdir / "index.ts").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ styles + voice

STYLE_ALIASES = {"hormozi": "punch"}  # 1.0 names still work in older plans


def load_styles() -> dict:
    f = Path(__file__).with_name("styles.json")
    return {k: v for k, v in read_json(f).items() if not k.startswith("_")} if f.exists() else {}


def apply_style(plan: dict) -> dict:
    """Merge a style preset under the plan: anything the plan sets explicitly wins."""
    name = STYLE_ALIASES.get(plan.get("style") or "", plan.get("style"))
    if not name:
        return plan
    styles = load_styles()
    if name not in styles:
        raise PlanError(f"unknown style '{name}'. Known: {', '.join(styles)}")
    st = styles[name]
    out = dict(plan)
    out["theme"] = {**st.get("theme", {}), **plan.get("theme", {})}
    out["captions"] = {**st.get("captions", {}), **plan.get("captions", {})}
    out.setdefault("look", st.get("look"))
    out.setdefault("letterbox", st.get("letterbox", False))
    out["_sceneBg"] = st.get("sceneBg")
    out["_transition"] = st.get("transition")
    return out


def clip_levels(media: Path, fps: int) -> list[float]:
    """Loudness (dBFS) of every source frame of a clip, cached next to the clip."""
    cache = media.with_suffix(".voice.json")
    size = media.stat().st_size
    if cache.exists():
        c = read_json(cache)
        if c.get("size") == size and c.get("fps") == fps:
            return c["db"]
    sr = 48000
    proc = subprocess.run([ffmpeg(), "-hide_banner", "-nostats", "-i", str(media), "-map", "0:a:0", "-vn", "-af",
                           f"aresample={sr},asetnsamples=n={sr // fps}:p=0,astats=metadata=1:reset=1,"
                           "ametadata=print:key=lavfi.astats.Overall.RMS_level", "-f", "null", "-"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    db = []
    for m in re.finditer(r"RMS_level=(-?[\d.]+|-inf)", proc.stdout + proc.stderr):
        v = m.group(1)
        db.append(-90.0 if v == "-inf" else round(float(v), 1))
    write_json(cache, {"size": size, "fps": fps, "db": db})
    return db


def voice_track(segs: list[dict], project: Path, fps: int, total: int) -> list[float]:
    """Speech loudness per OUTPUT frame, 0–1 — for voice-reactive overlays."""
    levels = [0.0] * total
    cache: dict[str, list[float]] = {}
    for sg in segs:
        db = cache.setdefault(sg["clip"], clip_levels(project / "media" / f"{sg['clip']}.mp4", fps))
        for f in range(sg["durationInFrames"]):
            src = sg["trimBefore"] + f
            out = sg["startFrame"] + f
            if 0 <= out < total and src < len(db):
                levels[out] = max(levels[out], db[src])
    speech = sorted(v for v in levels if v > -60)
    top = speech[int(len(speech) * 0.95)] if speech else -20
    floor = top - 30
    return [round(min(1.0, max(0.0, (v - floor) / (top - floor))), 2) if v > -90 else 0.0 for v in levels]


# ------------------------------------------------------------------ sound effects mix

def premix_sfx(cues: list[dict], public: Path, slug: str, fps: int, total: int) -> list[dict]:
    """All effect sounds mixed into ONE WAV: a single audio layer renders faster, keeps Windows
    below its command-length limit (ENAMETOOLONG with many layers), and lets the mix be leveled
    as a whole. Returns the cue list Remotion plays (one entry)."""
    if not cues:
        return []
    files = sorted({c["src"] for c in cues})
    idx = {f: i for i, f in enumerate(files)}
    uses: dict[str, list[dict]] = {f: [] for f in files}
    for c in cues:
        uses[c["src"]].append(c)
    lines, labels = [], []
    for f in files:
        n = len(uses[f])
        outs = [f"s{idx[f]}_{j}" for j in range(n)]
        lines.append(f"[{idx[f]}:a]aformat=sample_rates=48000:channel_layouts=stereo,asplit={n}" +
                     "".join(f"[{o}]" for o in outs) if n > 1 else
                     f"[{idx[f]}:a]aformat=sample_rates=48000:channel_layouts=stereo[{outs[0]}]")
        for j, c in enumerate(uses[f]):
            ms = round(c["startFrame"] * 1000 / fps)
            lab = f"d{idx[f]}_{j}"
            lines.append(f"[{outs[j]}]adelay={ms}|{ms},volume={c['volume']:.3f}[{lab}]")
            labels.append(lab)
    lines.append("".join(f"[{l}]" for l in labels) +
                 f"amix=inputs={len(labels)}:normalize=0:duration=longest,apad=whole_dur={total / fps:.3f},"
                 f"atrim=0:{total / fps:.3f}[out]")
    out = public / "p" / slug / "sfx_mix.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    script = out.with_suffix(".filter.txt")
    script.write_text(";\n".join(lines), encoding="utf-8")
    cmd = [ffmpeg(), "-hide_banner", "-loglevel", "error", "-y"]
    for f in files:
        cmd += ["-i", str(public / f) if not f.startswith("http") else f]
    tail = ["-map", "[out]", "-ar", "48000", "-c:a", "pcm_s16le", str(out)]
    r = subprocess.run(cmd + ["-/filter_complex", str(script)] + tail,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 and "filter_complex" in r.stderr:  # an older ffmpeg (before 7)
        r = subprocess.run(cmd + ["-filter_complex_script", str(script)] + tail,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise PlanError(f"could not mix the sound effects: {r.stderr[-300:]}")
    script.unlink(missing_ok=True)
    return [{"src": out.relative_to(public).as_posix(), "startFrame": 0, "volume": 1.0, "cues": len(cues)}]


# ------------------------------------------------------------------ scenes

def pip_segments(segs: list[dict], start: int, dur: int) -> list[dict]:
    """The speaker's picture during a scene window, as small pieces relative to the scene."""
    out = []
    for sg in segs:
        s0 = max(sg["startFrame"], start)
        s1 = min(sg["startFrame"] + sg["durationInFrames"], start + dur)
        if s1 > s0:
            out.append({"src": sg["src"], "startFrame": s0 - start, "durationInFrames": s1 - s0,
                        "trimBefore": sg["trimBefore"] + (s0 - sg["startFrame"]),
                        "srcWidth": sg.get("srcWidth"), "srcHeight": sg.get("srcHeight")})
    return out


def hide_captions(pages: list[dict], windows: list[tuple[int, int]]) -> list[dict]:
    """Drop caption words spoken during scenes that show the words themselves (kinetic, statement)."""
    if not windows:
        return pages
    out = []
    for p in pages:
        toks = [t for t in p["tokens"] if not any(a <= t["startFrame"] < b for a, b in windows)]
        if not toks:
            continue
        start = toks[0]["startFrame"]
        end = p["endFrame"]
        for a, b in windows:
            if start < a < end:
                end = a
        out.append({**p, "tokens": toks, "startFrame": start, "endFrame": max(start + 2, end)})
    return out


# ------------------------------------------------------------------ face safety

def load_framing(project: Path) -> dict:
    f = project / "reframe.json"
    if not f.exists():
        return {}
    return {clip: info["framing"] for clip, info in read_json(f).get("clips", {}).items() if info.get("framing")}


def face_box(seg: dict, fr: dict, width: int, height: int) -> tuple[float, float, float, float] | None:
    """The head (hair..chin) of a segment's clip, in OUTPUT coordinates 0–1, after fit/focus/zoom."""
    sw, sh = seg.get("srcWidth"), seg.get("srcHeight")
    if not sw or not sh:
        return None
    fit = seg.get("fit", "cover")
    scale = (max if fit == "cover" else min)(width / sw, height / sh)
    rw, rh = sw * scale, sh * scale
    fx, fy = seg.get("focus", [0.5, 0.5])
    ox_px = (width - rw) * (fx if fit == "cover" else 0.5)
    oy_px = (height - rh) * (fy if fit == "cover" else 0.5)
    pts = [((ox_px + fr[a] * rw) / width, (oy_px + fr[b] * rh) / height)
           for a, b in (("left", "hair"), ("right", "chin"))]
    z = float(seg.get("zoom", 1.0))
    m = re.match(r"\s*([\d.]+)%\s+([\d.]+)%", str(seg.get("zoomOrigin", "50% 30%")))
    zx, zy = (float(m.group(1)) / 100, float(m.group(2)) / 100) if m else (0.5, 0.3)
    (x0, y0), (x1, y1) = [(zx + (x - zx) * z, zy + (y - zy) * z) for x, y in pts]
    return x0, y0, x1, y1


def overlay_box(ov: dict, width: int, height: int) -> tuple[float, float, float, float] | None:
    """Rough screen area an overlay occupies (0–1), from the kit's default sizes."""
    t = ov.get("type")
    num = lambda k, d: float(ov[k]) if isinstance(ov.get(k), (int, float)) else d  # noqa: E731
    x, y = num("x", 0.5), num("y", -1)
    lines = str(ov.get("text", "")).count("\n") + 1
    if t == "hook":
        y = num("y", 0.16)
        return 0.06, y, 0.94, y + 0.045 * lines + 0.01
    if t == "title":
        y = num("y", 0.4)
        return 0.07, y - 0.035 * lines, 0.93, y + 0.035 * lines
    if t == "callout":
        y = num("y", 0.3)
        return max(0, x - 0.3), y - 0.03, min(1, x + 0.3), y + 0.03
    if t == "lowerthird":
        y = num("y", 0.46)
        return 0.45, y, 0.94, y + 0.07
    if t == "cta":
        y = num("y", 0.47)
        return 0.25, y - 0.03, 0.75, y + 0.05
    if t == "list":
        y = num("y", 0.17)
        n = len(ov.get("items", []) or []) + (1 if ov.get("title") else 0)
        return 0.08, y, 0.92, y + 0.042 * max(1, n)
    if t == "counter":
        y = num("y", 0.33)
        return max(0, x - 0.25), y - 0.06, min(1, x + 0.25), y + (0.09 if ov.get("label") else 0.05)
    if t in ("emoji", "image", "sticker"):
        size = num("size", 0.2 if t == "emoji" else 0.3)
        x, y = num("x", 0.78 if t == "emoji" else 0.5), num("y", 0.3)
        hh = size * width / height / 2
        return x - size / 2, y - hh, x + size / 2, y + hh
    return None


def covers(a: tuple, face: tuple, small: bool = False) -> bool:
    """True when box a hides a meaningful part of the head. The head box includes hair width,
    so a small sticker only counts when it reaches well into it (not just grazing the hair)."""
    ix = min(a[2], face[2]) - max(a[0], face[0])
    iy = min(a[3], face[3]) - max(a[1], face[1])
    if small:
        return ix > 0.06 and iy > 0.25 * (face[3] - face[1])
    return ix > 0.02 and iy > 0.15 * (face[3] - face[1])


def faces_during(segs: list[dict], framing: dict, start: int, end: int, width: int, height: int) -> list[tuple]:
    boxes = []
    for seg in segs:
        s0, s1 = seg["startFrame"], seg["startFrame"] + seg["durationInFrames"]
        if s0 < end and s1 > start and seg["clip"] in framing:
            b = face_box(seg, framing[seg["clip"]], width, height)
            if b:
                boxes.append(b)
    return boxes


# ------------------------------------------------------------------ main

def compile_plan(project: Path, workspace: Path, check_only: bool, plan_file: Path | None = None,
                 variant: str | None = None) -> dict:
    plan = apply_style(read_json(plan_file or project / "plan.json"))
    fmt = plan.get("format", {})
    fps = int(fmt.get("fps", 30))
    width, height = int(fmt.get("width", 1080)), int(fmt.get("height", 1920))
    slug = project.name
    if not re.fullmatch(r"[a-z0-9-]+", slug):
        raise PlanError(f"project folder '{slug}' must be lowercase English letters, digits and dashes")
    remotion = workspace / "remotion"
    public = remotion / "public"

    segs = build_segments(plan, project, fps)
    total = segs[-1]["startFrame"] + segs[-1]["durationInFrames"]
    dropped: list = []
    words = output_words(segs, project, fps, dropped)
    apply_fixes(words, plan.get("fixes", {}))
    framing = load_framing(project)

    table: list = []
    warnings: list[str] = []
    hide_windows: list[tuple[int, int]] = []
    overlays, sfx = transition_effects(segs, public, fps, warnings)
    for seg in segs:
        t = seg.get("transitionIn")
        if t and t["overlap"]:
            inside = [w["text"] for w in words
                      if seg["startFrame"] <= w["startFrame"] < seg["startFrame"] + t["durationInFrames"]]
            if inside:
                warnings.append(f"'{t['type']}' into segment {seg['index']} overlaps speech "
                                f"({' '.join(inside[:6])}) — two voices at once; use a CUT transition "
                                "or move the cut into a pause")
    for i, ov in enumerate(plan.get("overlays", [])):
        label = f"overlay[{i}] {ov.get('type', '?')}"
        start = resolve_at(ov.get("at", 0), words, segs, fps, label, table)
        if "until" in ov:  # e.g. {"word": "לבד", "edge": "end"} — lasts until that word
            until = ov["until"]
            if isinstance(until, dict) and "word" in until and "edge" not in until:
                until = {**until, "edge": "end"}
            if isinstance(until, dict) and "word" in until and "after" not in until:
                until = {**until, "after": start / fps}
            end = resolve_at(until, words, segs, fps, f"{label} until", table)
            dur = end - start + round(float(ov.get("tail", 0.15)) * fps)
            if dur <= 0:
                raise PlanError(f"{label}: 'until' is before 'at'")
        else:
            dur = round(float(ov.get("dur", 1.5)) * fps)
        if start >= total:
            raise PlanError(f"{label}: starts after the end of the edit")
        dur = min(dur, total - start)
        props = {k: v for k, v in ov.items() if k not in ("at", "dur", "until", "tail", "sfx", "sfxGain", "sfxOffset")}
        for key in ("src", "image", "video"):
            if isinstance(props.get(key), str):
                props[key] = stage_asset(props[key], project, public)
        if ov.get("type") == "emoji":
            props.update(resolve_emoji(str(ov.get("emoji", "")), str(ov.get("style", "fluent")), public, warnings))
        # timed lists: items / steps / messages / lines (and compare's before/after items) —
        # each entry may carry its own "at" (+ "sfx") and appears on that word
        def timed(entries: list, what: str) -> list:
            out = []
            for j, item in enumerate(entries):
                if isinstance(item, dict) and "at" in item:
                    f = resolve_at(item["at"], words, segs, fps, f"{label} {what} {j}", table)
                    out.append({**{k: v for k, v in item.items() if k not in ("at", "sfx", "sfxGain")},
                                "startFrame": max(0, f - start)})
                    if item.get("sfx"):
                        sfx.append({"src": find_sound(item["sfx"], public), "startFrame": max(0, f),
                                    "volume": float(item.get("sfxGain", 0.5))})
                else:
                    out.append(item)
            return out
        for key in ("items", "steps", "messages", "lines", "bars"):
            if isinstance(ov.get(key), list):
                props[key] = timed(ov[key], key)
        for side in ("before", "after"):
            if isinstance(ov.get(side), dict) and isinstance(ov[side].get("items"), list):
                props[side] = {**ov[side], "items": timed(ov[side]["items"], f"{side}.items")}
        if ov.get("type") == "scene":
            kind = ov.get("kind", "statement")
            if kind not in SCENE_KINDS:
                raise PlanError(f"{label}: unknown scene kind '{kind}'. Known: {', '.join(SCENE_KINDS)}")
            if isinstance(ov.get("after"), dict) and "at" in ov["after"]:  # compare: "after" side on its word
                fa = resolve_at(ov["after"]["at"], words, segs, fps, f"{label} after", table)
                props["afterAtFrame"] = max(0, fa - start)
            if "bg" not in ov and plan.get("_sceneBg") and kind != "media":
                props["bg"] = plan["_sceneBg"]
            if kind == "kinetic":  # the words spoken during the scene, relative to its start
                kws = plan.get("captions", {}).get("keywords", []) + ov.get("keywords", [])
                props["words"] = [{"text": w["text"], "startFrame": w["startFrame"] - start,
                                   "endFrame": w["endFrame"] - start,
                                   "keyword": any(word_matches(w["text"], k) for k in kws)}
                                  for w in words if start - 2 <= w["startFrame"] < start + dur]
            if ov.get("speaker") == "pip":
                props["pipSegments"] = pip_segments(segs, start, dur)
                clip = next((sg["clip"] for sg in segs if sg["startFrame"] <= start < sg["startFrame"] + sg["durationInFrames"]), None)
                if clip in framing and "pipFocus" not in ov:
                    fr = framing[clip]  # the circle is fitted to the head: hair to chin, centered
                    props["pipFace"] = [fr["cx"], fr["hair"], fr["chin"]]
            # a scene tells its own story on screen: captions pause unless asked to stay
            hide = ov.get("hideCaptions", True)
            if hide:
                hide_windows.append((start, start + dur))
        overlays.append({**props, "startFrame": start, "durationInFrames": dur, "planIndex": i})
        scene_sfx = ov.get("sfx", "whoosh" if ov.get("type") == "scene" else None)
        if scene_sfx == "none":
            scene_sfx = None
        if scene_sfx and "sfx" not in ov:  # default entrance whoosh for scenes
            try:
                sfx.append({"src": find_sound(scene_sfx, public), "startFrame": max(0, start - round(0.1 * fps)),
                            "volume": 0.55})
            except PlanError:
                pass
        elif ov.get("sfx") and ov.get("sfx") != "none":
            sfx.append({"src": find_sound(ov["sfx"], public),
                        "startFrame": max(0, start + round(float(ov.get("sfxOffset", 0)) * fps)),
                        "volume": float(ov.get("sfxGain", 0.55 if ov.get("type") == "scene" else 0.6))})
    for i, cue in enumerate(plan.get("sfx", [])):
        start = resolve_at(cue.get("at", 0), words, segs, fps, f"sfx[{i}] {cue.get('sound')}", table)
        sfx.append({"src": find_sound(cue["sound"], public), "startFrame": max(0, start),
                    "volume": float(cue.get("gain", 0.6))})

    # --- face safety: nothing important on the face; captions under the chin by default
    scene_windows = [(o["startFrame"], o["startFrame"] + o["durationInFrames"]) for o in overlays
                     if o.get("type") == "scene"]
    for i, ov in enumerate(overlays):
        if ov.get("fromTransition") or ov.get("type") == "scene":
            continue
        s0, s1 = ov["startFrame"], ov["startFrame"] + ov["durationInFrames"]
        if any(a <= s0 and s1 <= b for a, b in scene_windows):  # the speaker is hidden then
            continue
        box = overlay_box(ov, width, height)
        if not box:
            continue
        for face in faces_during(segs, framing, ov["startFrame"], ov["startFrame"] + ov["durationInFrames"],
                                 width, height):
            if covers(box, face, small=ov["type"] in ("emoji", "image", "sticker")):
                warnings.append(f"overlays[{ov.get('planIndex', i)}] {ov['type']} (y {box[1]:.2f}–{box[3]:.2f}, x {box[0]:.2f}–{box[2]:.2f}) "
                                f"covers the face (head y {face[1]:.2f}–{face[3]:.2f}, x {face[0]:.2f}–{face[2]:.2f}) "
                                "— move it above the head, below the chin, or to the side")
                break
    cap_cfg = dict(plan.get("captions", {"enabled": True}))
    captions = None
    if cap_cfg.get("enabled", True):
        all_faces = faces_during(segs, framing, 0, total, width, height)
        if "y" not in cap_cfg and all_faces:
            chin = max(f[3] for f in all_faces)
            cap_cfg["y"] = round(min(0.74, max(0.6, chin + 0.075)), 3)
            print(f"[build] captions y={cap_cfg['y']} (just under the lowest chin, {chin:.2f})", file=sys.stderr)
            if chin + 0.075 > 0.74:
                warnings.append("the chin is very low in frame — captions at 0.74 may touch the face; "
                                "consider smaller captions or maxWords 2")
        elif "y" not in cap_cfg and not framing:
            warnings.append("no framing data — run `studio framing <name>` so captions and overlays avoid the face")
        cy = float(cap_cfg.get("y", 0.6))
        cap_box = (0.11, cy - 0.045, 0.89, cy + 0.045)
        for face in all_faces:
            mouth_zone = (face[0], face[3] - 0.35 * (face[3] - face[1]), face[2], face[3])
            if min(cap_box[3], mouth_zone[3]) - max(cap_box[1], mouth_zone[1]) > 0.01:
                warnings.append(f"captions at y {cy:.2f} sit on the mouth/chin (chin at {face[3]:.2f}) — "
                                "remove captions.y to let the build place them, or set it lower")
                break
        captions = {k: v for k, v in cap_cfg.items() if k not in ("keywords", "emojis")}
        captions["pages"] = hide_captions(build_pages(words, cap_cfg, fps, total), hide_windows)
    if dropped and dropped[0]:
        print(f"[build] {dropped[0]} transcript word(s) fall entirely inside cuts (not captioned)", file=sys.stderr)

    music = plan.get("music")
    if music and music.get("src"):
        music = {**music, "src": stage_asset(music["src"], project, public)}

    edit = {
        "id": f"{slug}--{variant}" if variant else slug,
        "fps": fps, "width": width, "height": height, "durationInFrames": total,
        "theme": plan.get("theme", {}),
        "segments": [{k: v for k, v in s.items() if k not in ("from", "to", "index", "clip")} for s in segs],
        "warnings": warnings,
        "captions": captions, "overlays": overlays,
        "sfx": sfx if check_only else premix_sfx(sorted(sfx, key=lambda c: c["startFrame"]), public,
                                                 edit_slug := (f"{slug}--{variant}" if variant else slug), fps, total),
        "sfxCues": [{"src": c["src"], "startFrame": c["startFrame"]} for c in sorted(sfx, key=lambda c: c["startFrame"])],
        "music": music,
        "look": plan.get("look"), "letterbox": bool(plan.get("letterbox")),
        "voice": voice_track(segs, project, fps, total),
    }

    print(f"[build] {slug}: {len(segs)} segments, {total / fps:.2f}s, "
          f"{len(words)} words, {len(overlays)} overlays, {len(sfx)} sfx", file=sys.stderr)
    if table:
        print("[build] anchor table (label | anchor | frame=seconds | spoken token):", file=sys.stderr)
        for label, anchor, frame, token in table:
            print(f"   {label:<28} {anchor:<22} {frame:>5} = {frame / fps:6.2f}s  {token}", file=sys.stderr)

    for w in warnings:
        print(f"[build] WARNING: {w}", file=sys.stderr)

    if not check_only:
        for seg in segs:
            link_or_copy(project / "media" / f"{seg['clip']}.mp4", public / "p" / slug / f"{seg['clip']}.mp4")
        if variant:
            write_json(project / "styles" / variant / "edit.json", edit)
        else:
            write_json(project / "edit.json", edit)
        register(remotion, edit["id"], edit)
    return edit


def main() -> int:
    utf8_console()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", type=Path, help="projects/<name>")
    ap.add_argument("--workspace", type=Path, default=None, help="studio root (default: parent of projects/)")
    ap.add_argument("--check", action="store_true", help="validate and print anchors, write nothing")
    ap.add_argument("--plan", type=Path, default=None, help="use this plan file instead of plan.json")
    ap.add_argument("--variant", default=None, help="register as composition <project>--<variant> (style board)")
    args = ap.parse_args()
    project = args.project.resolve()
    workspace = (args.workspace or project.parent.parent).resolve()
    try:
        edit = compile_plan(project, workspace, args.check, args.plan, args.variant)
    except PlanError as e:
        print(f"[build] PLAN ERROR: {e}", file=sys.stderr)
        return 2
    if not args.check:
        print(f"[build] ok -> composition '{edit['id']}' "
              f"({edit['durationInFrames'] / edit['fps']:.2f}s). Next: studio stills {edit['id']} <sec,sec,…> "
              f"then studio render {edit['id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
