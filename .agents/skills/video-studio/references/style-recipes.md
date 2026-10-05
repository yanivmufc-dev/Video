# Style recipes — the editing grammar

Values here were **measured** from reference reels frame by frame and survived real client
review rounds — not blog folklore. Use them as defaults; the member's taste and the material
win. When the member brings a reference video, model it (last section) instead of picking a
recipe.

## Contents
1. Laws that hold in every style
2. Recipe A — Punchy creator (Instagram/TikTok native)
3. Recipe B — Cinematic premium
4. Recipe C — Clean educational
5. Long-form YouTube
6. Colors and fonts
7. What clients rejected (don't go there)
8. Modeling a reference video

---

## 1. Laws that hold in every style

- **When the speaker is on screen, the face is fully visible — hair to chin.** A cropped
  forehead is an instant rejection. Punch-ins top-anchored and ≤ 1.25; overlays never cover the
  mouth. **Hiding the speaker completely is fine and often better**: full-screen scenes and
  B-roll cutaways (Recipe D). What's never OK is *half*-covering a face.
- **Something changes at least every ~2 s** — not necessarily a cut: a caption page flipping,
  an element entering, a counter climbing, a punch-in. Measured median hold in strong reels:
  1.5–2 s; longest static run ≤ 2 s. 18–31 cuts/minute in punchy reels.
- **…and leave clean air.** Effect coverage in a premium cut is ~45% of runtime; a pro editor
  left 2.5 s of nothing right before the big "solution" moment. Density is contrast.
- **Every effect lands on its spoken word** (word anchors, never eyeballed seconds).
- **Sound follows picture**: each visual hit has a sound, 8–18 cues per minute, effects one
  notch under the voice (gain ~0.6–0.8), voice untouched, final −14 LUFS.
- **Captions render above everything** except a split-second transition flash — most viewers
  watch muted.
- **Motion comes from content, not from zooming the speaker**: typing, counters, lists
  building, icons dropping, pages flipping.

## 2. Recipe A — Punchy creator

The look of self-edited viral reels: louder, a bit "cheap-trick", retention-first.

| Layer | Setting |
|---|---|
| Hook | `hook` banner, 2–4 short lines, accent box per line, first 3–5 s, above the hair |
| Captions | `karaoke` (or `box`), `maxWords` 2–3, white + keyword accent from the subject (the creator this was measured from used hot pink `#F71C8A` as their own brand), Heebo 900 with outline, placed under the chin (automatic with `studio framing`) |
| Cuts | tight (`studio cuts --mode reel`), jump-cut punch-ins 1.1–1.2 between sentences |
| Effects | emoji pops on emotional words, arrows/circles on screen recordings, `counter` on numbers, `cta` with follow button at the end |
| Transitions | `whip` / `flash` / `zoom` on section changes |
| Sound | pop on stickers, pop/click on keyword pages, whoosh on transitions, ding on numbers; no music (trending audio added in-app) |
| Structure | Hook → problem ("מכירים את זה ש…") → promise ("והנה הפתרון, 100% בחינם") → steps → CTA ("שימו עוקב / כתבו X בתגובות") |

## 2b. Recipe D — Fully produced (ads, explainers, "make it rich")

When the member says "more on screen", "it's too simple", or it's an ad/course promo: the
speaker is the narrator, the screen is the show.

| Layer | Setting |
|---|---|
| Coverage | speaker visible only ~40–55% of the runtime; the rest is **scenes** (edit-plan.md → Scenes) |
| Rhythm | a scene every 5–10 s, each 1.5–6 s; between scenes the speaker shot is short (2–6 s) and busy (captions, emoji, callouts, punch-ins) |
| Something new | every 1–1.5 s — a word slamming in, an item appearing, a counter, a sound |
| Scene choice | follow the words: a claim → `kinetic`/`statement`; a price/stat → `number`; a process → `steps`; features/bonuses → `list` or `icons`; old vs. new → `compare`; "it asked me / chatted" → `chat`; "it built / installed / ran" → `terminal` or `device`; a website/app → `device` with a real screenshot (or `mock`) |
| Variety | never the same kind twice in a row; alternate dark (`gradient`/`grid`/`spotlight`) and `light` backgrounds; `speaker: "pip"` in 1–3 scenes so the face stays present |
| Hook | open on a scene or a big `hook` banner in the first 1–2 s — the first frame should already be interesting |
| Transitions | scenes bring their own entrances (`zoom`, `wipe`, `circle`); between speaker shots use `whip`/`flash`/`glitch` |
| Sound | every scene entrance whooshes (automatic); every item/step/number gets a click/pop/ding; the CTA gets a riser into a pop |
| Ending | a `kinetic` or `statement` CTA scene, then the `cta` button over the speaker |

## 3. Recipe B — Cinematic premium

A professional editor's grammar: the speaker stays hero, effects are atmosphere, meaning is
carried by a few full-frame moments.

| Layer | Setting |
|---|---|
| Captions | `karaoke` or `chips`, calmer (`maxWords` 3), smaller accent use |
| Full-frame moments | the problem: `wash` red + `glitch`; the solution: `flash` + gold/`lightleak`; never two at once — escalate |
| B-roll | `band` with soft edge, short 2–4 s bursts, **subject imagery** (the product, the result, the world of the topic). Generic stock "code on a laptop" reads as filler — clients reject it |
| Numbers | big `counter`, metallic/gold accent color |
| Lower third | one designed `lowerthird` for the product/offer moment, max twice |
| Icons | small (~0.14 width), float flat near the shoulder, 1.5–2 s |
| Transitions | `lightleak` / `flash` at act boundaries; no slides |
| Sound | whoosh on transitions, thud/boom on drama, sparkle/chime on magic, ding on numbers; optional quiet ambient bed only if asked |
| Coverage | ~45% of runtime has an effect; deliberate air before the peak |

## 4. Recipe C — Clean educational

For tutorials, explainers, "3 tips" videos, B2B.

| Layer | Setting |
|---|---|
| Captions | `chips` (small dark chip, 2–3 words) or `plain` |
| Backbone | a `list` that builds item by item on its words and stays on screen |
| Section cards | `title` in the display font at each new part ("שלב 2") |
| Visuals | screen recordings as `pip` or `full`, `arrow`/`circle`/`callout` to point |
| Punch-ins | rare; motion from list items, typing, counters |
| Transitions | `slide` / `wipe` over pauses between sections (overlap is fine there) |
| Sound | soft clicks/ticks for list items, page-turn between sections |

## 5. Long-form YouTube

1920×1080, `--mode youtube` cuts (keeps breathing room), captions optional (`chips` at the
bottom or none — YouTube has its own), chapter `title` cards, B-roll `full` for 3–6 s over
explanations, a `lowerthird` for the speaker in the first minute, `progress` bar optional.
Effects density far lower than reels: a beat every 10–20 s is plenty.

## 6. Colors and fonts

- **Palette = the subject's colors, not a generic brand kit.** A video about Claude Code →
  Claude's clay `#D97757`, cream `#F4F1E9`, ink `#121110`. About money → green/gold. About
  Instagram → its gradient pinks. If the member has a real brand, use it for the accent only.
- Sample real colors from a logo or reference frame (read the hex), don't eyeball.
- Hebrew fonts: captions **Heebo 800–900** (fallback Rubik 800); titles **Secular One**
  (alternatives Suez One, Karantina for a condensed look). Frank Ruhl Libre reads as dated
  newsprint in reels; pixel fonts read as "old and square".
- No CAPS in Hebrew → emphasis = weight + size + color.

## 7. What clients rejected (don't go there)

| Rejected | Why / instead |
|---|---|
| Animated zoom-in on the speaker every ~2 s | "the movements… that's not the way" → static punch-ins at sentence boundaries, motion from content |
| Full-screen blur/overlay hiding the face | the face is the content → band/pip/brief full B-roll |
| Band-cropping a tight selfie (forehead cut) | scale the whole clip instead (`fit: contain/blur`) or pick a different focus |
| "Nice but not enough — I want much more on screen" (club owner, 2026-09) | Recipe D: full-screen scenes for ~half the runtime, the speaker returns between them |
| Generic stock B-roll | subject-specific imagery or a built graphic |
| Hard-edged B-roll band | soft feathered edge (the kit's `band` does this) |
| Pixel/retro fonts, Frank Ruhl for titles | Secular One |
| Brand colors on a video about another subject | the subject's colors |
| Every gap filled with an effect | deliberate air; bursts land harder after calm |

## 8. Modeling a reference video

"Make it like this" is the single biggest quality jump — model, don't invent.

1. `studio new ref-<name>` and `studio ingest ref-<name> <reference.mp4>`.
2. Contact sheets at 0.5 s: `studio sheet projects/ref-<name>/media/clip01.mp4 --every 0.5
   --start 0 --end 20` (in windows of ~20 s). **Read every sheet.** Per event note: what,
   when, where on frame, how long.
3. Transcribe it too — you'll see where effects land relative to words.
4. Sample exact colors from full-resolution frames (don't guess hex values).
5. Cut rhythm: count cuts and punch-ins (scene detection misses same-shot punch-ins — look
   for face-size changes in the sheets).
6. Audio: is there music under the speech gaps? (listen to/measure a pause) → music or not.
7. Write a **delta table** into notes.md: element → their treatment → our overlay/setting →
   what changes. Then build. If the member says "it's not it", measure at a finer resolution
   and compare stills side by side — the gap is always findable.
