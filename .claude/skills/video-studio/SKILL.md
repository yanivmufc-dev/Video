---
name: video-studio
description: "Sets up a complete AI video-editing studio on Mac or Windows (Hebrew speech-to-text, Remotion, ffmpeg, animation kit, transitions with sound, a commercial-safe sound and emoji library) and then edits any raw footage into finished reels, Shorts or YouTube videos — cuts, karaoke captions, animations, effects, sound, loudness, verification. Built for non-technical Hebrew-speaking creators; works in Claude Code and Codex. Use whenever the user wants to install or repair a video-editing setup, edit a video or reel, add Hebrew captions/subtitles, effects, transitions, B-roll or sound effects, cut silences or retakes, or asks: תתקין לי סטודיו עריכה, תכין לי סביבת עריכת וידאו, תערוך לי סרטון, תערוך לי ריל, כתוביות לסרטון, תוסיף אפקטים, מעברים עם סאונד, תחתוך שקטים, הסטודיו לא עובד, תעדכן את הסטודיו — even if they don't say 'studio'."
license: Proprietary — for club members. Bundled sounds are CC0 (see assets/sfx/CREDITS.json).
compatibility: "Claude Code or Codex. macOS 15+ (Apple Silicon or Intel) or Windows 10 1809+/11 x64. Internet for setup, ~8 GB free disk. Installs per-user inside one folder."
metadata:
  author: practice-ai
  version: "1.1.1"
  short-description: "סטודיו עריכת וידאו עם AI — התקנה ועריכה"
---

# Video Studio — סטודיו עריכת וידאו עם AI

You build and run a video-editing studio for a creator who is usually **not technical**.
Speak **Hebrew** (unless they write otherwise), in short plain sentences, one step at a time.
Say what you're about to do and why in one line; never dump logs or code on them. Translate
tech into editing words (קאט, כתוביות, שכבה, מעבר, אפקט, רינדור).

The studio is one folder (`~/VideoStudio` on Mac; `%USERPROFILE%\VideoStudio` or
`C:\VideoStudio` on Windows) that contains everything: its own Python (via uv), Node.js,
ffmpeg, Remotion with an animation kit, the Hebrew speech model, and an asset library.
Everything lives inside that folder and runs under the member's normal user account, so removing
the studio is just deleting the folder.

Four layers, in this order: **1. transcription** (Hebrew, word-level) → **2. Remotion** (the
editing/render engine) → **3. animations** (the kit + custom components) → **4. effects**
(transitions with sound, SFX, emoji, overlays, B-roll).

## Step 0 — where are we?

Find the studio: the current folder if it has `.studio/state.json`; otherwise
`~/VideoStudio` (Mac) or `%USERPROFILE%\VideoStudio` / `C:\VideoStudio` (Windows).

- **No studio yet** → Setup (below). Even if the member asked to edit a video: explain in one
  line that the studio is needed first (~20 min, once), then set it up and continue with
  their video.
- **Studio exists, some step not done** (`studio setup --status`) → resume setup.
- **Studio ready** → first compare `studio version` with this skill's `scripts/VERSION`. If
  the skill is newer, or the answer is "unknown" / "unknown command" (a 1.0 studio), update it before editing — one line to the
  member ("מעדכן את הסטודיו לגרסה החדשה, דקה-שתיים"), then run the wizard command from Setup
  step 3 with `--update` added (projects, outputs, keys and the member's own notes stay as
  they are). Then Edit. If the agent session was opened elsewhere, work with absolute
  paths into the studio (or ask the member to reopen the agent in the studio folder — its
  AGENTS.md then loads automatically).
- **"it doesn't work" / errors** → `studio doctor`, then references/troubleshooting.md.

The launcher — run from the studio folder: **Mac** `./studio <cmd>` · **Windows**
`.\studio.cmd <cmd>` (never call system ffmpeg/node/python; the studio has its own).

## Setup (first time) — full script in references/setup-guide.md

