# Editing a video — from raw footage to a finished file

The whole loop, for any raw material: a talking-head reel, a long YouTube video, a podcast
clip, a screen recording with voice, several phone clips of one message. Commands are shown
as `studio <cmd>` — on Mac run `./studio <cmd>`, on Windows `.\studio.cmd <cmd>`, always
from the studio folder.

## Contents
1. The principle
2. Intake — find and ingest the footage
3. Transcribe, then read it
4. The brief (one short interview)
5. The cut — tighten and choose takes
6. The creative plan
7. Build + stills gate
8. Render, master, verify
9. Deliver and iterate
10. Long-form, multi-clip, landscape and other material

---

## 1. The principle

**You never watch the video. You read it.** A word-level transcript (≈10 KB) tells you
everything you need to cut and to place effects; frames are looked at only at decision points
(contact sheets, stills). This is how the leading agent editors work, and it's why a laptop
can do this at all.

**Ask → confirm → execute → verify → show.** Never touch the cut before the member approves
the plan in plain Hebrew. Never show the member anything you haven't looked at yourself first.

**Everything hangs on words.** Cuts snap to word boundaries, captions come from the words,
every effect is anchored to the word it illustrates. No magic numbers.

## 2. Intake

1. Find the footage. Default place: the studio's `input/` folder. If the member points at a
   file elsewhere (Desktop, Downloads, WhatsApp export), use that path directly; files with
   Hebrew names or spaces are fine — ingest makes clean copies.
2. Create the project: `studio new <short english name>` → `projects/<name>/`. Use an English
   slug even for Hebrew videos (e.g. `claude-tips`), it becomes the composition id.
3. Ingest every clip, in the order the member recorded them:
   `studio ingest <name> input/IMG_4412.MOV input/IMG_4413.MOV`
   This makes `media/clip01.mp4…` — CFR 30 fps, H.264, SDR (iPhone HDR is tone-mapped),
   ≤1920 px, rotation baked in, AAC 48 kHz — and prints each clip's size and duration.
   Use `--fps 25` only if the member shoots PAL/cinema and wants to keep it.
4. Look once: `studio sheet projects/<name>/media/clip01.mp4 --count 8 --grid` and open the
   image (it lands in `projects/<name>/sheets/`). You now know framing, lighting, background.
5. Measure the face: `studio framing <name>`. It prints where the head is in each clip (hair →
   chin, left → right). The build uses it to put captions under the chin and to warn when any
   overlay covers the face; for landscape clips it also finds the crop (`--apply` writes `focus`).

## 3. Transcribe, then read it

`studio transcribe <name> --prompt "names, brands, terms the speaker uses"`
→ `transcripts/clipNN.words.json` (cached) + `transcript.md` (the readable version).

Read `transcript.md` fully. It shows each phrase with its source times, pauses (`⏸ 1.2s`),
hesitations (`~אה~`), soft fillers (`(כאילו)`) and suspected retakes (`↺ L12`).

Then read the key lines back to the member in Hebrew and ask about names: speech recognition
confuses brand names ("Cloud" for "Claude"), people's names and English terms. Every fix goes
into `plan.json → fixes`. The member catches these in seconds; you won't.

## 4. The brief

One interview, not a drip of questions (use the question tool if you have one; otherwise a
short numbered list). Adapt to what you saw — typical:

