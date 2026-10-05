// Drawn graphics: counters, hand-drawn arrows and circles, progress bar.
import {evolvePath} from '@remotion/paths';
import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {envelope, num, popIn, progress, str} from '../anim';
import {fontFamily, OUTLINE} from '../theme';
import type {OverlayProps} from './types';

/** Number that climbs to its value — "10x", "₪5,000", "97%". */
export const Counter: React.FC<OverlayProps> = ({ov, theme}) => {
	const frame = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const k = Math.min(width, height) / 1080;
	const from = num(ov.from, 0);
	const to = num(ov.to, 100);
	const decimals = num(ov.decimals, 0);
	const countFrames = Math.round(num(ov.countDur, 1.1) * fps);
	const value = interpolate(frame, [0, countFrames], [from, to], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
		easing: Easing.out(Easing.cubic),
	});
	const text = value.toLocaleString('en-US', {minimumFractionDigits: decimals, maximumFractionDigits: decimals});
	const landed = frame >= countFrames;
	const p = popIn(frame, fps);
	const size = num(ov.size, 170) * k;
	return (
		<AbsoluteFill style={{opacity: envelope(frame, ov.durationInFrames, 1, 6)}}>
			<div
				dir="ltr"
				style={{
					position: 'absolute',
					left: width * num(ov.x, 0.5),
					top: height * num(ov.y, 0.33),
					transform: `translate(-50%, -50%) scale(${p * (landed ? 1.06 : 1)})`,
					fontFamily: fontFamily(str(ov.font, theme.displayFont)),
					fontSize: size,
					fontVariantNumeric: 'tabular-nums',
					color: str(ov.color, theme.accent),
					whiteSpace: 'nowrap',
					...OUTLINE(Math.round(size / 16)),
				}}
			>
				{str(ov.prefix, '')}
				{text}
				{str(ov.suffix, '')}
			</div>
			{ov.label ? (
				<div
					dir="rtl"
					style={{
						position: 'absolute',
						left: 0,
						right: 0,
						top: height * num(ov.y, 0.33) + size * 0.62,
						textAlign: 'center',
						fontFamily: fontFamily(theme.font),
						fontWeight: 800,
						fontSize: 48 * k,
						color: '#fff',
						...OUTLINE(5 * k),
					}}
				>
					{str(ov.label, '')}
				</div>
			) : null}
		</AbsoluteFill>
	);
};

/** Hand-drawn arrow. x/y = where the tip points (0–1), angle = direction in degrees (90 = down). */
export const Arrow: React.FC<OverlayProps> = ({ov}) => {
	const frame = useCurrentFrame();
	const {width, height} = useVideoConfig();
	const k = Math.min(width, height) / 1080;
	const len = num(ov.length, 260) * k;
	const color = str(ov.color, '#FF2D2D');
	const sw = num(ov.stroke, 16) * k;
	// Shaft drawn along +x ending at the tip (0,0), slight curve like a marker stroke.
	const shaft = `M ${-len} ${len * 0.12} Q ${-len * 0.5} ${-len * 0.18} 0 0`;
	const head = `M ${-len * 0.22} ${-len * 0.16} L 0 0 L ${-len * 0.2} ${len * 0.17}`;
	const pShaft = progress(frame, 0, 9);
	const pHead = progress(frame, 7, 12);
	const s = evolvePath(pShaft, shaft);
	const h = evolvePath(pHead, head);
	const wiggle = Math.sin(frame / 4) * 4 * k;
	return (
		<AbsoluteFill style={{opacity: envelope(frame, ov.durationInFrames, 1, 6)}}>
			<svg width={width} height={height} style={{position: 'absolute', inset: 0, overflow: 'visible'}}>
				<g
					transform={`translate(${width * num(ov.x, 0.5) + wiggle}, ${height * num(ov.y, 0.5)}) rotate(${num(ov.angle, 90)})`}
				>
					<path d={shaft} stroke={color} strokeWidth={sw} fill="none" strokeLinecap="round" {...s} />
					<path d={head} stroke={color} strokeWidth={sw} fill="none" strokeLinecap="round" strokeLinejoin="round" {...h} />
				</g>
			</svg>
		</AbsoluteFill>
	);
};

/** Marker circle drawn around something. x/y = center, w/h = size (fractions of the frame). */
export const Circle: React.FC<OverlayProps> = ({ov}) => {
	const frame = useCurrentFrame();
	const {width, height} = useVideoConfig();
	const k = Math.min(width, height) / 1080;
	const cx = width * num(ov.x, 0.5);
	const cy = height * num(ov.y, 0.5);
	const rx = (width * num(ov.w, 0.4)) / 2;
	const ry = (height * num(ov.h, 0.12)) / 2;
	// An ellipse that overshoots its start by ~15% — reads as hand-drawn.
	const pts: string[] = [];
	for (let i = 0; i <= 64; i++) {
		const t = (i / 64) * Math.PI * 2 * 1.15 - Math.PI * 0.6;
		const wob = 1 + Math.sin(t * 3) * 0.03;
		pts.push(`${cx + Math.cos(t) * rx * wob} ${cy + Math.sin(t) * ry * wob}`);
	}
	const d = `M ${pts[0]} ` + pts.slice(1).map((p) => `L ${p}`).join(' ');
	const p = evolvePath(progress(frame, 0, 12), d);
	return (
		<AbsoluteFill style={{opacity: envelope(frame, ov.durationInFrames, 1, 6)}}>
			<svg width={width} height={height} style={{position: 'absolute', inset: 0}}>
				<path
					d={d}
					stroke={str(ov.color, '#FF2D2D')}
					strokeWidth={num(ov.stroke, 12) * k}
					fill="none"
					strokeLinecap="round"
					{...p}
				/>
			</svg>
		</AbsoluteFill>
	);
};

/** Thin progress bar that fills over the overlay's duration (use dur = whole video). */
export const ProgressBar: React.FC<OverlayProps> = ({ov, theme}) => {
	const frame = useCurrentFrame();
	const {width, height} = useVideoConfig();
	const k = Math.min(width, height) / 1080;
	const p = frame / Math.max(1, ov.durationInFrames - 1);
	const atBottom = ov.position === 'bottom';
	return (
		<AbsoluteFill>
			<div
				style={{
					position: 'absolute',
					left: 0,
					right: 0,
					[atBottom ? 'bottom' : 'top']: 0,
					height: num(ov.thickness, 10) * k,
					background: 'rgba(255,255,255,0.18)',
				}}
			>
				{/* fills right-to-left, like Hebrew reading */}
				<div style={{width: `${p * 100}%`, height: '100%', background: str(ov.color, theme.accent), marginLeft: 'auto'}} />
			</div>
		</AbsoluteFill>
	);
};