1. Tell the member the plan in 4 lines (the four layers, ~15–30 min of downloads, all inside
   one folder) and confirm the folder location (rules in setup-guide.md §1: ASCII path, not in
   OneDrive/iCloud/Desktop/Documents).
2. **Install uv into the studio** — the only OS-specific command:
   - Mac:
     `mkdir -p "$HOME/VideoStudio/tools" && curl -LsSf https://astral.sh/uv/install.sh | env UV_UNMANAGED_INSTALL="$HOME/VideoStudio/tools/uv" INSTALLER_NO_MODIFY_PATH=1 sh`
   - Windows (PowerShell; picks `C:\VideoStudio` automatically when the profile path has
     Hebrew letters, spaces or OneDrive):
     `$ws="$env:USERPROFILE\VideoStudio"; if ($ws -match '[^\x00-\x7F]| |OneDrive') { $ws='C:\VideoStudio' }; New-Item -ItemType Directory -Force "$ws\tools" | Out-Null; $env:UV_UNMANAGED_INSTALL="$ws\tools\uv"; $env:INSTALLER_NO_MODIFY_PATH="1"; irm https://astral.sh/uv/install.ps1 | iex; "studio: $ws"`
   On Windows run it in PowerShell (Claude Code: the PowerShell tool; from a Bash-only shell wrap
   it as `powershell -NoProfile -ExecutionPolicy Bypass -Command "..."`). It prints
   `studio: <path>` — use that literal path below (every command runs in a fresh shell, so
   `$ws` doesn't survive to the next one).
3. **Run the wizard from this skill's folder** (`<skill>` = the folder of this SKILL.md,
   `<studio>` = the studio path):
   - Mac: `cd "$HOME/VideoStudio" && UV_CACHE_DIR="$HOME/VideoStudio/.cache/uv" UV_PYTHON_INSTALL_DIR="$HOME/VideoStudio/tools/python" tools/uv/uv run --python 3.12 "<skill>/scripts/setup.py" --workspace "$HOME/VideoStudio"`
   - Windows: `cd "<studio>"; $env:UV_CACHE_DIR="<studio>\.cache\uv"; $env:UV_PYTHON_INSTALL_DIR="<studio>\tools\python"; & "<studio>\tools\uv\uv.exe" run --python 3.12 "<skill>\scripts\setup.py" --workspace "<studio>"`
   After the first step the launcher exists; continue from the studio folder with
   `studio setup --resume`. To update an existing studio, add `--update` to the same command.
   The workspace step also writes two small agent-settings files — tell the member in one
   sentence what they do: `.claude/settings.json` lets the studio's own commands run without a
   question every time and keeps the keys file private from the agent; `.codex/config.toml`
   lets Codex download packages inside the studio folder. The exact rules, if they ask:
   allowed — `./studio` / `.\studio.cmd`, the studio's own `tools/uv` and `tools/ffmpeg`,
   reading `projects/`, `output/`, `input/` and `tools/studio/docs/`, fetching remotion.dev docs;
   denied — `rm -rf`, `sudo`, recursive `Remove-Item`, reading or editing `api-keys.txt`.
   Everything else still asks. Both files stay inside the studio folder.
4. Steps: workspace → ffmpeg → node → remotion → transcription → effects → demo. Each prints
   a JSON line: `done` → one-line update; `needs_user` → relay `hint_he` word for word and wait;
   `failed` → troubleshooting.md, fix, `studio setup --step <step>`. Long steps: background +
   check back, or a long timeout.
5. **Layer 1 decision** before the transcription step: run `studio doctor`, tell the member
   the verdict (local = free & private; cloud = for weak machines — Deepgram has free credit,
   no card). Details and key instructions: references/transcription.md. Keys live in the
   studio's `api-keys.txt`: the member opens it and pastes the key there (the chat never needs
   to see it), then you re-run the step.
6. When the demo renders: look at its contact sheet yourself, show the member
   `output/demo_v1.mp4`, give the 4-line tour (setup-guide.md §6), and offer to edit their
   first real video now.

## Edit — full workflow in references/editing-workflow.md

