# Setup guide — building the studio with the member, step by step

The member is usually not technical. Speak Hebrew, one short step at a time, say what is
about to happen and why in one sentence, and report progress in plain words ("מוריד את
מנוע העריכה — כ-2 דקות"). Never dump logs. Every step is resumable: if anything breaks or
the member closes the app, `studio setup --resume` continues where it stopped.

## Contents
1. Before starting (what to ask, where the studio goes)
2. Stage 0 — install uv (the only per-OS command)
3. Stage 1..6 — run the wizard
4. Reading the wizard's output
5. The transcription choice (layer 1)
6. After setup — the tour and the first edit
7. Updating and repairing

---

## 1. Before starting

1. Detect the OS from your environment (macOS → zsh; Windows → PowerShell). Don't ask the
   member what they have if you can tell.
2. Explain the plan in 4 lines (the four layers): transcription in Hebrew → the editing
   engine (Remotion) → animations → effects and sounds. ~15–30 minutes, mostly downloads
   (~3 GB). Everything installs inside one folder under your own user — deleting the folder
   removes it all.
3. Where the studio goes:
   - **Mac**: `~/VideoStudio`
   - **Windows**: `%USERPROFILE%\VideoStudio` if that path is plain English letters with no
     spaces and is **not** inside OneDrive; otherwise `C:\VideoStudio`.
   Never inside Desktop/Documents/Downloads (iCloud/OneDrive sync them), never a path with
   Hebrew letters. Confirm the location with the member in one sentence.
4. **Codex users**: Codex's sandbox only writes inside the folder the session was opened in,
   and blocks internet by default. Smoothest flow: run stage 0 (it creates the studio folder),
   then ask the member to open a **new Codex session in the studio folder** and say
   "המשך התקנה" — from there every write is inside the workspace; approve network access when
   Codex asks (downloads). After setup, `.codex/config.toml` in the studio enables network for
   that folder once the member trusts it.

## 2. Stage 0 — install uv into the studio

uv is a small tool that brings its own Python, so nothing else needs to be installed first.
Run exactly one of these (they only write inside the studio folder):

**Mac (zsh):**
```sh
mkdir -p "$HOME/VideoStudio/tools" && curl -LsSf https://astral.sh/uv/install.sh | env UV_UNMANAGED_INSTALL="$HOME/VideoStudio/tools/uv" INSTALLER_NO_MODIFY_PATH=1 sh
```
**Windows (PowerShell)** — chooses `C:\VideoStudio` by itself when the profile path has Hebrew
letters, spaces or OneDrive, and prints the chosen path:
```powershell
$ws="$env:USERPROFILE\VideoStudio"; if ($ws -match '[^\x00-\x7F]| |OneDrive') { $ws='C:\VideoStudio' }; New-Item -ItemType Directory -Force "$ws\tools" | Out-Null; $env:UV_UNMANAGED_INSTALL="$ws\tools\uv"; $env:INSTALLER_NO_MODIFY_PATH="1"; irm https://astral.sh/uv/install.ps1 | iex; "studio: $ws"
```
If PowerShell refuses to run the script: `powershell -ExecutionPolicy ByPass -NoProfile -Command "<the same line>"`
(this affects only that one command — never change the system execution policy).

## 3. Run the wizard

From the skill's folder (`<skill>` = the directory containing this skill's SKILL.md):

