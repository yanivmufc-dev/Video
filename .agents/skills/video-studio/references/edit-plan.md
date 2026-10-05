# plan.json — the edit, in human terms

`projects/<name>/plan.json` is the single file you (the agent) write to describe an edit.
`studio build <name>` compiles it into frames (`edit.json`), and Remotion renders exactly that.
You never compute frame numbers yourself — you say *which word* an effect lands on and the
compiler finds the frame in the final cut.

## Contents
1. Skeleton
2. `segments` — the cut (and punch-ins, reframing, transitions)
3. `captions`
4. Anchors — how `at` works
5. `overlays` — the catalog
6. Transitions (+ their sounds)
7. `sfx` and `music`
8. `theme`, `fixes`
9. A complete example
10. Reading the build output

---

## 1. Skeleton

```json
{
  "format": {"width": 1080, "height": 1920, "fps": 30},
  "style": "punch",
  "look": "punchy",
  "theme": {"accent": "#D97757", "font": "Heebo", "displayFont": "Secular One"},
  "fixes": {"קלוד קוד": "Claude Code", "Cloud Code": "Claude Code"},
  "segments": [ ... ],
  "captions": {"style": "karaoke", "keywords": ["חינם"]},
  "overlays": [ ... ],
  "sfx": [ ... ],
  "music": null
}
```
Formats: Reels/TikTok/Shorts `1080x1920`; YouTube `1920x1080`; square `1080x1080`.

**`style`** — a complete preset (theme colors + fonts, caption style, look, scene background,
default transition). Anything you set explicitly still wins. Presets (tools/studio/styles.json):
`creator` (karaoke, pink keywords) · `punch` (word-by-word punch, yellow active word, grid
scenes) · `minimal` (clean small captions, light scenes, calm) · `cinematic` (film grade,
letterbox, small captions) · `neon` (glowing captions, dark grid, glitches) · `retro` (VHS look,
typewriter captions) · `luxury` (black & gold, serif titles) · `energetic` (huge pop captions,
shakes, saturated). Let the member choose from the **style board** (`studio styles <name>`).
A segment `"transition": "default"` uses the style's transition.

**`look`** — color grade on the speaker footage: `natural`, `punchy`, `cinematic`, `warm`,
`cool`, `bw`, `vintage`, `vhs`, `neon`, `none`. **`letterbox`**: true = cinema bars.
`fps` must equal the fps the clips were ingested at (default 30).

## 2. `segments` — the cut

The kept pieces of the raw clips, in playing order. Times are **source seconds** of that clip
(read them from `transcript.md`, or paste `cuts.json → segments` from `studio cuts`).

```json
{"clip": "clip01", "from": 0.42, "to": 6.30}
{"clip": "clip01", "from": 6.34, "to": 12.2, "zoom": 1.15}
{"clip": "clip02", "from": 3.10, "to": 9.80, "transition": {"type": "whip"}}
{"clip": "clip03", "from": 0.00, "to": 14.0, "fit": "blur"}
{"clip": "clip04", "from": 2.00, "to": 8.00, "focus": [0.35, 0.3]}
```

| Field | Meaning |
|---|---|
| `clip`, `from`, `to` | which ingested clip, and the in/out point in its own seconds |
| `zoom` | punch-in, a *static* jump-cut scale. 1.10–1.25. Never more: the forehead must stay in frame. Top-weighted origin by default (`zoomOrigin: "50% 30%"`) |
| `fit` | `cover` (default, fill the frame), `contain` (whole picture, bars), `blur` (whole picture on a blurred copy of itself — the standard way to put landscape footage in a vertical video) |
| `focus` | `[x, y]` 0–1: which part of a wider picture stays visible in `cover` mode (reframing landscape → vertical; `[0.5, 0.5]` = center). `studio reframe` finds it from the face |
| `volume` | 1 = untouched. Leave the voice alone unless a clip is clearly louder/quieter |
| `transition` | how this segment enters from the previous one — see §6 |

Rules: never cut inside a word (the `studio cuts` output already respects this); keep every
segment ≥ 0.4 s; consecutive segments of the same clip with a small gap = a jump cut, which is
normal for talking heads. Audio gets a 1-frame ramp at every seam automatically (no clicks).

## 3. `captions`

```json
"captions": {"style": "karaoke", "maxWords": 3, "keywords": ["חינם", "Claude"], "y": 0.6}
```

