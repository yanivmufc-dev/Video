// A full-screen scene: covers the speaker completely (the voice keeps playing), draws an
// animated background and one "kind" of content, with an entrance/exit and optionally the
// speaker in a small circle ("pip"). plan.json: {"type": "scene", "kind": "number", ...}
import {Video} from '@remotion/media';
import React from 'react';
import {AbsoluteFill, interpolate, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {num, str} from '../anim';
import type {OverlayProps} from '../overlays/types';
import {SceneBackground, type BgKind} from './Background';
import {ChartScene, CompareScene, IconGridScene, ListScene, MediaScene, NumberScene, StepsScene} from './info';
import {KineticScene, StatementScene} from './kinetic';
import type {SceneProps} from './types';
import {useVoice} from '../voice';
import {ChatScene, DeviceScene, TerminalScene} from './ui';

export const SCENE_KINDS: Record<string, React.FC<SceneProps>> = {
	kinetic: KineticScene,
	statement: StatementScene,
	number: NumberScene,
	list: ListScene,
	compare: CompareScene,
	steps: StepsScene,
	icons: IconGridScene,
	media: MediaScene,
	chat: ChatScene,
	terminal: TerminalScene,
	device: DeviceScene,
	chart: ChartScene,
};

// where the speaker circle goes by default, away from each layout's content
const PIP_DEFAULT: Record<string, string> = {
	device: 'bottom-left',
	chat: 'top-left',
	icons: 'bottom-right',
	list: 'bottom-right',
	steps: 'bottom-right',
	compare: 'bottom-right',
	chart: 'bottom-right',
	terminal: 'bottom-right',
};

type PipSeg = {
	src: string;
	startFrame: number;
	durationInFrames: number;
	trimBefore: number;
	srcWidth?: number;
	srcHeight?: number;
};

/** The speaker, small, in a circle — follows the real edit (built by build_edit.py). */
const Pip: React.FC<{
	segs: PipSeg[];
	pos: string;
	size: number;
	accent: string;
	focus: [number, number];
	face?: [number, number, number];
	start: number;
}> = ({segs, pos, size, accent, focus, face, start}) => {
	const frame = useCurrentFrame();
	const level = useVoice()(frame + start);
	const {fps, width, height} = useVideoConfig();
	const d = Math.min(width, height) * size; // same visual size in vertical, square, landscape
	const p = spring({frame: frame - 4, fps, config: {damping: 14}});
	const mx = Math.min(width, height) * 0.06;
	const top = pos.startsWith('top') ? Math.max(mx, height * 0.08) : height - d - Math.max(mx, height * 0.07);
	const left = pos.endsWith('left') ? mx : width - d - mx;
	return (
		<div
			style={{
				position: 'absolute',
				top,
				left,
				width: d,
				height: d,
				borderRadius: '50%',
				overflow: 'hidden',
				border: `${Math.round(d * (0.03 + level * 0.03))}px solid ${accent}`,
				boxShadow: `0 20px 50px rgba(0,0,0,0.5), 0 0 ${Math.round(d * level * 0.25)}px ${accent}`,
				transform: `scale(${p})`,
				background: '#000',
			}}
		>
			{segs.map((s, i) => {
				const sw = s.srcWidth ?? 1080;
				const sh = s.srcHeight ?? 1920;
				// with framing data: hair-to-chin fills ~80% of the circle, centered on the face;
				// the picture always covers the whole circle
				const cover = Math.max(d / sw, d / sh);
				const scale = face ? Math.max(cover, (0.8 * d) / ((face[2] - face[1]) * sh)) : cover;
				const w = sw * scale;
				const h = sh * scale;
				const cx = face ? face[0] : focus[0];
				const cy = face ? (face[1] + face[2]) / 2 : focus[1];
				const lx = Math.min(0, Math.max(d - w, d / 2 - cx * w));
				const ty = Math.min(0, Math.max(d - h, d / 2 - cy * h));
				return (
					<Sequence key={i} from={s.startFrame} durationInFrames={s.durationInFrames} layout="none">
						<div style={{position: 'absolute', width: w, height: h, left: lx, top: ty}}>
							<Video
								src={s.src.startsWith('http') ? s.src : staticFile(s.src)}
								trimBefore={s.trimBefore}
								muted
								objectFit="fill"
								style={{position: 'absolute', inset: 0, width: '100%', height: '100%'}}
							/>
						</div>
					</Sequence>
				);
			})}
		</div>
	);
};

const enterStyle = (kind: string, frame: number, fps: number): React.CSSProperties => {
	const p = spring({frame, fps, config: {damping: 200}, durationInFrames: 10});
	switch (kind) {
		case 'cut':
			return {};
		case 'fade':
			return {opacity: p};
		case 'slide':
			return {transform: `translateX(${(1 - p) * -100}%)`};
		case 'wipe':
			return {clipPath: `inset(0 0 0 ${(1 - p) * 100}%)`};
		case 'circle':
			return {clipPath: `circle(${p * 80}% at 50% 50%)`};
		case 'zoom':
		default:
			return {transform: `scale(${1.18 - 0.18 * p})`, opacity: Math.min(1, p * 1.6)};
	}
};

const exitStyle = (kind: string, framesLeft: number): React.CSSProperties => {
	const p = interpolate(framesLeft, [0, 6], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	if (p <= 0 || kind === 'cut') {
		return {};
	}
	switch (kind) {
		case 'slide':
			return {transform: `translateX(${p * 100}%)`};
		case 'wipe':
			return {clipPath: `inset(0 ${p * 100}% 0 0)`};
		case 'zoom':
			return {transform: `scale(${1 + p * 0.12})`, opacity: 1 - p};
		case 'fade':
		default:
			return {opacity: 1 - p};
	}
};

export const Scene: React.FC<OverlayProps> = ({ov, theme}) => {
	const frame = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const kind = str(ov.kind, 'statement');
	const Comp = SCENE_KINDS[kind];
	if (!Comp) {
		throw new Error(`Unknown scene kind "${kind}". Known: ${Object.keys(SCENE_KINDS).join(', ')}`);
	}
	const bg = str(ov.bg, kind === 'media' ? 'solid' : 'gradient') as BgKind;
	const ink = str(ov.ink, bg === 'light' ? '#121110' : '#FFFFFF');
	const enter = enterStyle(str(ov.enter, 'zoom'), frame, fps);
	const exit = exitStyle(str(ov.exit, 'fade'), ov.durationInFrames - 1 - frame);
	const transform = [enter.transform, exit.transform].filter(Boolean).join(' ') || undefined;
	const opacity = (typeof enter.opacity === 'number' ? enter.opacity : 1) * (typeof exit.opacity === 'number' ? exit.opacity : 1);
	const hasPip = Array.isArray(ov.pipSegments) && ov.pipSegments.length > 0;
	const pipPos = str(ov.pipPosition, PIP_DEFAULT[kind] ?? 'top-right');
	const short = Math.min(width, height);
	const reserve = hasPip && width > height ? short * num(ov.pipSize, 0.3) + short * 0.12 : 0;
	return (
		<AbsoluteFill style={{...enter, ...exit, transform, opacity, overflow: 'hidden'}}>
			<SceneBackground
				kind={bg}
				accent={str(ov.bgAccent, theme.accent)}
				base={typeof ov.bgColor === 'string' ? ov.bgColor : undefined}
				src={typeof ov.bgSrc === 'string' ? ov.bgSrc : undefined}
			/>
			{/* landscape + speaker circle: the content moves aside and the circle gets its own strip */}
			<AbsoluteFill style={reserve ? {width: 'auto', [pipPos.endsWith('left') ? 'left' : 'right']: reserve} : undefined}>
				<Comp ov={ov} theme={theme} ink={ink} />
			</AbsoluteFill>
			{hasPip ? (
				<Pip
					segs={ov.pipSegments as PipSeg[]}
					pos={pipPos}
					size={num(ov.pipSize, 0.3)}
					accent={theme.accent}
					focus={(Array.isArray(ov.pipFocus) ? ov.pipFocus : [0.5, 0.33]) as [number, number]}
					face={(Array.isArray(ov.pipFace) ? ov.pipFace : undefined) as [number, number, number] | undefined}
					start={ov.startFrame}
				/>
			) : null}
		</AbsoluteFill>
	);
};
