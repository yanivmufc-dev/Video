// Text overlays: hook banner, big title, callout, lower third, CTA, building list.
// All Hebrew-first: dir="rtl", logical order, Latin runs isolated.
import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {bob, envelope, num, popIn, progress, str} from '../anim';
import {toRuns} from '../bidi';
import {fontFamily, OUTLINE} from '../theme';
import type {OverlayProps} from './types';

/** Instagram-style hook: each line on its own rounded color box, top of frame. */
export const Hook: React.FC<OverlayProps> = ({ov, theme}) => {
	const frame = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const k = Math.min(width, height) / 1080;
	const lines = str(ov.text, '').split('\n');
	const out = envelope(frame, ov.durationInFrames, 1, 8);
	return (
		<AbsoluteFill style={{opacity: out}}>
			<div
				dir="rtl"
				style={{
					position: 'absolute',
					top: height * num(ov.y, 0.16),
					left: width * 0.06,
					right: width * 0.06,
					display: 'flex',
					flexDirection: 'column',
					alignItems: 'center',
					gap: 10 * k,
				}}
			>
				{lines.map((line, i) => {
					const p = popIn(frame, fps, i * 4, 13);
					return (
						<span
							key={i}
							style={{
								unicodeBidi: 'isolate',
								background: str(ov.bg, theme.accent),
								color: str(ov.color, '#FFFFFF'),
								fontFamily: fontFamily(str(ov.font, theme.displayFont)),
								fontSize: num(ov.size, 66) * k,
								lineHeight: 1.2,
								padding: `${8 * k}px ${26 * k}px`,
								borderRadius: 18 * k,
								transform: `scale(${p}) rotate(${(1 - p) * -3}deg)`,
								boxShadow: '0 10px 30px rgba(0,0,0,0.25)',
							}}
						>
							{line}
						</span>
					);
				})}
			</div>
		</AbsoluteFill>
	);
};

/** Big statement / chapter title, words rise in one after another. */
export const Title: React.FC<OverlayProps> = ({ov, theme}) => {
	const frame = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const k = Math.min(width, height) / 1080;
	const words = str(ov.text, '').split(/\s+/).filter(Boolean);
	const size = num(ov.size, 112) * k;
	const out = envelope(frame, ov.durationInFrames, 1, 7);
	return (
		<AbsoluteFill style={{opacity: out, justifyContent: 'center'}}>
			<div
				dir="rtl"
				style={{
					position: 'absolute',
					top: height * num(ov.y, 0.4),
					left: width * 0.07,
					right: width * 0.07,
					transform: 'translateY(-50%)',
					display: 'flex',
					flexWrap: 'wrap',
					justifyContent: 'center',
					columnGap: size * 0.28,
					fontFamily: fontFamily(str(ov.font, theme.displayFont)),
					fontSize: size,
					lineHeight: 1.08,
					color: str(ov.color, '#FFFFFF'),
					...OUTLINE(Math.round(size / 14)),
				}}
			>
				{toRuns(words.map((text) => ({text}))).map((run, r) => {
					const renderWord = ({t, i}: {t: {text: string}; i: number}) => {
						const p = popIn(frame, fps, i * 3, 14);
						const isAccent = Array.isArray(ov.accentWords) && (ov.accentWords as string[]).includes(t.text);
						return (
							<span
								key={i}
								style={{
									unicodeBidi: 'isolate',
									display: 'inline-block',
									color: isAccent ? theme.accent : undefined,
									transform: `translateY(${(1 - p) * 40 * k}px)`,
									opacity: Math.min(1, p * 1.4),
								}}
							>
								{t.text}
							</span>
						);
					};
					return run.ltr && run.items.length > 1 ? (
						<span key={`run-${r}`} dir="ltr" style={{display: 'inline-flex', columnGap: size * 0.28}}>
							{run.items.map(renderWord)}
						</span>
					) : (
						run.items.map(renderWord)
					);
				})}
			</div>
		</AbsoluteFill>
	);
};

/** A short callout box anywhere on the frame (x/y = center, 0–1). */
export const Callout: React.FC<OverlayProps> = ({ov, theme}) => {
	const frame = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const k = Math.min(width, height) / 1080;
	const p = popIn(frame, fps);
	const out = envelope(frame, ov.durationInFrames, 1, 6);
	return (
		<AbsoluteFill style={{opacity: out}}>
			<div
				dir="rtl"
				style={{
					position: 'absolute',
					left: width * num(ov.x, 0.5),
					top: height * num(ov.y, 0.3),
					transform: `translate(-50%, -50%) scale(${p}) translateY(${bob(frame, fps, 4)}px)`,
					width: 'max-content',
					maxWidth: width * 0.8,
					background: str(ov.bg, 'rgba(15,15,15,0.92)'),
					color: str(ov.color, '#FFFFFF'),
					fontFamily: fontFamily(str(ov.font, theme.font)),
					fontWeight: 800,
					fontSize: num(ov.size, 50) * k,
					padding: `${14 * k}px ${28 * k}px`,
					borderRadius: 22 * k,
					textAlign: 'center',
					unicodeBidi: 'isolate',
					border: ov.border === false ? undefined : `${4 * k}px solid ${theme.accent}`,
				}}
			>
				{str(ov.text, '')}
			</div>
		</AbsoluteFill>
	);
};

