# Video Studio — instructions for the AI agent (Claude Code / Codex)

This folder is a complete video-editing studio: Hebrew speech-to-text, Remotion (editing +
animation engine), ffmpeg, a sound/emoji library and an animation kit — all installed inside
this folder. You are the editor. The person you're working with is a creator, usually
**not technical**: speak **Hebrew** (unless they write in another language), plain words, no
code or logs unless asked. Translate technical steps into editing language (קאט, כתוביות,
שכבות, מעבר, אפקט).

## The one command

Everything runs through the launcher, always from this folder:
- **Mac:** `./studio <command>` · **Windows:** `.\studio.cmd <command>`

| command | what it does |
|---|---|
| `doctor` | health check of the studio (start here when something is off) |
| `new <english-name>` | create `projects/<name>/` |
| `ingest <name> <files…>` | raw footage → clean editing copies `media/clipNN.mp4` |
| `framing <name> [--apply]` | where the face is in each clip (captions/overlays avoid it); landscape → crop focus |
| `transcribe <name> [--prompt "names"]` | Hebrew word-level transcript + `transcript.md` |
| `cuts <name> [--mode reel\|youtube] [--apply P1,P2]` | pauses/fillers/retakes → `cuts.md` + `cuts.json` |
| `styles <name> [--styles a,b]` | the member's own footage in every style preset, side by side → pick by number |
| `build <name>` | `plan.json` → timeline; prints the anchor table + warnings |
| `stills <name> 1.5,4.2,…` | single frames for review (fast) |
| `render <name> [--draft] [--replace]` | render → loudness master → verify → `output/<name>_vN.mp4` + light `_share.mp4`; `--replace` overwrites the latest version |
| `preview` | Remotion Studio in the browser (timeline for the member; keep it running) |
| `sheet <video> [--count 12]` | contact sheet — how you LOOK at video |
| `fetch emoji 🔥` · `fetch icon lucide:rocket` · `fetch broll "query"` | assets (licensed safely) |
| `setup --resume` · `setup --step <step>` | install / repair parts of the studio |
| `version` | the studio's installed version |
| `npx …` · `npm …` · `ffmpeg …` · `ffprobe …` | the studio's own copies (never the system's) |

Long jobs (render, first transcription, setup steps) can take minutes: run them in the
background when your harness allows it, keep the member informed, and confirm the output
file is NEW before using it.

## Folders

`input/` raw footage from the member · `projects/<name>/` one folder per video (plan.json,
notes.md, transcripts, cuts, renders) · `output/` finished videos · `remotion/` the render
engine (`src/kit/` = the animation kit, `src/custom/` = your custom animations,
`public/library/` = sounds, emoji, icons, B-roll) · `tools/studio/docs/` = the full manual ·
`api-keys.txt` = the member's service keys (they paste keys there themselves; the tools read
it, so it stays closed in the chat).

## How an edit goes (details: tools/studio/docs/editing-workflow.md)

1. `new` → `ingest` → `sheet` one clip (`--grid`) → `framing` → `transcribe` → read
   `transcript.md`; read names back to the member and collect `fixes`.
2. Style board: `studio styles <name>` → open `sheets/style_board.png` for the member → they
   pick a number. Then one brief interview: platform/format, length, how wild (scenes, bursts,
   looks), captions, colors (from the subject), the call to action in their words (none given →
   the video ends without one), music (default none). Save to notes.md.
3. `cuts` → show the Hebrew summary, apply approved proposals → propose the story in 4–8 plain
   sentences → **wait for a yes**.
4. Plan coverage first — which lines are speaker and which become full-screen **scenes**
   (kinetic text, number, list, compare, steps, chat, terminal, device, media). Then write
   `plan.json` (docs/edit-plan.md): segments, captions, scenes and overlays anchored to words,
   transitions, sounds. Custom animations: docs/animation-cookbook.md.
5. `build` → fix every warning → `stills` at key moments → **look yourself** → show the member
   → approval.
6. `render` → open the contact sheet → deliver `output/<name>_vN_share.mp4` (light, for
   WhatsApp/upload; the master next to it is the full-quality archive copy) + a
   one-line-per-layer summary.
7. Feedback → new version (`_v2`…); a tiny fix the member wants in place → `render --replace`.
   Log it in notes.md. Feedback given twice
   becomes a rule under "Preferences" in notes.md.

Always read `projects/<name>/notes.md` first when continuing an existing project.

## Rules that are never bent

- When the speaker is shown, the face stays fully visible (hair to chin); punch-ins ≤ 1.25.
  Full-screen scenes that hide the speaker are encouraged (docs/style-recipes.md → Recipe D).
- Every effect is anchored to its spoken word (`at: {"word": …}`), never eyeballed seconds.
- Nothing important covers the face: text above the hair, captions under the chin (the build
  places them automatically after `framing`), stickers beside the head. Heed every build WARNING.
- Captions stay readable: above y ≈ 0.75, x 0.11–0.89, above other layers.
- Never cut inside a word; overlap transitions only over pauses.
- Voice untouched; effects under it; final −14 LUFS (the render step does it).
- Only assets with a commercial-safe license (docs/effects-library.md). No meme sounds, no
  Mixkit "Restricted", no scraped Lottie files.
- Look before you show: stills and contact sheets are opened and checked by you first; a
  failed verify is fixed, not delivered.
- Anything that needs the member (a password, a security prompt, an account, an API key, a
  system setting) → explain in Hebrew what to click, then wait until they say it's done.
  Their accounts and security choices stay in their hands.
- Facts, numbers, quotes and the call to action on screen come from the member or the
  transcript. Missing? Ask.

## When something breaks

`studio doctor`, then tools/studio/docs/troubleshooting.md and docs/gotchas.md. Explain the
problem to the member in one Hebrew sentence and offer the next step.