| Field | Default | Notes |
|---|---|---|
| `enabled` | true | `false` = no burned-in captions |
| `style` | `karaoke` | `karaoke` all words shown, active word lights up · `pop` words appear as spoken · `punch` words punch in one by one, spoken word in the accent · `box` active word gets a colored box · `glow` neon glow · `typewriter` letters type out on a dark box · `clean` soft, no outline (minimal/luxury) · `chips` small dark chip · `plain` outlined white |
| `emojis` | {} | `{"חינם": "🎁", "87": "💸"}` — the emoji pops above that word when it's spoken |
| `maxWords` | 3 | words per page (1–4). 1–2 = punchy, 3 = standard, 4 = calm |
| `keywords` | [] | shown in the accent color and bigger. Single words (Hebrew prefixes handled: `"חינם"` also matches `בחינם`), or a full name produced by `fixes` (`"Claude Code"`) |
| `y` | auto | vertical center (0–1). **Leave it out**: with `studio framing` data the build puts captions just under the lowest chin (0.60–0.74) and says so. Set it only to override; the build warns if it sits on the mouth |
| `size` | 78 | px at 1080 wide |
| `font`, `color`, `highlight` | theme | |
| `gapBreak` | 0.26 | a pause this long starts a new page |

Pages never cross a cut and break after punctuation. A word appears in the captions if at least
~0.12 s of it survives the cut (in the segment it overlaps most) — widen a segment slightly if a
spoken word is missing. Pick keywords **with** the member: subject
nouns, numbers, brand names, the promise, CTA verbs — what would be bold in a headline.

## 4. Anchors — how `at` works

Every overlay and sound has `at`. Three forms:

| Form | Meaning |
|---|---|
| `"at": 3.5` | second 3.5 of the **final** video |
| `"at": {"word": "חינם"}` | the moment that word is spoken in the final cut (1st time) |
| `"at": {"word": "חינם", "n": 2}` | …the 2nd time |
| `"at": {"word": "פי 10"}` | multi-word: the first word of that exact phrase |
| `"at": {"word": "חינם", "after": 20}` | first occurrence after second 20 |
| `"at": {"word": "חינם", "offset": -0.15}` | shift (seconds); `"edge": "end"` = when the word ends |
| `"at": {"clip": "clip03", "t": 12.4}` | a source moment (error if it was cut out) |

If a word is not in the final cut, the build stops and lists similar words — fix the plan,
don't guess. Word anchors are the whole point: effects land ON their word.

## 5. `overlays` — the catalog

Common fields: `type`, `at`, `dur` (seconds, default 1.5), optional `sfx` (sound name on the
first frame), `sfxGain` (default 0.6; scene entrances 0.55, items inside a scene 0.5),
`sfxOffset` (seconds), `z` (stacking).
Positions `x`/`y` are 0–1 fractions of the frame — the element's **center**, except `hook`,
`list` and `lowerthird`, where `y` is the **top edge**.

