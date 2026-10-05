# /// script
# requires-python = ">=3.10,<3.14"
# dependencies = [
#   "faster-whisper==1.2.1",
#   "ctranslate2>=4.6.3,<5",
#   "huggingface_hub>=1.0,<2",
#   "onnxruntime<1.24; sys_platform == 'darwin' and platform_machine == 'x86_64'",
#   "requests>=2.31",
#   "av>=11,<19",
#   "numpy>=1.26",
# ]
# ///
"""Hebrew word-level transcription of every clip in a project.

    uv run tools/transcribe.py projects/my-reel                    # engine from .studio/state.json
    uv run tools/transcribe.py projects/my-reel --engine local
    uv run tools/transcribe.py projects/my-reel --engine deepgram  # needs DEEPGRAM_API_KEY in api-keys.txt
    uv run tools/transcribe.py projects/my-reel --prompt "Claude Code, Remotion, סקיל"
    uv run tools/transcribe.py projects/my-reel --test-model      # just load the model (setup check)

Writes projects/<p>/transcripts/<clip>.words.json:
    {"words": [{"text", "start", "end", "prob"}], "duration", "engine", "model", ...}
Word-level and verbatim on purpose: phrase/SRT output loses the timing that cuts,
karaoke captions and word-anchored effects all depend on. Cached: a clip is only
transcribed again if its media changed (or with --force).

Engines
  local      ivrit-ai/whisper-large-v3-turbo-ct2 (the best Hebrew model we know), free,
             offline. GPU on NVIDIA, fast CPU path on Apple Silicon, int8 elsewhere.
  soniox     most accurate Hebrew API; ~$0.10 per audio hour (SONIOX_API_KEY)
  deepgram   Nova-3 Hebrew; $200 free credit, no card (DEEPGRAM_API_KEY)
  groq       free tier, vanilla Whisper large-v3 — ~2x the errors of ivrit.ai (GROQ_API_KEY)
  openai     whisper-1, the only OpenAI model with word timestamps (OPENAI_API_KEY).
             The newer gpt-4o/gpt-transcribe models have NO word timestamps -> unusable here.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _studio import KEYS_FILE, api_key, ffmpeg, read_json, write_json  # noqa: E402

REPO = "ivrit-ai/whisper-large-v3-turbo-ct2"
SONIOX_MODEL = "stt-async-v5"
# Pinned snapshot (weights v2025.05.13). Snapshots differ in quality — never float to "latest".
REVISION = "72ad623a37947395efcc3933132353790e5a12f5"


def load_wav(path: Path):
    """16 kHz mono PCM WAV -> float32 array. Handing faster-whisper an array (not a path)
    skips its PyAV decoder, whose API changes between releases (PyAV 19 broke it)."""
    import wave

    import numpy as np
    with wave.open(str(path)) as f:
        data = f.readframes(f.getnframes())
    return np.frombuffer(data, np.int16).astype(np.float32) / 32768.0


# ------------------------------------------------------------------ audio

def extract_audio(src: Path, dst: Path, for_upload: bool) -> Path:
    """16 kHz mono. WAV for local models; small Opus (~11 MB/hour) for uploads."""
    if for_upload:
        args = ["-c:a", "libopus", "-b:a", "24k", "-application", "voip"]
    else:
        args = ["-c:a", "pcm_s16le"]
    subprocess.run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
                    "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "16000", *args, str(dst)], check=True)
    return dst


# ------------------------------------------------------------------ local (faster-whisper)

def add_windows_cuda_dlls() -> None:
    """pip's nvidia-cublas-cu12 puts its DLLs where Windows never looks. Register them
    before ctranslate2 loads (ctranslate2 >= 4.6.3 no longer needs cuDNN)."""
    if sys.platform != "win32":
        return
    for pkg in ("nvidia.cublas",):
        try:
            spec = importlib.util.find_spec(pkg)
        except ModuleNotFoundError:
            spec = None
        for base in (spec.submodule_search_locations or []) if spec else []:
            dll_dir = os.path.join(base, "bin")
            if os.path.isdir(dll_dir):
                os.add_dll_directory(dll_dir)
                os.environ["PATH"] = dll_dir + os.pathsep + os.environ.get("PATH", "")


def total_ram_gb() -> float:
    if sys.platform == "win32":
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = MEMORYSTATUSEX()
        m.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))  # type: ignore[attr-defined]
        return m.ullTotalPhys / 2**30
    return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30


def local_plans():
    """Ordered (device, compute_type, batch) candidates; the first one that works wins."""
    import ctranslate2
    out = []
    if ctranslate2.get_cuda_device_count() > 0:
        out.append(("cuda", "float16", 8))
        out.append(("cuda", "int8_float16", 4))  # small-VRAM fallback
    ram = total_ram_gb()
    if sys.platform == "darwin" and platform.machine() == "arm64" and ram >= 15:
        out.append(("cpu", "float32", 8))  # Accelerate/AMX: fastest on Apple Silicon (6x realtime on M4)
    out.append(("cpu", "int8", 4 if ram >= 7 else 1))
    return out


_MODELS: dict = {}


def recover_gaps(model, audio, words: list[dict], kw: dict) -> None:
    """The batched pipeline sometimes drops a sentence — at the end of a clip or in the middle.
    Any stretch of >= 1.2 s without words but with speech-level sound is transcribed again on
    its own and the words are inserted in place."""
    import numpy as np
    sr = 16000
    hop = sr // 10
    ref = float(np.sqrt(np.mean(audio ** 2))) + 1e-9
    dur = len(audio) / sr
    edges = [0.0] + [x for w in words for x in (w["start"], w["end"])] + [dur]
    gaps = [(edges[i], edges[i + 1]) for i in range(0, len(edges) - 1, 2) if edges[i + 1] - edges[i] >= 1.2]
    added = 0
    for a, b in gaps:
        chunk = audio[int(a * sr):int(b * sr)]
        n = len(chunk) // hop
        if n < 6:
            continue
        rms = np.sqrt(np.mean(chunk[: n * hop].reshape(n, hop) ** 2, axis=1))
        if (rms > 0.5 * ref).sum() < 6:  # < 0.6 s of speech-level sound: a real pause
            continue
        s0, s1 = max(0.0, a - 0.15), min(dur, b + 0.15)
        segs, _ = model.transcribe(audio[int(s0 * sr):int(s1 * sr)], vad_filter=False,
                                   condition_on_previous_text=False, **kw)
        for sg in segs:
            for w in sg.words or []:
                st, en = w.start + s0, w.end + s0
                if st >= a - 0.05 and en <= b + 0.1 and w.word.strip():
                    words.append({"text": w.word.strip(), "start": round(st, 3), "end": round(en, 3),
                                  "prob": round(w.probability, 3)})
                    added += 1
    if added:
        words.sort(key=lambda w: w["start"])
        print(f"[transcribe] recovered {added} word(s) the first pass had missed", file=sys.stderr)


def local_transcribe(wav: Path, prompt: str | None) -> dict:
    add_windows_cuda_dlls()
    from faster_whisper import BatchedInferencePipeline, WhisperModel

    last_err = None
    for device, compute, batch in local_plans():
        try:
            key = (device, compute)
            if key not in _MODELS:
                _MODELS[key] = WhisperModel(REPO, revision=REVISION, device=device, compute_type=compute)
            model = _MODELS[key]
            kw = dict(language="he", word_timestamps=True, beam_size=5)
            if prompt:
                kw["initial_prompt"] = prompt
            audio = load_wav(wav)
            if batch > 1:
                segments, info = BatchedInferencePipeline(model).transcribe(audio, batch_size=batch, **kw)
            else:
                segments, info = model.transcribe(audio, vad_filter=True,
                                                  condition_on_previous_text=False, **kw)
            words, phrases = [], []
            for s in segments:  # lazy: GPU library errors surface HERE, not at load time
                phrases.append({"start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip()})
                for w in s.words or []:
                    words.append({"text": w.word.strip(), "start": round(w.start, 3),
                                  "end": round(w.end, 3), "prob": round(w.probability, 3)})
            recover_gaps(model, audio, words, kw)
            return {"duration": round(info.duration, 3), "engine": "local", "model": REPO,
                    "revision": REVISION, "device": f"{device}/{compute}", "phrases": phrases, "words": words}
        except (RuntimeError, OSError, ValueError) as e:  # e.g. cublas64_12.dll not found
            last_err = e
            print(f"[transcribe] {device}/{compute} failed ({e}); trying the next option", file=sys.stderr)
    raise SystemExit(f"[transcribe] every local option failed ({last_err}). Use a cloud engine: "
                     "--engine deepgram (free credit) or --engine soniox.")


# ------------------------------------------------------------------ cloud

def need_key(name: str) -> str:
    key = api_key(name)
    if not key:
        raise SystemExit(f"[transcribe] {name} is missing. Ask the member to add it to {KEYS_FILE} in the "
                         f"studio folder as a line {name}=... (keys go in that file, not in the chat).")
    return key


def cloud_deepgram(audio: Path, prompt: str | None) -> dict:
    import requests
    params = {"model": "nova-3", "language": "he", "punctuate": "true", "smart_format": "true"}
    if prompt:
        params["keyterm"] = [t.strip() for t in prompt.split(",") if t.strip()][:50]
    with open(audio, "rb") as f:
        r = requests.post("https://api.deepgram.com/v1/listen", params=params, data=f, timeout=900,
                          headers={"Authorization": f"Token {need_key('DEEPGRAM_API_KEY')}",
                                   "Content-Type": "audio/ogg"})
    r.raise_for_status()
    j = r.json()
    alt = j["results"]["channels"][0]["alternatives"][0]
    words = [{"text": w.get("punctuated_word", w["word"]), "start": round(w["start"], 3),
              "end": round(w["end"], 3), "prob": round(w.get("confidence", 1.0), 3)} for w in alt["words"]]
    return {"duration": round(j["metadata"]["duration"], 3), "engine": "deepgram", "model": "nova-3",
            "words": words}


def cloud_soniox(audio: Path, prompt: str | None) -> dict:
    import requests
    base = "https://api.soniox.com/v1"
    h = {"Authorization": f"Bearer {need_key('SONIOX_API_KEY')}"}
    with open(audio, "rb") as f:
        up = requests.post(f"{base}/files", headers=h, files={"file": (audio.name, f)}, timeout=900)
    up.raise_for_status()
    file_id = up.json()["id"]
    body = {"model": SONIOX_MODEL, "file_id": file_id,
            "language_hints": ["he"]}
    if prompt:
        body["context"] = prompt
    tr = requests.post(f"{base}/transcriptions", headers=h, json=body, timeout=60)
    tr.raise_for_status()
    tid = tr.json()["id"]
    for _ in range(720):  # up to ~1 hour
        st = requests.get(f"{base}/transcriptions/{tid}", headers=h, timeout=60).json()
        if st.get("status") == "completed":
            break
        if st.get("status") == "error":
            raise SystemExit(f"[transcribe] soniox error: {st.get('error_message')}")
        time.sleep(5)
    tokens = requests.get(f"{base}/transcriptions/{tid}/transcript", headers=h, timeout=120).json()["tokens"]
    # Soniox tokens can be sub-words: a new word starts when a token begins with a space.
    words: list[dict] = []
    for t in tokens:
        text = t["text"]
        if not text.strip():
            continue
        if words and not text.startswith(" "):
            words[-1]["text"] += text
            words[-1]["end"] = t["end_ms"] / 1000
        else:
            words.append({"text": text.strip(), "start": t["start_ms"] / 1000, "end": t["end_ms"] / 1000,
                          "prob": round(t.get("confidence", 1.0), 3)})
    for tid_path in (f"{base}/transcriptions/{tid}", f"{base}/files/{file_id}"):
        requests.delete(tid_path, headers=h, timeout=30)  # don't leave the member's audio on the server
    dur = words[-1]["end"] if words else 0.0
    return {"duration": round(dur, 3), "engine": "soniox", "model": body["model"], "words": words}


def cloud_openai_style(audio: Path, prompt: str | None, url: str, key_name: str, model: str) -> dict:
    import requests
    if audio.stat().st_size > 24 * 1024 * 1024:
        raise SystemExit("[transcribe] audio is over the 25 MB API limit — split the video, "
                         "or use deepgram/soniox (large files are fine there)")
    data = [("model", model), ("language", "he"), ("response_format", "verbose_json"),
            ("timestamp_granularities[]", "word"), ("timestamp_granularities[]", "segment")]
    if prompt:
        data.append(("prompt", prompt))
    with open(audio, "rb") as f:
        r = requests.post(url, headers={"Authorization": f"Bearer {need_key(key_name)}"},
                          files={"file": (audio.name, f)}, data=data, timeout=900)
    r.raise_for_status()
    j = r.json()
    words = [{"text": w["word"].strip(), "start": round(w["start"], 3), "end": round(w["end"], 3), "prob": 1.0}
             for w in j.get("words", [])]
    return {"duration": round(j.get("duration", words[-1]["end"] if words else 0), 3),
            "engine": key_name.split("_")[0].lower(), "model": model, "words": words}


CLOUD_HOSTS = {"deepgram": "api.deepgram.com", "soniox": "api.soniox.com",
               "groq": "api.groq.com", "openai": "api.openai.com"}


def cloud(engine: str, audio: Path, prompt: str | None) -> dict:
    print(f"[transcribe] cloud engine: the voice-only audio of {audio.name} is sent to "
          f"{CLOUD_HOSTS.get(engine, engine)} for transcription (nothing else leaves this computer)",
          file=sys.stderr)
    if engine == "deepgram":
        return cloud_deepgram(audio, prompt)
    if engine == "soniox":
        return cloud_soniox(audio, prompt)
    if engine == "groq":
        return cloud_openai_style(audio, prompt, "https://api.groq.com/openai/v1/audio/transcriptions",
                                  "GROQ_API_KEY", "whisper-large-v3")
    if engine == "openai":
        return cloud_openai_style(audio, prompt, "https://api.openai.com/v1/audio/transcriptions",
                                  "OPENAI_API_KEY", "whisper-1")
    raise SystemExit(f"[transcribe] unknown engine '{engine}'")


# ------------------------------------------------------------------ main

def configured_engine(project: Path) -> str:
    state = project.resolve().parent.parent / ".studio" / "state.json"
    if state.exists():
        try:
            return read_json(state).get("transcription", {}).get("engine", "local")
        except Exception:
            pass
    return "local"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", type=Path)
    ap.add_argument("--engine", default=None, choices=["local", "soniox", "deepgram", "groq", "openai"])
    ap.add_argument("--prompt", default=None, help="comma-separated names/terms the speaker uses")
    ap.add_argument("--force", action="store_true", help="re-transcribe even if cached")
    ap.add_argument("--only", default=None, help="only this clip (e.g. clip02)")
    ap.add_argument("--test-model", action="store_true", help="download + load the local model, then exit")
    args = ap.parse_args()

    if args.test_model:
        # Load the model AND run a real (tiny) transcription: loading alone doesn't catch
        # decoder/library problems that only appear when audio is processed.
        import numpy as np
        add_windows_cuda_dlls()
        from faster_whisper import WhisperModel
        t0 = time.time()
        device, compute, _ = local_plans()[0]
        model = WhisperModel(REPO, revision=REVISION, device=device, compute_type=compute)
        load_s = time.time() - t0
        tone = (0.1 * np.sin(2 * np.pi * 220 * np.arange(16000 * 2) / 16000)).astype(np.float32)
        segments, _info = model.transcribe(tone, language="he", word_timestamps=True, beam_size=1)
        list(segments)  # force the lazy generator (GPU errors surface here)
        print(json.dumps({"ok": True, "model": REPO, "device": f"{device}/{compute}",
                          "load_seconds": round(load_s, 1), "decode_test": "ok"}))
        return 0

    engine = args.engine or configured_engine(args.project)
    media = sorted((args.project / "media").glob("clip*.mp4"))
    if args.only:
        media = [m for m in media if m.stem == args.only]
    if not media:
        raise SystemExit(f"[transcribe] no clips in {args.project / 'media'} — run ingest first")
    out_dir = args.project / "transcripts"
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = args.project / ".tmp"
    tmp.mkdir(exist_ok=True)

    for clip in media:
        out = out_dir / f"{clip.stem}.words.json"
        stamp = {"source_size": clip.stat().st_size}
        if out.exists() and not args.force:
            prev = read_json(out)
            if prev.get("source_size") == stamp["source_size"]:
                print(f"[transcribe] cached: {clip.stem} ({len(prev['words'])} words)", file=sys.stderr)
                continue
        t0 = time.time()
        if engine == "local":
            audio = extract_audio(clip, tmp / f"{clip.stem}.wav", for_upload=False)
            result = local_transcribe(audio, args.prompt)
        else:
            audio = extract_audio(clip, tmp / f"{clip.stem}.ogg", for_upload=True)
            result = cloud(engine, audio, args.prompt)
        audio.unlink(missing_ok=True)
        dt = max(0.1, time.time() - t0)
        result.update({"source": clip.name, "language": "he", **stamp})
        write_json(out, result)
        speed = result["duration"] / dt
        print(f"[transcribe] {clip.stem}: {len(result['words'])} words, {result['duration']:.0f}s of audio "
              f"in {dt:.0f}s ({speed:.1f}x realtime, {result['engine']} {result.get('device', '')})",
              file=sys.stderr)
    try:
        tmp.rmdir()
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
