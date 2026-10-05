// Transitions between segments. Two families (docs: edit-plan.md §6):
//
//  OVERLAP  fade · slide · wipe · flip · clock · iris · push
//           Real two-clip transitions from @remotion/transitions. The clips overlap for the
//           transition's duration, so the edit gets shorter by that much (build_edit.py does
//           the math). Best on silence/B-roll — two voices overlapping sounds bad.
//
//  CUT      flash · whip · zoom · blur · glitch · shake · lightleak
//           Effects that live ON the cut: the timeline does not change, captions and
//           anchors stay exactly on their words. The right default for talking heads.
//
// Only flag-free presentations are used, so Studio preview == final render on every machine.
import {linearTiming, springTiming, type TransitionPresentation} from '@remotion/transitions';
import {clockWipe} from '@remotion/transitions/clock-wipe';
import {fade} from '@remotion/transitions/fade';
import {flip} from '@remotion/transitions/flip';
import {iris} from '@remotion/transitions/iris';
import {pushCut} from '@remotion/transitions/push-cut';
import {slide} from '@remotion/transitions/slide';
import {wipe} from '@remotion/transitions/wipe';
import {Easing, interpolate} from 'remotion';
import type {TransitionSpec} from './types';

export const OVERLAP_TRANSITIONS = ['fade', 'slide', 'wipe', 'flip', 'clock', 'iris', 'push'] as const;
export const CUT_TRANSITIONS = ['flash', 'whip', 'zoom', 'blur', 'glitch', 'shake', 'lightleak'] as const;

type Dir = 'from-left' | 'from-right' | 'from-top' | 'from-bottom';

type AnyPresentation = TransitionPresentation<Record<string, unknown>>;
const any = (p: unknown) => p as AnyPresentation;

export const presentationFor = (t: TransitionSpec, width: number, height: number): AnyPresentation => {
	// RTL audiences read right→left, so "next" enters from the left by default.
	const direction = (t.direction ?? 'from-left') as Dir;
	switch (t.type) {
		case 'slide':
			return any(slide({direction}));
		case 'wipe':
			return any(wipe({direction}));
		case 'flip':
			return any(flip({direction}));
		case 'clock':
			return any(clockWipe({width, height}));
		case 'iris':
			return any(iris({width, height}));
		case 'push':
			return any(pushCut());
		case 'fade':
		default:
			return any(fade());
	}
};

export const timingFor = (t: TransitionSpec) =>
	t.type === 'slide' || t.type === 'flip' || t.type === 'push'
		? springTiming({config: {damping: 200}, durationInFrames: t.durationInFrames})
		: linearTiming({durationInFrames: t.durationInFrames, easing: Easing.inOut(Easing.cubic)});

/**
 * Entry motion of the INCOMING segment for cut transitions (frame = frame inside the segment).
 * Returns CSS for the video layer. The matching overlay (flash, glitch, leak) is drawn by
 * overlays/CutTransition.tsx on top of the cut.
 */
export const cutEntryStyle = (t: TransitionSpec | undefined, frame: number): React.CSSProperties => {
	if (!t || t.overlap) {
		return {};
	}
	const d = Math.max(2, Math.round(t.durationInFrames / 2));
	const p = interpolate(frame, [0, d], [0, 1], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
		easing: Easing.out(Easing.cubic),
	});
	if (p >= 1) {
		return {};
	}
	const sign = t.direction === 'from-right' ? 1 : t.direction === 'from-top' || t.direction === 'from-bottom' ? 0 : -1;
	switch (t.type) {
		case 'whip':
			// small travel + overscale: reads as a fast pan without exposing frame edges
			return {
				transform: `translateX(${sign * (1 - p) * 10}%) scale(${1 + (1 - p) * 0.25})`,
				filter: `blur(${(1 - p) * 26}px)`,
			};
		case 'zoom':
			return {transform: `scale(${1 + (1 - p) * 0.25})`, filter: `blur(${(1 - p) * 10}px)`};
		case 'blur':
			return {filter: `blur(${(1 - p) * 30}px)`};
		case 'shake': {
			const amp = (1 - p) * 28;
			return {transform: `translate(${Math.sin(frame * 2.7) * amp}px, ${Math.cos(frame * 3.1) * amp}px)`};
		}
		default:
			return {};
	}
};

/** Exit motion of the OUTGOING segment (frame counted from the segment's end: 0 = last frame). */
export const cutExitStyle = (t: TransitionSpec | undefined, framesLeft: number): React.CSSProperties => {
	if (!t || t.overlap) {
		return {};
	}
	const d = Math.max(2, Math.round(t.durationInFrames / 2));
	const p = interpolate(framesLeft, [0, d], [1, 0], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
		easing: Easing.out(Easing.cubic),
	});
	if (p <= 0) {
		return {};
	}
	const sign = t.direction === 'from-right' ? -1 : 1;
	switch (t.type) {
		case 'whip':
			return {transform: `translateX(${sign * p * 10}%) scale(${1 + p * 0.25})`, filter: `blur(${p * 26}px)`};
		case 'zoom':
			return {transform: `scale(${1 + p * 0.2})`, filter: `blur(${p * 8}px)`};
		case 'blur':
			return {filter: `blur(${p * 30}px)`};
		default:
			return {};
	}
};