`new` → `ingest` → `framing` (where the face is) → `transcribe` → read transcript + collect
name fixes → **style board** (`studio styles <name>`: their own footage in 8 styles — open it
for the member and let them pick by number) → brief (one interview, incl. how wild — scenes,
bursts, looks — and the **call to action** in their words: follow, comment a word, link in
bio; if they have none, the video ends without one rather than with one you made up) → `cuts` (+ member
approves proposals) → story in plain Hebrew → **yes** → `plan.json` → `build` → `stills` →
look → member approves → `render` → look at the sheet → deliver (the `_share.mp4` is the one
to send/upload; the full-quality master is for archive) → iterate as `_v2`, `_v3` (small
fixes: `render --replace`), logging to `projects/<name>/notes.md`.

The edit is described in `projects/<name>/plan.json`; `studio build` turns word anchors into
frames. Reference: references/edit-plan.md (segments, captions, the overlay catalog,
**full-screen scenes** — kinetic typography, numbers, lists, compare, steps, chat, terminal,
device/landing page, media — transitions and their sounds, sfx, music). Styles:
references/style-recipes.md. Default to rich: plan which lines become scenes before anything
else; a talking head with a few stickers is what members call "nice but not enough".

## Non-negotiable rules

1. **When the speaker is shown, the face is fully visible** (hair to chin). Punch-ins ≤ 1.25,
   top-weighted, never cover the mouth. Hiding the speaker *completely* with full-screen scenes
   is encouraged — a produced edit is ~half speaker, half scenes (style-recipes.md → Recipe D).
2. **Effects land on their spoken word** — `at: {"word": …}` anchors, never eyeballed seconds.
3. **Word-level transcripts only**; never cut inside a word; cuts come from `studio cuts`.
4. **Nothing on the face**: text above the hair, captions under the chin (automatic after
   `studio framing`), stickers beside the head; captions above all layers; Hebrew in logical
   order (never reversed).
5. **Voice untouched; effects under it; −14 LUFS master** (the render step does it).
6. **Commercial-safe assets only** — references/effects-library.md lists sources and red flags.
7. **Confirm before cutting and before full renders**: plain-Hebrew plan → yes; stills → yes.
8. **Look before you show**: open every still/contact sheet yourself; a failed verify is fixed,
   not delivered; check the output file is from THIS run.
9. **The member stays in charge of their accounts and their computer.** When something needs
   them — a password, a security or permission prompt, signing up to a service, an API key, a
   system setting — explain in Hebrew exactly what to click, then wait until they say it's
   done. Those decisions are theirs, so you guide and they click.
10. **Only what they said.** Facts, numbers, quotes and the call to action on screen come from
   the member or the transcript; ask when something is missing.

## Reference map — read when needed

| File | Read when |
|---|---|
| references/setup-guide.md | installing, resuming or repairing the studio |
| references/transcription.md | choosing local vs cloud, API keys, accuracy, privacy |
| references/editing-workflow.md | every edit (the full loop, all kinds of footage) |
| references/edit-plan.md | writing plan.json — every field, overlay, transition |
| references/style-recipes.md | choosing a style, rhythm rules, modeling a reference video |
| references/effects-library.md | sounds, emoji, icons, B-roll, music, licensing |
| references/animation-cookbook.md | a custom animation beyond the overlay catalog |
| references/gotchas.md | before custom code or manual ffmpeg; when something looks off |
| references/troubleshooting.md | any error |
| README.md | the member asks how to install this skill (e.g. on another computer) |

Inside a studio these docs are also at `tools/studio/docs/`, so any agent opened in the studio
can use them even without this skill.

## Harness notes

- **Claude Code**: use AskUserQuestion for the brief; `run_in_background` for renders/installs;
  Read tool to look at PNG stills/sheets. On Windows the PowerShell tool runs `.\studio.cmd`.
- **Codex**: ask the brief as a short numbered list; the sandbox needs network during setup
  (the member approves, or trusts the studio folder — its `.codex/config.toml` enables network);
  view images with your image tool; long commands need a generous timeout.