/** Name + role card, slides in from the right (RTL start side). */
export const LowerThird: React.FC<OverlayProps> = ({ov, theme}) => {
	const frame = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const k = Math.min(width, height) / 1080;
	const p = popIn(frame, fps, 0, 18);
	const out = envelope(frame, ov.durationInFrames, 1, 8);
	return (
		<AbsoluteFill style={{opacity: out}}>
			<div
				dir="rtl"
				style={{
					position: 'absolute',
					right: width * 0.06,
					top: height * num(ov.y, 0.46),
					transform: `translateX(${(1 - p) * 110}%)`,
					display: 'flex',
					alignItems: 'stretch',
					gap: 16 * k,
					background: 'rgba(12,12,12,0.88)',
					borderRadius: 20 * k,
					padding: `${16 * k}px ${26 * k}px`,
					fontFamily: fontFamily(str(ov.font, theme.font)),
				}}
			>
				<div style={{width: 10 * k, borderRadius: 6 * k, background: theme.accent}} />
				<div>
					<div style={{color: '#fff', fontWeight: 800, fontSize: num(ov.size, 50) * k, unicodeBidi: 'isolate'}}>
						{str(ov.title, '')}
					</div>
					{ov.subtitle ? (
						<div style={{color: 'rgba(255,255,255,0.75)', fontWeight: 500, fontSize: num(ov.size, 50) * 0.62 * k}}>
							{str(ov.subtitle, '')}
						</div>
					) : null}
				</div>
			</div>
		</AbsoluteFill>
	);
};

/** Call to action: pulsing pill + a tapping hand. */
export const Cta: React.FC<OverlayProps> = ({ov, theme}) => {
	const frame = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const k = Math.min(width, height) / 1080;
	const p = popIn(frame, fps);
	const pulse = 1 + Math.max(0, Math.sin((frame / fps) * Math.PI * 2.2)) * 0.05;
	const tap = interpolate(frame % Math.round(fps * 0.9), [0, 6, 12], [0, 18 * k, 0], {extrapolateRight: 'clamp'});
	const out = envelope(frame, ov.durationInFrames, 1, 6);
	return (
		<AbsoluteFill style={{opacity: out}}>
			<div
				style={{
					position: 'absolute',
					left: '50%',
					top: height * num(ov.y, 0.47),
					transform: `translate(-50%, -50%) scale(${p * pulse})`,
				}}
			>
				<div
					dir="rtl"
					style={{
						background: str(ov.bg, theme.accent),
						color: str(ov.color, '#FFFFFF'),
						fontFamily: fontFamily(str(ov.font, theme.font)),
						fontWeight: 900,
						fontSize: num(ov.size, 60) * k,
						padding: `${16 * k}px ${48 * k}px`,
						borderRadius: 999,
						boxShadow: '0 14px 40px rgba(0,0,0,0.35)',
						whiteSpace: 'nowrap',
						unicodeBidi: 'isolate',
					}}
				>
					{str(ov.text, 'עקבו')}
				</div>
				<div
					style={{
						position: 'absolute',
						left: '12%',
						top: '55%',
						fontSize: 90 * k,
						transform: `translateY(${tap}px) rotate(-12deg)`,
					}}
				>
					{str(ov.hand, '👆')}
				</div>
			</div>
		</AbsoluteFill>
	);
};

/** A list that builds item by item and stays (retention backbone for "3 tips" videos). */
export const List: React.FC<OverlayProps> = ({ov, theme}) => {
	const frame = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const k = Math.min(width, height) / 1080;
	const items = (Array.isArray(ov.items) ? ov.items : []) as Array<string | {text: string; startFrame?: number}>;
	const stagger = Math.round(num(ov.stagger, 0.6) * fps);
	const out = envelope(frame, ov.durationInFrames, 1, 8);
	return (
		<AbsoluteFill style={{opacity: out}}>
			<div
				dir="rtl"
				style={{
					position: 'absolute',
					top: height * num(ov.y, 0.17),
					left: width * 0.08,
					right: width * 0.08,
					display: 'flex',
					flexDirection: 'column',
					gap: 14 * k,
					fontFamily: fontFamily(str(ov.font, theme.font)),
				}}
			>
				{ov.title ? (
					<div style={{color: '#fff', fontWeight: 900, fontSize: 58 * k, ...OUTLINE(5 * k)}}>{str(ov.title, '')}</div>
				) : null}
				{items.map((item, i) => {
					const text = typeof item === 'string' ? item : item.text;
					const at = typeof item === 'string' || item.startFrame === undefined ? i * stagger : item.startFrame;
					const p = progress(frame, at, at + 8);
					if (frame < at) {
						return null;
					}
					return (
						<div
							key={i}
							style={{
								display: 'flex',
								alignItems: 'center',
								gap: 16 * k,
								background: 'rgba(12,12,12,0.86)',
								borderRadius: 18 * k,
								padding: `${12 * k}px ${22 * k}px`,
								transform: `translateX(${(1 - p) * 40}%)`,
								opacity: p,
							}}
						>
							<div
								style={{
									minWidth: 54 * k,
									height: 54 * k,
									borderRadius: 999,
									background: theme.accent,
									color: '#111',
									fontWeight: 900,
									fontSize: 32 * k,
									display: 'flex',
									alignItems: 'center',
									justifyContent: 'center',
								}}
							>
								{ov.numbered === false ? '✓' : i + 1}
							</div>
							<div style={{color: '#fff', fontWeight: 800, fontSize: num(ov.size, 46) * k, unicodeBidi: 'isolate'}}>
								{text}
							</div>
						</div>
					);
				})}
			</div>
		</AbsoluteFill>
	);
};
