// Small animation vocabulary shared by all overlays. Every motion is driven by the
// frame INSIDE the overlay's own Sequence — never by useVideoConfig().durationInFrames,
// which returns the whole composition length (a classic "fade-out starts at once" bug).
import {Easing, interpolate, spring, useVideoConfig} from 'remotion';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

/** Springy 0→1 entrance (scale-in, pop). */
export const popIn = (frame: number, fps: number, delay = 0, damping = 12) =>
	spring({frame: frame - delay, fps, config: {damping, stiffness: 180, mass: 0.6}});

/** 1→0 over the last `out` frames of an element that lives `dur` frames. */
export const exitOut = (frame: number, dur: number, out = 6) =>
	interpolate(frame, [dur - out, dur], [1, 0], {...clamp, easing: Easing.in(Easing.cubic)});

/** Fade in over `inF` frames and out over `outF` frames. */
export const envelope = (frame: number, dur: number, inF = 5, outF = 6) =>
	Math.min(
		interpolate(frame, [0, inF], [0, 1], clamp),
		interpolate(frame, [dur - outF, dur], [1, 0], clamp),
	);

/** Gentle floating motion for stickers/emoji (pixels). */
export const bob = (frame: number, fps: number, amp = 10, period = 1.6) =>
	Math.sin((frame / fps / period) * Math.PI * 2) * amp;

/** Linear progress 0→1 across [from, to] frames, clamped. */
export const progress = (frame: number, from: number, to: number, ease = Easing.out(Easing.cubic)) =>
	interpolate(frame, [from, to], [0, 1], {...clamp, easing: ease});

/** Positions in plan.json are 0–1 fractions of the frame; convert to px. */
export const px = (fraction: unknown, size: number, fallback: number) =>
	(typeof fraction === 'number' ? fraction : fallback) * size;

export const num = (v: unknown, fallback: number) => (typeof v === 'number' ? v : fallback);
export const str = (v: unknown, fallback: string) => (typeof v === 'string' && v.length > 0 ? v : fallback);

/** Size unit: 1 at 1080 on the SHORT side, so vertical, square and landscape all scale sanely. */
export const useUnit = () => {
	const {width, height} = useVideoConfig();
	return Math.min(width, height) / 1080;
};

/**
 * Width scene content may use. Vertical/square: the frame width. Landscape: a centered column —
 * layouts designed for a phone screen would otherwise stretch across 1920 px and run into the
 * speaker circle.
 */
export const stageWidth = (width: number, height: number) => (width > height ? Math.min(width * 0.7, height * 1.25) : width);