- **Where will it be published?** Reels/TikTok/Shorts (1080×1920) · YouTube (1920×1080) · both.
- **Target length?** Offer a concrete number from the transcript ("the raw is 2:10; a tight
  reel would be ~55 s").
- **Style — show, don't ask in the abstract.** Run `studio styles <name>` (≈20 s): it renders
  the member's OWN footage in all 8 style presets (speaker frame + a scene frame each) into
  `projects/<name>/sheets/style_board.png` with numbers. Look at it yourself, open it for the
  member (Mac `open <file>`, Windows `start "" <file>`), and ask which number they like (the
  names and one-line descriptions are in `sheets/style_board.json`). Mixing is fine ("the
  captions of 2 with the colors of 5") — set `style` and override `captions`/`theme`/`look`.
  Or "I have a reference video" → teardown (style-recipes.md).
- **How wild?** Offer the extras explicitly — members don't know they exist: full-screen scenes
  (kinetic text, charts, chat, terminal, a landing page that builds itself), the speaker in a
  circle, confetti/emoji bursts on key words, emoji over caption words, voice-reactive bars,
  a film look / VHS / letterbox.
- **Captions?** Yes by default (most people watch muted). Style + which words to highlight.
- **Colors** — from the subject (a video about Claude → Claude's clay; about money → green/gold),
  or the member's brand if they insist.
- **CTA?** Ask for it in their words: follow / comment a word / link in bio / a product.
  The CTA is the member's promise to their audience, so it comes from them. No answer → the
  video ends on the last strong line, without a CTA.
- **Music?** Default no — trending audio is added inside Instagram/TikTok. If yes, see
  effects-library.md for safe sources.

Write the answers to `projects/<name>/notes.md` (a "Brief" section). Every later session
starts by reading notes.md.

## 5. The cut

`studio cuts <name>` (or `--mode youtube` for natural pacing) writes `cuts.md` + `cuts.json`:
- **automatic**: pauses (found in the audio — Whisper's timestamps hide them), head/tail
  silence, hesitation sounds;
- **proposed** (numbered P1…): retakes (keeps the LAST take — people repeat a sentence because
  the first try failed), repeated words (stutter vs. emphasis!), isolated discourse fillers.

Show the member a short Hebrew summary: "the raw is 2:10, after removing pauses 1:48; I found
2 retakes and one 'כאילו' — shall I remove P1 and P3?". Apply the approved ones:
`studio cuts <name> --apply P1,P3`, then paste `cuts.json → segments` into `plan.json`.

Then edit the **story**, which no script does for you: which sentences serve the target
length and the promise of the hook? For reels, the strongest line often moves to the top (a
cold open), and everything that doesn't pay off the hook goes. Propose this in 4–8 plain
sentences ("I open with 'saved me 7 hours', then the problem, the 3 steps, and end on the
follow CTA — 52 s") and wait for a yes.

## 6. The creative plan

With the story approved, plan the layers (style-recipes.md has the grammar):

0. **Layout first**: from the framing numbers, decide the zones — text above the hair, captions
   below the chin, emoji/stickers beside the head. The kit's default positions assume a small
   head; a close selfie needs higher titles and lower captions.
1. **Hook** (0–3 s): banner with the promise and/or a strong visual on the first word.
2. **Captions**: style + keywords.
3. **Coverage plan** (before the beats): go through the transcript line by line and mark which
   lines are *speaker* and which become a *scene* (edit-plan.md → Scenes) — what would a
   motion designer show here? Default to Recipe D density unless the member asked for a calm,
   personal video. Write the plan as a table in notes.md (time range → speaker/scene kind).
3b. **Beats**: pick the words that deserve an effect — numbers (counter), names/products
   (logo/sticker/callout), emotions (emoji), the problem (wash/glitch), the solution
   (title/flash), lists (list overlay), the CTA. Rhythm law: something changes on screen at
   least every ~2 s, but leave deliberate clean air — contrast is what makes a beat land.
4. **Punch-ins**: 1.1–1.25 on emphasis sentences (a jump cut, never an animated zoom).
5. **Transitions**: at section changes only, 2–5 per minute, with their sound.
6. **Sound**: every visual event that "hits" gets a matching sound; pops for stickers,
   whooshes for movement, ding for numbers. Voice stays untouched; effects sit under it.
7. **B-roll** (if any): subject-specific, never generic stock "filler".

Write it all into `plan.json` (edit-plan.md is the full reference). For a beat you can't make
with the catalog, write a custom component (animation-cookbook.md).

## 7. Build + stills gate

1. `studio build <name>` — read the anchor table, the caption placement line and every WARNING
   (face covered, captions on the mouth, speech under a transition). Fix, rebuild.
2. `studio stills <name> 1.2,4.5,9.8,...` — render 4–8 single frames (half resolution, fast)
   at the strongest moments
   (hook, a caption with a keyword, each big effect at its MIDDLE — not its first frame, a
   fade-in 2% in looks like a bug — the CTA).
3. **Look at every still yourself first.** Check: face fully visible (hair to chin), captions
   readable and inside the safe area, nothing covering the mouth, Hebrew order correct, colors
   right, long captions not wrapping into 3 lines (use `maxWords: 2` if they do). Fix what's wrong.
4. Show the stills to the member and ask for approval **before** the full render. This gate
   exists because full renders that skipped it came back rejected.

For a quick moving preview: `studio render <name> --draft` (half resolution, fast), or open
`studio preview` (Remotion Studio in the browser — the member can scrub the timeline).

## 8. Render, master, verify

`studio render <name>` does all three:
- Remotion render (H.264, BT.709) → `projects/<name>/renders/`
- two-pass loudness master to −14 LUFS, true peak ≤ −1 dBTP (voice untouched, level only)
- verify: format, size, duration vs. plan, loudness, black frames, frozen picture, silence
  gaps, and a 12-frame contact sheet → `output/<name>_vN.mp4` (+ `_sheet.png`). A frozen
  picture is a WARN (a still title card is fine) — look at that moment, it doesn't block.
- share copy: `output/<name>_vN_share.mp4` — same picture and sound at about a third of the
  size (fits WhatsApp, fast to upload; Instagram/TikTok re-encode anyway)

Renders take roughly 1–2× the video length on a modern laptop; run them in the background if
your harness allows and keep talking to the member. **Open the contact sheet and look.** If any
check FAILS, fix before showing. Verify also that the output file is new (its time), not a
stale file from a previous version.

## 9. Deliver and iterate

Tell the member where the file is — the `_share.mp4` is the one to send and upload; the
master (`output/<name>_v1.mp4`) is the full-quality archive copy — what's in it (one line per
layer), and ask what to change. Every round is a new version (`_v2`, `_v3`) — keep the old
ones; people ask for "the one from before". For a tiny fix the member wants in place (a typo),
`studio render <name> --replace` overwrites the latest version instead.

Feedback → change `plan.json` → build → stills of the changed moments → render. Don't
re-transcribe (cached) and don't re-ingest. Append each round to `notes.md` ("v2: hook
shorter, removed the red wash — 'too aggressive'"). When the same feedback appears twice,
it's a rule for this member: write it under "Preferences" in notes.md and apply it
unprompted next time.

If any asset needs credit (Noto animated emoji), `studio fetch credits projects/<name>`
prints the line for the post caption.

## 10. Other material

- **Several clips / takes**: ingest all; `transcript.md` shows each clip; pick the best take of
  each beat across clips and order the segments by story, not by file order.
- **Long-form (YouTube 10–40 min)**: `--mode youtube` cuts; format 1920×1080; captions often
  `chips` or off (YouTube has its own); fewer effects, chapter `title` cards at section changes;
  transcription on a weak computer → cloud engine (transcription.md).
- **Landscape footage → vertical**: `fit: "blur"` (whole frame on a blurred fill) or
  `fit: "cover"` + `focus` from `studio reframe <name>` (follows the face). Check stills —
  two people in frame usually want `blur` or alternating focus per segment.
- **Podcast / two speakers**: one segment per speaker turn with its own `focus`; captions stay
  single-line (`maxWords: 2`).
- **Screen recordings**: keep them `contain` or `pip`; use `arrow`/`circle`/`callout` to point;
  zooms are fine on screens (never on faces beyond 1.25).
- **Audio-only / voice-over**: ingest makes a black picture; build the visuals from B-roll,
  titles and lists.
- **Reference video ("make it like this")**: ingest it into a separate project, contact
  sheets every 0.5 s, measure (cut rhythm, caption style, colors — sample real hex values),
  write a delta table, THEN build. See style-recipes.md → "Modeling a reference".
