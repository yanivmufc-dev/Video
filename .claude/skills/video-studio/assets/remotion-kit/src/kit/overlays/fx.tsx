// Full-frame effects. Also used as the visible half of CUT transitions (build_edit.py
// centers them on the cut): flash, lightleak, glitch. Keep them short — 0.3–0.6 s.
import {lightLeak} from '@remotion/effects/light-leak';
import React from 'react';
import {AbsoluteFill, interpolate, random, Solid, useCurrentFrame, useVideoConfig} from 'remotion';
import {num, str} from '../anim';
import type {OverlayProps} from './types';

/** Camera-flash: fast attack, slower release, peak in the middle (on the cut). */
export const Flash: React.FC<OverlayProps> = ({ov}) => {
	const frame = useCurrentFrame();
	const d = ov.durationInFrames;
	const mid = Math.max(1, Math.floor(d / 2));
	const opacity = interpolate(frame, [0, mid, d], [0, num(ov.peak, 0.9), 0], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});
	return <AbsoluteFill style={{backgroundColor: str(ov.color, '#FFFFFF'), opacity}} />;
};

/** Organic warm light leak (Remotion effect, needs the angle GL renderer — set in remotion.config.ts). */
export const LightLeak: React.FC<OverlayProps> = ({ov}) => {
	const frame = useCurrentFrame();
	const {width, height} = useVideoConfig();
	const p = interpolate(frame, [0, ov.durationInFrames], [0, 1], {extrapolateRight: 'clamp'});
	return (
		<AbsoluteFill style={{mixBlendMode: 'screen'}}>
			<Solid
				width={width}
				height={height}
				color="#000000"
				effects={[lightLeak({seed: num(ov.seed, 3), hueShift: num(ov.hueShift, 0), progress: p})]}
			/>
		</AbsoluteFill>
	);
};

/** Digital glitch: displaced color bars + scanlines for a few frames. */
export const Glitch: React.FC<OverlayProps> = ({ov}) => {
	const frame = useCurrentFrame();
	const {width, height} = useVideoConfig();
	const d = ov.durationInFrames;
	const strength = interpolate(frame, [0, d / 2, d], [0.3, 1, 0], {extrapolateRight: 'clamp'});
	const bars = Array.from({length: 9}, (_, i) => {
		const r = (n: number) => random(`glitch-${ov.startFrame}-${frame}-${i}-${n}`);
		return {
			top: r(1) * height,
			h: (0.01 + r(2) * 0.06) * height,
			shift: (r(3) - 0.5) * width * 0.25 * strength,
			color: r(4) > 0.5 ? 'rgba(0,255,240,0.55)' : 'rgba(255,0,140,0.55)',
			show: r(5) < 0.75 * strength,
		};
	});
	return (
		<AbsoluteFill style={{mixBlendMode: 'screen', pointerEvents: 'none'}}>
			{bars.map((b, i) =>
				b.show ? (
					<div
						key={i}
						style={{
							position: 'absolute',
							left: b.shift,
							top: b.top,
							width,
							height: b.h,
							background: b.color,
						}}
					/>
				) : null,
			)}
			<AbsoluteFill
				style={{
					opacity: 0.35 * strength,
					backgroundImage: 'repeating-linear-gradient(0deg, rgba(255,255,255,0.18) 0 2px, transparent 2px 6px)',
				}}
			/>
		</AbsoluteFill>
	);
};

/** Darkened edges — focuses the eye, cinematic mood for a section. */
export const Vignette: React.FC<OverlayProps> = ({ov}) => {
	const frame = useCurrentFrame();
	const fade = interpolate(frame, [0, 8, ov.durationInFrames - 8, ov.durationInFrames], [0, 1, 1, 0], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});
	const color = str(ov.color, '0,0,0');
	return (
		<AbsoluteFill
			style={{
				opacity: fade * num(ov.strength, 0.8),
				background: `radial-gradient(ellipse at center, rgba(${color},0) 45%, rgba(${color},0.85) 100%)`,
			}}
		/>
	);
};

/** Colored wash for a dramatic moment ("the problem"): red by default. */
export const Wash: React.FC<OverlayProps> = ({ov}) => {
	const frame = useCurrentFrame();
	const d = ov.durationInFrames;
	const opacity = interpolate(frame, [0, 4, d - 6, d], [0, num(ov.peak, 0.35), num(ov.peak, 0.35), 0], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});
	return <AbsoluteFill style={{backgroundColor: str(ov.color, '#E00000'), opacity, mixBlendMode: 'multiply'}} />;
};
