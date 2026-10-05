# Troubleshooting — symptom → cause → fix

Start every diagnosis with `studio doctor` (read its "studio" checks) and the step status in
`.studio/state.json`. Explain problems to the member in one plain Hebrew sentence; never paste
a stack trace at them. If a fix needs the member (a click, a password, a setting), say exactly
what to click and wait — never try to work around a security prompt.

## Install / setup

| Symptom | Cause | Fix |
|---|---|---|
| `studio` / `studio.cmd` "not found" | the agent's shell is not in the studio folder | run it with the full path, or `cd` into the studio folder first |
| Mac: "permission denied" on `./studio` | lost the executable bit (copied via zip) | `chmod +x studio` |
| Windows: `npm.ps1 cannot be loaded` | PowerShell execution policy | use `.\studio.cmd npm …` — cmd isn't affected, so the system policy can stay as it is |
| Windows: ffmpeg/ffprobe "blocked" or "access denied" | Smart App Control / Defender blocks unsigned programs | re-run `studio setup --step ffmpeg` first. If it's still blocked, guide the member to Windows Security → App & browser control → the blocked item, and let them decide whether to allow it (it's their security setting) |
| setup `remotion` step: "macOS 15 required" | old macOS | member updates macOS (System Settings → General → Software Update) |
| `npm install` very slow on Windows | Defender scanning thousands of files | normal on first install (5–10 min); wait |
| `npm install` fails with network / certificate errors | office proxy / filtering (e.g. Netfree) | ask if they're on a filtered/corporate network; try another network; for Netfree, the member must allow nodejs.org/npmjs.org/huggingface.co |
| model download stuck / fails | network, disk space | `studio doctor` for free disk; re-run `studio setup --step transcription` (resumes) |
| Codex: every command asks for approval / network blocked | project not trusted or sandbox without network | the member trusts the folder when Codex asks; `.codex/config.toml` enables network for trusted projects |
| Windows on ARM (Snapdragon laptops) | no native Remotion / speech builds | transcription → cloud engine; rendering runs x64-emulated (may be slow, unverified) |

## Transcription

| Symptom | Cause | Fix |
|---|---|---|
| `cublas64_12.dll not found` then CPU fallback | NVIDIA libs missing | re-run `studio setup --step transcription` (adds them); CPU fallback still works |
| very slow (< 0.7× realtime) | weak CPU | offer a cloud engine (transcription.md) |
| gibberish / English words spelled in Hebrew | wrong language or very noisy audio | the engine is fixed to Hebrew; check audio quality; for English videos this studio isn't tuned |
| brand names wrong ("Cloud") | normal ASR behavior | `fixes` in plan.json |
| `…_API_KEY is missing` | key not in `api-keys.txt` (or the `#` is still at the line start) | member adds it (transcription.md §5) |
| `TypeError … metadata_errors` (PyAV) | a new PyAV release changed its API | the studio passes decoded audio as an array and pins `av<19`; re-run the workspace update from the current skill (setup-guide.md §7) |

## Build

| Symptom | Fix |
|---|---|
| `PLAN ERROR: word 'X' … not found in the final cut` | the word was cut out, or spelled differently (prefix, final letter). Use the "similar words" hint, `n`, or a `{"clip","t"}` anchor |
| `segment N: media/clipNN.mp4 not found` | ingest first; clip names are clip01, clip02… |
| `sound 'X' not in library/sfx` | pick a name from the printed list (effects-library.md), or `studio sfx-make` |
| WARNING overlap transition over speech | use a CUT transition, or move the cut into a pause |
| WARNING emoji has no asset | `studio fetch emoji 🔥` |
| WARNING overlay covers the face | move it: text above the hair, stickers beside the head (the warning prints the head's box) |
| WARNING captions sit on the mouth | remove `captions.y` (auto placement under the chin) or set it lower |
| WARNING no framing data | run `studio framing <name>` |
| "N transcript words fall inside cuts" | normal for removed retakes; if a word you wanted is missing, widen that segment |

## Render

| Symptom | Cause | Fix |
|---|---|---|
| "Could not find composition <name>" | not built / Studio cache | `studio build <name>` again |
| TypeScript/compile error in `src/custom/…` | a custom component bug | `studio npx tsc --noEmit`, fix, rebuild |
| render hangs at 0% or "delayRender … not cleared" | font/network load, GPU renderer on old Windows | re-run; if it repeats: `studio render <name> --gl=swangle` |
| render very slow | 4K sources not ingested, heavy blur/shadows, many B-roll videos | always ingest; `--draft` for previews; close other apps |
| colors look washed on the phone | BT.601 tag (old render path) | renders through `studio render` are tagged BT.709 |
| audio pops at cuts | cut inside a word / raw ffmpeg concat | use segments from `studio cuts`; never concat with `-c copy` |
| lips out of sync | concatenated AAC with stream copy, or a frame-dependent trim in custom code | re-render through `studio render`; check custom code rule 6 |
| ENAMETOOLONG (Windows) | too many audio layers | fewer SFX; B-roll is muted automatically |

## Verify failures

| Check | Meaning / fix |
|---|---|
| loudness | re-run `studio master in out`; if the source is extremely quiet/noisy, say so |
| black | a gap in segments or a B-roll that failed to load — look at the sheet at that time |
| frozen | a still image or paused video ≥ 2 s — fine if intentional (a screenshot), otherwise fix |
| silence | ≥ 2.5 s without sound — a missing audio track or a mis-cut |
| duration | the output doesn't match the plan — a stale file or a failed render; re-render |

## Manual ffmpeg

`studio ffmpeg …` and the Python tools resolve relative paths from the folder you run them in;
`studio npx …`/`npm …` always run inside `remotion/` (so `studio npx tsc --noEmit`, no `-p`). The studio's ffmpeg
has no font configuration: `drawtext` needs an explicit `fontfile=`; for labeled frames use
`studio sheet` instead.

## Asking for help

When stuck after two attempts: write in notes.md what was tried, show the member the one
error line in Hebrew terms, and offer the next concrete option (another engine, a draft
render, skipping the problematic effect).
