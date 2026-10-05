# Animation cookbook — custom Remotion animations

The overlay catalog (edit-plan.md) covers most reels. When the video needs something the
catalog doesn't have — an animated chart, a fake app screen, a map, a product demo, text
behind the speaker — write a custom component. Remotion is React: every frame is a function
of the frame number.

The workspace also has Remotion's **official agent skills** installed (`remotion-best-practices`,
`remotion-markup`, `remotion-captions`, `remotion-multimedia`…) — load them when you write
Remotion code; they are the authoritative API reference and are kept current.

## Contents
1. The contract
2. The six rules of deterministic animation
3. Core patterns (copy-paste)
4. Effects, shapes, paths, Lottie
5. Hebrew text in components
6. Test before you render
7. Ideas that work in reels

---

## 1. The contract

```tsx
// remotion/src/custom/PriceTag.tsx
import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {OverlayProps} from '../kit/overlays/types';
import {fontFamily} from '../kit/theme';

export const PriceTag: React.FC<OverlayProps> = ({ov, theme}) => {
  const frame = useCurrentFrame();            // 0 = the overlay's first frame (its word)
  const {fps, width, height} = useVideoConfig();
  const enter = spring({frame, fps, config: {damping: 12}});
  const out = interpolate(frame, [ov.durationInFrames - 6, ov.durationInFrames], [1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{opacity: out}}>
      <div dir="rtl" style={{position: 'absolute', left: width * 0.5, top: height * 0.3,
        transform: `translate(-50%,-50%) scale(${enter})`, fontFamily: fontFamily(theme.displayFont),
        fontSize: 120 * (width / 1080), color: theme.accent}}>
        {String(ov.text ?? '')}
      </div>
    </AbsoluteFill>
  );
};
```
Register it in `remotion/src/custom/index.ts`:
```ts
import {PriceTag} from './PriceTag';
export const CUSTOM = {PriceTag};
```
Use it in `plan.json`: `{"type": "custom", "component": "PriceTag", "at": {"word": "שקל"}, "dur": 2, "text": "₪99"}`.
Any extra keys you put in the plan arrive in `ov`. Files in `src/custom/` are never
overwritten by studio updates; `src/kit/` is.

## 2. The six rules of deterministic animation

Remotion renders frames in parallel, out of order, in several browser tabs. So:
1. **All motion comes from `useCurrentFrame()`** (via `interpolate`/`spring`). No CSS
   `transition`/`animation`, no `setTimeout`, no `requestAnimationFrame`, no GSAP timelines
   running on their own clock.
2. **No `Math.random()`** — use `random('some-seed')` from `remotion` (same value every render).
3. **Time relative to the element**: inside an overlay, frame 0 is its start. Never drive an
   element's fade-out from `useVideoConfig().durationInFrames` — inside a Sequence that is the
   whole video's length (classic "fade-out starts immediately" bug). Use `ov.durationInFrames`.
4. **Load async data with `useDelayRender()`** (fetch JSON, measure fonts) — render waits.
5. **Assets through `staticFile('library/...')`** — plain `/path` URLs 404.
6. **Video/audio inside components via `@remotion/media`** (`<Video>`, `<Audio>`), with a
   static `trimBefore`. Offsets come from `<Sequence from>` — a frame-dependent trim makes
   garbled, double-speed audio.

## 3. Core patterns

```tsx
// ease in over 10 frames starting at frame 5
const x = interpolate(frame, [5, 15], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  easing: Easing.out(Easing.cubic)});
// bouncy pop
const s = spring({frame, fps, config: {damping: 10, stiffness: 180, mass: 0.6}});
// staggered children
items.map((it, i) => spring({frame: frame - i * 4, fps}))
// typewriter
const shown = text.slice(0, Math.floor(interpolate(frame, [0, 30], [0, text.length], {extrapolateRight: 'clamp'})));
// color change
const c = interpolateColors(frame, [0, 20], ['#ffffff', theme.accent]);
// a sub-timeline inside a component
<Sequence from={15} durationInFrames={30} layout="none"><Child/></Sequence>
```
Helpers already in the kit (`src/kit/anim.ts`): `popIn`, `envelope` (fade in/out),
`exitOut`, `bob` (float), `progress`, `px`, `num`, `str`.

## 4. Effects, shapes, paths, Lottie

- **@remotion/effects** (installed): GPU effects on `<Solid>`, `<Img>`, `<Video>`:
  ```tsx
  import {glow} from '@remotion/effects/glow';
  import {whiteNoise} from '@remotion/effects/white-noise';
  <Img src={staticFile('library/icons/lucide/rocket.svg')} effects={[glow({radius: 20})]} />
  ```
  Check an effect's parameters in `node_modules/@remotion/effects/dist/<name>.d.ts`. Rendering
  uses the GPU renderer set in `remotion.config.ts` (`angle`). If a render hangs on an old
  Windows PC, render with `--gl=swangle`.
- **@remotion/shapes**: `<Star>`, `<Heart>`, `<Triangle>`, `<Callout>`, `<Arrow>`…
- **@remotion/paths**: `evolvePath(progress, d)` draws an SVG path on (see the kit's `Arrow`).
- **@remotion/transitions** presentations can also be used inside components.
- **@remotion/lottie** + JSON (e.g. Noto animated emoji) — see the kit's `Emoji`.
- **Text behind the speaker** (advanced): `@remotion/video-matting` separates the person from
  the background; put text between the two layers. Heavy — test on stills first.

Preview-only caveat: some newer transitions/effects need a Chrome flag to show in the Studio
preview (bookFlip, filmBurn, ripple, crossZoom…). Renders work; the member's preview won't. The
kit sticks to flag-free ones.

## 5. Hebrew text in components

- Container `dir="rtl"`; keep strings in logical order — never reverse, never `row-reverse`.
- Word-by-word layouts: give each word `unicodeBidi: 'isolate'`, and group consecutive English
  words into one `dir="ltr"` run (the kit's `toRuns()` in `src/kit/bidi.ts` does this) —
  otherwise "Claude Code" comes out "Code Claude".
- Latin/number/filename runs inside Hebrew: `<bdi>` or `dir="ltr"` island, otherwise `.pdf`
  renders as `pdf.`.
- Fonts: `fontFamily(theme.font)` from the kit (loads Hebrew subsets, blocks render until loaded).

## 6. Test before you render

1. `studio npx tsc --noEmit` — type errors caught in seconds.
2. `studio build <name>` then `studio stills <name> <sec>` at the middle of your animation and
   at its end. Look at them.
3. Only then render. A broken custom component fails the whole render.

## 7. Ideas that work in reels

App-UI mockups (a chat bubble conversation, a terminal typing a command, a notification
dropping in) · a price tag slamming in · before/after split with a wipe · a bar chart growing on
the number word · a map pin drop · a checklist with strikethroughs · a timer counting down ·
an "X → ✓" swap on the solution word · a phone frame around a screen recording.