**Where things may go** — the face first, the app UI second:
1. Run `studio framing <name>` once after ingest. It prints where the head is (e.g. "hair 0.22 →
   chin 0.61, x 0.25–0.76"). The build then **warns** for every overlay that covers the head.
2. Text goes **above the hair** (typical band y 0.05–0.19), **below the chin** (captions), or
   **beside the head** (emoji/stickers at x ≈ 0.12–0.18 or 0.82–0.88). The kit's default
   positions assume a small head — always check them against the framing numbers.
3. App UI: keep anything that must be read above y ≈ 0.75 and inside x 0.11–0.89.

**Text**

| type | props | use |
|---|---|---|
| `hook` | `text` (lines split by `\n`), `y`=0.16 (top edge), `bg`, `color`, `size`=66, `font` | opening promise, first 2–4 s. Instagram-style: each line on its own rounded color box |
| `title` | `text`, `y`=0.4, `size`=112, `accentWords` [..], `color`, `font` | big statement / chapter card; words rise in one by one |
| `callout` | `text`, `x`, `y`=0.3, `bg`, `color`, `size`=50, `border`(bool) | a label: "PDF · Excel · Word", a price, a name |
| `lowerthird` | `title`, `subtitle`, `y`=0.46, `size` | who is speaking / product name |
| `cta` | `text`="עקבו", `y`=0.47, `bg`, `hand`="👆" | follow / comment / link — the last seconds |
| `list` | `title`, `items` [strings, or `{"text", "at", "sfx"}`], `y`=0.17 (top edge), `stagger`=0.6, `numbered` | "3 tips" backbone: builds item by item and stays. Give items their own `at` (and `sfx`, e.g. "click") so each appears on its word |

**Graphics**

| type | props | use |
|---|---|---|
| `counter` | `from`, `to`, `decimals`, `prefix`, `suffix`, `label`, `countDur`=1.1, `x`, `y`=0.33, `size`=170 | numbers: "10x", "₪5,000", "97%" |
| `arrow` | `x`, `y` (the tip), `angle` (90 = pointing down), `length`=260, `color`=red, `stroke` | point at something (hand-drawn, draws on) |
| `circle` | `x`, `y`, `w`, `h`, `color`, `stroke` | marker circle around a thing |
| `progress` | `position` top/bottom, `color`, `thickness`; give `at: 0`, `dur: 999` | retention bar across the whole video |

**Media**

| type | props | use |
|---|---|---|
| `broll` | `src`, `layout` `full`/`band`/`top`/`pip`, `trim` (s into the clip), `size`, `x`, `y`, `rotate`, `aspect` | cutaways. `band` = bottom 38% with a soft top edge (never a hard band). Video is always muted |
| `image` / `sticker` | `src`, `x`, `y` (center), `size`=0.3 (width fraction), `rotate`, `shadow` | logos, screenshots, product shots |
| `emoji` | `emoji`, `x`=0.78, `y`=0.3, `size`=0.2, `style` `fluent`/`animated`/`flat` | reactions. Run `studio fetch emoji 🔥` first (the build warns if missing). `animated` needs a credit line in the post caption |

`src` paths: `library/...` (shared library) or a path relative to the project folder
(`assets/screen.png`) — the build copies it where Remotion can read it.

**Full-frame effects**

| type | props | use |
|---|---|---|
| `flash` | `color`=white, `peak`=0.9 | punctuation, a reveal |
| `lightleak` | `seed`, `hueShift` | warm organic leak (0.6–1.2 s) |
| `glitch` | — | digital glitch bars (0.2–0.4 s) |
| `vignette` | `strength`=0.8, `color` ("r,g,b") | focus / mood for a section |
| `wash` | `color`=red, `peak`=0.35 | the "problem" moment |

**Energy**

| type | props | use |
|---|---|---|
| `burst` | `kind` `confetti`/`sparkles`/`emoji` (+`emoji` "💰🔥"), `x`, `y` (origin, default below the frame), `count`, `power`, `spread`, `gravity`; `dur` ~1.5–2 | celebration, money, "free!", a big reveal — shoots up from the bottom |
| `waveform` | `mode` `bars`/`ring`, `x`, `y`, `width`, `height`, `bars`, `size`, `color` | bars/ring that move with the speaker's voice (podcast feel, intros) |

**Your own**: `{"type": "custom", "component": "MyThing", ...props}` — see animation-cookbook.md.

### Scenes — the speaker disappears, the screen takes over

`{"type": "scene", "kind": "...", ...}` covers the whole frame (the voice keeps playing) with an
animated background and one kind of content. This is what makes an edit feel *produced*:
cutaways every few seconds instead of the same talking head. Timing: `at` + `until` (another
word anchor — the scene lasts until that word is said) or `dur`. Captions pause during scenes
(`"hideCaptions": false` to keep them). A `whoosh` plays on entry (`"sfx"` to change, `"none"`).

| kind | props | use it when the speaker says… |
|---|---|---|
| `kinetic` | `mode` `beat` (one phrase at a time, words slam in) / `stack` (lines build up), `keywords` [..], `maxWords` | a key sentence — the spoken words themselves become the picture, synced word by word |
| `statement` | `text` (`\n` lines; `*word*` = accent color), `accentWords`, `kicker` (small line above) | a claim or punchline you want to show verbatim |
| `number` | `value`, `from`, `prefix`, `suffix`, `decimals`, `label`, `oldValue` (struck-through), `title` | a price, a stat, a result |
| `list` | `title`, `items` [{`text`, `icon` (emoji), `sub`, `at`, `sfx`}] | "what you get", features, tips — each item appears on its word |
| `compare` | `title`, `before` {`title`, `items`}, `after` {`title`, `items`, `at` (word anchor — the "after" side appears on it)}, or `afterAt` (s into the scene) | problem vs. solution, old way vs. new way |
| `steps` | `title`, `steps` [{`text`, `sub`, `at`}] | a process: 1 → 2 → 3 |
| `icons` | `title`, `items` [emoji, or {`src`, `icon`, `text`, `at`}], `cols` | tools, platforms, integrations |
| `chat` | `name`, `avatar`, `status`, `messages` [{`from` "me"/"them", `text`, `at`}] | a conversation, a bot, WhatsApp, "it asked me questions" |
| `terminal` | `title`, `lines` [{`text`, `kind` "cmd"/"out"/"ok", `at`}], `charsPerSecond` | commands, code, "it installed / built / ran" |
| `device` | `device` `phone`/`browser`, `src` (screenshot/screen recording) + `scroll` 0–1, or `mock` {`brand`, `title`, `subtitle`, `cta`, `price`, `features`[3], `banner`, `stats`[3], `quote`} (a landing page that builds itself in ~2 s; `stats` and `quote` appear only when given — use the member's real numbers and testimonials), `url`, `caption` | a website/app/screen — real screenshots beat mocks when you have them |
| `media` | `src` (video/photo), `trim`, `title`, `titleY` | B-roll with a title, full screen |
| `chart` | `title`, `bars` [{`label`, `value`, `at`}], `prefix`, `suffix`, `highlight` (a label; default = biggest) | numbers compared: prices, growth, before/after in figures |

Common scene props: `bg` `gradient` / `grid` / `dots` / `spotlight` / `light` (cream) / `solid`
(+`bgColor`) / `media` (+`bgSrc`, blurred); `bgAccent`; `enter` `zoom`/`wipe`/`slide`/`circle`/
`fade`/`cut`; `exit` `fade`/`zoom`/`wipe`/`slide`/`cut`; `speaker: "pip"` keeps the speaker in a
small circle (`pipSize` 0.3 of the frame's short side, so it fits vertical, square and
landscape alike). After `studio framing` the circle is fitted to the head (hair to chin,
centered). `pipPosition` `top-right`/`top-left`/`bottom-right`/`bottom-left` — the default
already avoids each layout's content (icons/list/steps/compare/chart/terminal → bottom-right,
device → bottom-left, chat → top-left, others → top-right); check a still when you override it;
`ink` (text color). In `title`/`caption`, `*word*` marks accent-colored words. Timed entries
inside scenes (`items`, `steps`, `messages`, `lines`, compare items) take their own `at` and
`sfx`. Keep every scene 1.5–6 s; long monologue → alternate speaker ↔ scene.

## 6. Transitions

Put `transition` on the segment that is *entering*: `"transition": "whip"` or
`"transition": {"type": "slide", "dur": 0.4, "direction": "from-right", "sfx": "swipe", "sfxGain": 0.6}`.

| family | types | what happens | when |
|---|---|---|---|
| **CUT** (timeline unchanged) | `flash` `whip` `zoom` `blur` `glitch` `shake` `lightleak` | effect sits on the cut itself; captions/anchors stay exact | talking heads — the default choice |
| **OVERLAP** (crossfade) | `fade` `slide` `wipe` `flip` `clock` `iris` `push` | both clips visible for `dur`; the edit gets shorter by `dur` | B-roll montages, section changes over a pause |

Default sound per transition (override with `"sfx"`, silence with `"sfx": "none"`):

| transition | sound | transition | sound |
|---|---|---|---|
| whip | whip | slide / flip / zoom / blur / lightleak | whoosh |
| flash | shutter | wipe | whoosh-short |
| glitch | glitch | push | whoosh |
| shake | boom | iris | pop |
| fade | (none) | clock | whoosh-short |

The build **warns** when an overlap transition covers speech (two voices at once) — then use a
CUT transition or move the cut into a pause. Don't transition every cut: 2–5 per minute feels
produced; 20 feels like a template. Default direction is `from-left` (RTL: the next thing enters
from the reading end).

## 7. `sfx` and `music`

```json
"sfx": [{"at": {"word": "שלוש"}, "sound": "ding", "gain": 0.6}]
"music": {"src": "library/music/bed.mp3", "volume": 0.12, "duck": 0.5, "fadeOut": 1.5}
```
`sound` = a file name (no extension) from `library/sfx/` — see effects-library.md for the list.
Gains are relative to the voice (voice = 1.0, untouched). Every library sound is leveled to the
same loudness, so one scale fits all: 0.4 subtle · 0.6 normal · 0.8 a hit; the mix is mastered
to −14 LUFS at the end anyway. `studio build` mixes all the effect sounds into one track
(`remotion/public/p/<name>/sfx_mix.wav`) — edit.json's `sfxCues` lists where each one landed. Music is **off by default** (creators add trending
audio in the app); when used it sits low and ducks under speech automatically.