**Mac:** `cd "$HOME/VideoStudio" && UV_CACHE_DIR="$HOME/VideoStudio/.cache/uv" UV_PYTHON_INSTALL_DIR="$HOME/VideoStudio/tools/python" tools/uv/uv run --python 3.12 "<skill>/scripts/setup.py" --workspace "$HOME/VideoStudio"`
**Windows:** `cd "<studio>"; $env:UV_CACHE_DIR="<studio>\.cache\uv"; $env:UV_PYTHON_INSTALL_DIR="<studio>\tools\python"; & "<studio>\tools\uv\uv.exe" run --python 3.12 "<skill>\scripts\setup.py" --workspace "<studio>"`
(`<studio>` = the literal path printed by stage 0 — shell variables don't survive between commands.)

The first step copies everything the studio needs into the folder, including the launcher.
From then on use the launcher from inside the studio folder:
**Mac:** `./studio setup --resume` · **Windows:** `.\studio.cmd setup --resume`

The steps, what to tell the member, and how long they take:

| step | say (Hebrew, one line) | time |
|---|---|---|
| workspace | "יוצר את תיקיית הסטודיו והכלים" | seconds |
| ffmpeg | "מוריד את ffmpeg — מנוע הווידאו והסאונד" | ~1 min (~60 MB) |
| node | "מוריד את Node.js — מה שמריץ את מנוע האנימציות" | ~1 min (~50 MB) |
| remotion | "מתקין את Remotion — מנוע העריכה והאנימציות, ודפדפן רינדור" | 2–8 min |
| transcription | "בודק את החומרה ומתקין את מודל התמלול העברי (ivrit.ai)" | 3–10 min (1.7 GB) |
| effects | "מוריד ספריית סאונדים ואימוג'ים חינמיים לשימוש מסחרי" | ~1 min |
| demo | "מייצר סרטון בדיקה קצר מקצה לקצה" | 1–2 min |

Long steps: run in the background if your harness supports it and check back; otherwise use a
long command timeout (30–60 min). Tell the member it's fine to wait.

## 4. Reading the wizard's output

One JSON line per step:
- `"status": "done"` → move on, one-line update to the member.
- `"status": "needs_user", "hint_he": "..."` → relay the Hebrew hint (it's written for the
  member), wait for them to do it, then `studio setup --resume`.
- `"status": "failed", "error": "..."` → read the error, check troubleshooting.md, fix and
  `studio setup --step <that step>`. Two failures in a row → explain in Hebrew and offer
  options. Full error text is in `.studio/logs/<step>.log`.
`studio setup --status` shows every step's state; `studio doctor` checks the whole studio.

## 5. The transcription choice (layer 1)

Before the `transcription` step, run `studio doctor` and tell the member the verdict:
- **local** (most computers): "המחשב שלך חזק מספיק — התמלול ירוץ אצלך, חינם ופרטי. הורדה
  חד-פעמית של 1.7GB." → just continue.
- **cloud** (weak machine / Windows on ARM / no disk): explain simply, recommend **Deepgram**
  ($200 free credit, no credit card) and walk them through getting a key (transcription.md §5),
  then `studio setup --step transcription --engine deepgram`.
- The member may override either way (privacy → local; speed → cloud).
Keys go into `api-keys.txt` in the studio folder — the member pastes them there (transcription.md §5).

## 6. After setup — the tour and the first edit

1. Open `output/demo_v1.mp4` for them (Mac: `open`; Windows: `start ""`), and look at its
   contact sheet yourself first.
2. The 4-line tour (in Hebrew):
   - put raw videos in `input/` (or tell me where they are);
   - say what you want ("תערוך לי ריל מהסרטון הזה, עם כתוביות ואפקטים");
   - finished videos appear in `output/`;
   - to watch and tweak on a timeline: "תפתח לי את התצוגה" (Remotion Studio).
3. From now on the member opens Claude Code / Codex **in the studio folder** — the folder's
   AGENTS.md/CLAUDE.md tells any agent how the studio works.
4. Offer the first real edit right away with their own footage.

Permissions: the studio ships `.claude/settings.json` (common studio commands pre-approved,
destructive ones denied) and `.codex/config.toml`. Claude Code users can switch to Auto mode in
the mode selector for fewer prompts; never suggest bypassing permissions entirely.

## 7. Updating and repairing

- `studio doctor` — full health check (JSON + Hebrew summary).
- Repair one part: `studio setup --step <step>` (e.g. `remotion` re-installs packages and
  refreshes the kit; the member's `src/custom/` and projects are never touched).
- New skill version (`studio version` is older than the skill's `scripts/VERSION`, or says
  "unknown"): run the wizard command (§3) from the updated skill folder with `--update` — it
  refreshes tools, docs, the kit and the sound pack (workspace → remotion → effects), creates
  `api-keys.txt` if it's missing, and adds new permission rules to `.claude/settings.json`
  without removing the member's own. AGENTS.md and README.md are refreshed (the previous
  copies stay as `AGENTS.old.md` / `README.old.md`); CLAUDE.md, projects, outputs, keys and
  notes stay as they are.
- Remotion upgrades: deliberate only (`studio npx remotion upgrade`), then render the demo
  again before trusting it.
