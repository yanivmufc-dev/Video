# Gotchas — bugs that already happened once. Never again.

Each: symptom → cause → what the studio does / what you must do. Read before writing any
custom code or touching ffmpeg by hand.

## Hebrew / RTL

1. **"Claude Code" shows as "Code Claude" in word-by-word text.** Per-word spans in an RTL row
   reverse runs of English words. → Group consecutive LTR words into one `dir="ltr"` run
   (`toRuns()` in `src/kit/bidi.ts`; captions and titles already do it).
2. **"Claude Code," — the comma jumps to the start.** Trailing punctuation inside an LTR run
   sits on the wrong side. → Keep it outside the run (`splitTrailingPunct()`).
3. **`.pdf` renders as `pdf.`, `ה-AI` flips.** Latin/number runs need an isolate (`<bdi>`,
   `unicode-bidi: isolate`, or `dir="ltr"`).
4. **Never reverse strings, never `row-reverse`, never python-bidi before rendering** — double
   reversal scrambles punctuation and parentheses.
5. **Whisper splits "ה-AI" into "ה" + "-AI"** → the build glues tokens that start with `-`/`־`
   back onto the previous word.
6. **Speech recognition writes "Cloud" for "Claude"** (and similar for brand names, even with
   a prompt). → `fixes` in plan.json, every project.
7. **Burning captions with ffmpeg/libass instead of Remotion** (only if you ever must): ASS
   style `Encoding=-1` (177 misplaces parentheses), filter `ass=…:shaping=complex` (not
   `subtitles`), and use `\k` not `\kf` (the fill sweeps left→right, i.e. backwards in Hebrew).

## Remotion

8. **Garbled, double-speed audio.** A frame-dependent `trimBefore`/`startFrom`. → Trim is
   static; offsets come from `<Sequence from>`. The kit does this.
9. **Silent first seconds.** A full-screen intro *replaced* the video instead of covering it.
   → The voice track runs from frame 0; overlays only cover pixels.
10. **Fade-out starts immediately.** `useVideoConfig().durationInFrames` inside a Sequence is
    the whole video. → Use the element's own duration (`ov.durationInFrames`).
11. **Scaled keyword overlaps its neighbour.** CSS `transform: scale` doesn't take layout
    space. → Emphasis by font size (the kit does); transforms only for small pulses.
12. **Semi-transparent panels unreadable over bright video.** → Opaque backgrounds (≥ 0.85).
13. **A caption page split across a cut looks broken.** → Pages never cross a segment (built in).
14. **Remotion v4 tags output as BT.601 by default** (colors shift on phones). → Renders use
    `--color-space=bt709` (the launcher does).
15. **iPhone HEVC can't be decoded by headless Chrome** → silently falls back to the slow
    path. → Always ingest (H.264 proxies) first.
16. **Fonts not loaded → wrong font or render timeout.** → Load via the kit's `fontFamily()`
    (Hebrew subsets, few weights); timeout raised to 120 s in remotion.config.ts.
17. **Many audio layers → ENAMETOOLONG on Windows.** → B-roll video is always muted; keep SFX
    cues reasonable (< ~60).
18. **Newer transitions (bookFlip, filmBurn, ripple…) don't show in Studio preview** without a
    Chrome flag. → The kit uses only flag-free ones.
19. **macOS older than 15** → Remotion's bundled ffmpeg crashes. → The doctor blocks it with a
    clear message (update macOS).

## ffmpeg / audio

20. **`loudnorm` silently outputs 192 kHz.** → Always `-ar 48000` (master_audio does).
21. **`linear=true` silently degrades to dynamic** on peaky speech. → master_audio reports
    `normalization_type`; both are acceptable, it's informational.
22. **AAC re-introduces true peaks after loudnorm.** → Limiter 0.5 dB under the target.
23. **`alimiter` auto-normalizes by default.** → `level=disabled` always.
24. **Joining AAC clips with `-c copy` drifts lip-sync** (~4 ms per cut). → Never concat by
    stream copy; Remotion renders the whole timeline in one pass.
25. **iPhone 17 files have a second, undecodable spatial-audio track + metadata tracks.** →
    Always map `0:v:0` and `0:a:0` (ingest does).
26. **Homebrew's plain `ffmpeg` has no zscale/libass/drawtext anymore.** → The studio ships its
    own full ffmpeg in `tools/ffmpeg`; don't call a system ffmpeg.
27. **zsh eats `$VAR:l`** in shell one-liners. → Use `${VAR}` — or better, the studio tools.
28. **Whisper word timestamps are contiguous and ~0.1 s early** → pauses are found in the
    audio, cuts are padded (cut_plan does both).
28b. **Stretched words vanished from captions at cuts** (a word spanning a removed pause was
    dropped by its midpoint). → Words are assigned by largest overlap; the build reports how
    many words fell fully inside cuts.
28c. **A new PyAV release broke transcription** (`metadata_errors` removed) while the setup
    check (model load only) still passed. → Audio goes to the model as an array, `av<19` is
    pinned, and the setup check runs a real mini-transcription.
28e. **The cut planner removed the real words "אם"/"הם" as hesitations** (final-letter
    normalization turned them into "אמ"/"המ"). → Hesitations are matched on raw letters and
    need a doubled mem (אממ, הממ); always read cuts.md before applying.
28f. **The batched transcriber occasionally dropped the last seconds of a long clip.** →
    transcribe.py re-transcribes a tail that still has speech-level sound and appends it.
28d. **Default overlay positions covered a close selfie's face.** → `studio framing` + build
    warnings + automatic caption placement under the chin.

## Process

29. **Stale output shown as new.** A background render failed, a pipe hid the exit code, the
    old file was delivered. → Check the output file's modification time and the verify
    report of THIS run before showing anything.
30. **Commands time out after ~2 minutes in some agent shells.** Renders, model downloads and
    npm installs can take longer. → Run them in the background (if your harness supports it)
    and poll the output file/log; or set a long timeout.
31. **Sampling a still 2% into an effect shows a half-faded element** and looks like a bug. →
    Sample effects at their middle.
32. **No audio verification → a garbled render reached the client.** → verify.py checks
    loudness and silence gaps; also listen-check suspicious moments with a short draft.
33. **Hebrew Windows username / OneDrive folder breaks tools** (model loading, npm caches). →
    The studio lives at an ASCII local path and keeps every cache inside itself.
34. **PowerShell blocks `npm.ps1`/`npx.ps1`** (execution policy). → Always go through
    `studio.cmd` (cmd files aren't subject to it), e.g. `.\studio.cmd npx remotion …`.
35. **New PATH not visible after installing something.** → The studio never relies on PATH;
    everything is called by absolute path from `tools/`.