## 8. `theme`, `fixes`

`theme`: `accent` (keywords, banners — take it from the **subject** of the video, not a brand
kit), `text`, `bg`, `font` (captions/UI), `displayFont` (titles). Hebrew fonts available:
Heebo, Rubik, Assistant, Secular One, Suez One, Varela Round, Frank Ruhl Libre, Noto Sans Hebrew,
IBM Plex Sans Hebrew, Karantina, Alef. Display fonts (Secular One, Suez One) have no ₪ sign —
write prices with Heebo/Rubik or as "ש״ח".

`fixes`: speech-recognition corrections for display only (timing untouched). Multi-word keys
work, and a Hebrew prefix is kept: `"קלוד קוד": "Claude Code"` turns `לקלוד קוד` into
`ל-Claude Code`. A fix whose key or result has several words becomes **one caption word**, so a
name never splits across caption pages. Always add brand/product names the speaker uses — the
model writes "Cloud" for "Claude" even with a prompt.
Anchors and `keywords` match the text **after** fixes: use `{"word": "Claude Code"}` (or its
first word, `"Claude"`), not the misheard "Cloud".

## 9. A complete example (a 35 s reel)

```json
{
  "format": {"width": 1080, "height": 1920, "fps": 30},
  "theme": {"accent": "#D97757", "font": "Heebo", "displayFont": "Secular One"},
  "fixes": {"קלוד קוד": "Claude Code", "Cloud Code": "Claude Code"},
  "segments": [
    {"clip": "clip01", "from": 0.10, "to": 6.32},
    {"clip": "clip01", "from": 6.34, "to": 12.25, "zoom": 1.15, "transition": "whip"},
    {"clip": "clip02", "from": 0.00, "to": 5.36, "transition": "flash"},
    {"clip": "clip04", "from": 15.5, "to": 27.2, "transition": "lightleak"}
  ],
  "captions": {"style": "karaoke", "maxWords": 3, "keywords": ["מטורף", "Claude Code", "עוקב", "87"]},
  "overlays": [
    {"type": "hook", "at": 0, "dur": 3.2, "text": "הבעיה הכי מעצבנת\nשל Claude Code"},
    {"type": "emoji", "at": {"word": "מטורף"}, "dur": 1.5, "emoji": "🤯", "sfx": "pop"},
    {"type": "wash", "at": {"word": "נחסם"}, "dur": 1.6, "sfx": "error"},
    {"type": "counter", "at": {"word": "פי"}, "dur": 2.2, "from": 1, "to": 10, "suffix": "x", "sfx": "ding"},
    {"type": "scene", "kind": "kinetic", "at": {"word": "הבעיה"}, "until": {"word": "מהר"}, "bg": "spotlight"},
    {"type": "scene", "kind": "number", "at": {"word": "87"}, "dur": 2.5, "value": 87, "suffix": " ₪", "label": "לכל החיים", "sfx": "cash"},
    {"type": "scene", "kind": "terminal", "at": {"word": "מתקינים"}, "until": {"word": "עובד"}, "speaker": "pip",
     "lines": [{"text": "claude", "at": {"word": "מתקינים"}}, {"text": "Installed ✓", "kind": "ok", "at": {"word": "עובד"}}]},
    {"type": "list", "at": {"word": "צילומי"}, "dur": 5, "title": "מה מקבלים:", "items": [
      {"text": "צילומי מסך", "at": {"word": "צילומי"}},
      {"text": "כל הטיפים", "at": {"word": "הטיפים"}}]},
    {"type": "cta", "at": {"word": "עוקב"}, "dur": 2.8, "text": "שימו עוקב", "sfx": "swipe"},
    {"type": "progress", "at": 0, "dur": 999}
  ]
}
```

## 10. Reading the build output

`studio build` prints an **anchor table** — every effect, the word it resolved to, and its
second in the final video. Read it: a wrong `n` or a word that appears in two places is caught
here, before any render. It also prints where captions were placed and how many transcript
words fell entirely inside cuts. WARNING lines (an overlay covering the face, captions on the
mouth, speech under an overlap transition, missing emoji assets or sounds) must be fixed or
consciously accepted. A PLAN ERROR stops the build and says exactly what to change.
