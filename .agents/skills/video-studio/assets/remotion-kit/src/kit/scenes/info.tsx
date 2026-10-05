// Information scenes: big number/price, checklist, before/after, steps, icon grid, B-roll title.
// Items can appear on their own spoken word: build_edit.py turns each item's `at` into a
// `startFrame` relative to the scene.
import {evolvePath} from '@remotion/paths';
import {Video} from '@remotion/media';
import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {bob, num, popIn, progress, str, stageWidth} from '../anim';
import {fontFamily} from '../theme';
import type {SceneProps} from './types';

type Item = string | {text: string; icon?: string; sub?: string; startFrame?: number};
const text = (it: Item) => (typeof it === 'string' ? it : it.text);
const at = (it: Item, i: number, stagger: number) =>
	typeof it === 'string' || it.startFrame === undefined ? 8 + i * stagger : it.startFrame;
const url = (s: string) => (s.startsWith('http') ? s : staticFile(s));

const Title: React.FC<{t: unknown; ink: string; accent: string; family: string; k: number; frame: number; fps: number}> = ({
	t,
	ink,
	accent,
	family,
	k,
	frame,
	fps,
}) =>
	t ? (
		<div
			dir="rtl"
			style={{
				fontFamily: family,
				fontSize: 84 * k,
				lineHeight: 1.1,
				color: ink,
				textAlign: 'center',
				transform: `translateY(${(1 - popIn(frame, fps, 2, 14)) * 30 * k}px)`,
				opacity: Math.min(1, popIn(frame, fps, 2) * 1.3),
				unicodeBidi: 'isolate',
			}}
		>
			{String(t)
				.split('*')
				.map((part, i) => (
					<span key={i} style={{color: i % 2 ? accent : undefined}}>
						{part}
					</span>
				))}
		</div>
	) : null;

/** Big number / price. `oldValue` shows a struck-through old price first. */
export const NumberScene: React.FC<SceneProps> = ({ov, theme, ink}) => {
	const frame = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const k = Math.min(width, height) / 1080;
	const stage = stageWidth(width, height);
	const to = num(ov.value, 100);
	const from = num(ov.from, 0);
	const count = Math.round(num(ov.countDur, 1.0) * fps);
	const v = interpolate(frame, [4, 4 + count], [from, to], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
		easing: Easing.out(Easing.cubic),
	});
	const dec = num(ov.decimals, 0);
	const landed = frame >= 4 + count;
	const pulse = landed ? 1 + Math.max(0, Math.sin(((frame - 4 - count) / fps) * Math.PI * 4)) * 0.04 * Math.exp(-(frame - 4 - count) / 20) : 1;
	const strike = progress(frame, 2, 12);
	return (
		<AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
			<div dir="rtl" style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 * k, marginTop: -120 * k}}>
				<Title t={ov.title} ink={ink} accent={theme.accent} family={fontFamily(theme.font)} k={k * 0.8} frame={frame} fps={fps} />
				{ov.oldValue !== undefined ? (
					<div style={{position: 'relative', fontFamily: fontFamily(theme.font), fontWeight: 800, fontSize: 90 * k, color: `${ink}88`}}>
						<span dir="ltr">
							{str(ov.prefix, '')}
							{String(ov.oldValue)}
							{str(ov.suffix, '')}
						</span>
						<div
							style={{
								position: 'absolute',
								left: '-6%',
								top: '52%',
								height: 10 * k,
								width: `${112 * strike}%`,
								background: '#FF3B3B',
								borderRadius: 6,
								transform: 'rotate(-8deg)',
							}}
						/>
					</div>
				) : null}
				<div
					dir="ltr"
					style={{
						fontFamily: fontFamily(theme.font),
						fontWeight: 900,
						fontSize: num(ov.size, 300) * k,
						lineHeight: 1,
						color: theme.accent,
						fontVariantNumeric: 'tabular-nums',
						transform: `scale(${popIn(frame, fps, 0, 10) * pulse})`,
						textShadow: `0 0 ${60 * k}px ${theme.accent}88`,
						whiteSpace: 'nowrap',
					}}
				>
					{str(ov.prefix, '')}
					{v.toLocaleString('en-US', {minimumFractionDigits: dec, maximumFractionDigits: dec})}
					{str(ov.suffix, '')}
				</div>
				{ov.label ? (
					<div
						style={{
							fontFamily: fontFamily(theme.font),
							fontWeight: 800,
							fontSize: 56 * k,
							color: ink,
							textAlign: 'center',
							maxWidth: stage * 0.8,
							opacity: progress(frame, 4 + count, 4 + count + 8),
							unicodeBidi: 'isolate',
						}}
					>
						{str(ov.label, '')}
					</div>
				) : null}
			</div>
		</AbsoluteFill>
	);
};

/** Full-screen checklist: items slide in (on their words) with a drawn check or an emoji. */
export const ListScene: React.FC<SceneProps> = ({ov, theme, ink}) => {
	const frame = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const k = Math.min(width, height) / 1080;
	const stage = stageWidth(width, height);
	const items = (Array.isArray(ov.items) ? ov.items : []) as Item[];
	const stagger = Math.round(num(ov.stagger, 0.5) * fps);
	const card = ink === '#FFFFFF' ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)';
	return (
		<AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
			<div dir="rtl" style={{display: 'flex', flexDirection: 'column', gap: 22 * k, width: stage * 0.84, marginTop: -110 * k}}>
				<Title t={ov.title} ink={ink} accent={theme.accent} family={fontFamily(theme.displayFont)} k={k} frame={frame} fps={fps} />
				{items.map((it, i) => {
					const f0 = at(it, i, stagger);
					if (frame < f0) {
						return null;
					}
					const p = popIn(frame - f0, fps, 0, 14);
					const icon = typeof it === 'string' ? undefined : it.icon;
					const check = evolvePath(progress(frame, f0 + 3, f0 + 11), 'M 6 18 L 15 27 L 32 8');
					return (
						<div
							key={i}
							style={{
								display: 'flex',
								alignItems: 'center',
								gap: 24 * k,
								background: card,
								border: `${2 * k}px solid ${theme.accent}55`,
								borderRadius: 28 * k,
								padding: `${22 * k}px ${28 * k}px`,
								transform: `translateX(${(1 - p) * -30}%)`,
								opacity: Math.min(1, p * 1.5),
							}}
						>
							<div
								style={{
									minWidth: 76 * k,
									height: 76 * k,
									borderRadius: 999,
									background: theme.accent,
									display: 'flex',
									alignItems: 'center',
									justifyContent: 'center',
									fontSize: 44 * k,
								}}
							>
								{icon ? (
									icon
								) : (
									<svg width={40 * k} height={36 * k} viewBox="0 0 38 34">
										<path d="M 6 18 L 15 27 L 32 8" stroke="#fff" strokeWidth={6} fill="none" strokeLinecap="round" strokeLinejoin="round" {...check} />
									</svg>
								)}
							</div>
							<div>
								<div style={{fontFamily: fontFamily(theme.font), fontWeight: 800, fontSize: num(ov.size, 58) * k, color: ink, unicodeBidi: 'isolate'}}>
									{text(it)}
								</div>
								{typeof it !== 'string' && it.sub ? (
									<div style={{fontFamily: fontFamily(theme.font), fontWeight: 500, fontSize: 36 * k, color: `${ink}AA`, unicodeBidi: 'isolate'}}>
										{it.sub}
									</div>
								) : null}
							</div>
						</div>
					);
				})}
			</div>
		</AbsoluteFill>
	);
};

/** Before / after. `before` is on the right (read first in Hebrew), `after` wins on the left. */
export const CompareScene: React.FC<SceneProps> = ({ov, theme, ink}) => {
	const frame = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const k = Math.min(width, height) / 1080;
	const stage = stageWidth(width, height);
	const before = (ov.before ?? {}) as {title?: string; items?: Item[]};
	const after = (ov.after ?? {}) as {title?: string; items?: Item[]};
	const afterStart = typeof ov.afterAtFrame === 'number' ? ov.afterAtFrame : Math.round(num(ov.afterAt, 1.2) * fps);
	const dark = ink === '#FFFFFF';
	const neutral = dark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)';
	const neutralBorder = dark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.15)';
	const col = (side: typeof before, good: boolean, start: number) => {
		const p = popIn(frame - start, fps, 0, 14);
		if (frame < start) {
			return <div style={{flex: 1}} />;
		}
		return (
			<div
				style={{
					flex: 1,
					background: good ? `${theme.accent}22` : neutral,
					border: `${3 * k}px solid ${good ? theme.accent : neutralBorder}`,
					borderRadius: 30 * k,
					padding: `${28 * k}px ${22 * k}px`,
					transform: `translateY(${(1 - p) * 80 * k}px) scale(${good ? 1 + 0.03 * p : 1})`,
					opacity: Math.min(1, p * 1.4),
					filter: good ? undefined : 'saturate(0.3)',
				}}
			>
				<div style={{fontSize: 90 * k, textAlign: 'center'}}>{good ? '✅' : '❌'}</div>
				<div
					style={{
						fontFamily: fontFamily(theme.displayFont),
						fontSize: 66 * k,
						color: good ? theme.accent : ink,
						textAlign: 'center',
						margin: `${10 * k}px 0 ${20 * k}px`,
						unicodeBidi: 'isolate',
					}}
				>
					{side.title ?? (good ? 'אחרי' : 'לפני')}
				</div>
				{(side.items ?? []).map((it, i) => {
					const f0 = typeof it !== 'string' && it.startFrame !== undefined ? it.startFrame : start + 6 + i * 6;
					return frame >= f0 ? (
						<div
							key={i}
							style={{
								fontFamily: fontFamily(theme.font),
								fontWeight: 700,
								fontSize: 46 * k,
								color: good ? ink : `${ink}99`,
								textDecoration: good ? undefined : 'line-through',
								marginBottom: 12 * k,
								opacity: progress(frame, f0, f0 + 6),
								unicodeBidi: 'isolate',
								textAlign: 'center',
							}}
						>
							{text(it)}
						</div>
					) : null;
				})}
			</div>
		);
	};
	return (
		<AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
			<div dir="rtl" style={{width: stage * 0.9, marginTop: -100 * k}}>
				<Title t={ov.title} ink={ink} accent={theme.accent} family={fontFamily(theme.displayFont)} k={k} frame={frame} fps={fps} />
				<div style={{display: 'flex', gap: 24 * k, marginTop: 30 * k, alignItems: 'stretch'}}>
					{col(before, false, 4)}
					{col(after, true, afterStart)}
				</div>
			</div>
		</AbsoluteFill>
	);
};

/** Steps 1 → 2 → 3, vertical, a line draws down between them. */
export const StepsScene: React.FC<SceneProps> = ({ov, theme, ink}) => {
	const frame = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const k = Math.min(width, height) / 1080;
	const stage = stageWidth(width, height);
	const steps = (Array.isArray(ov.steps) ? ov.steps : []) as Item[];
	const stagger = Math.round(num(ov.stagger, 0.7) * fps);
	return (
		<AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
			<div dir="rtl" style={{width: stage * 0.8, marginTop: -100 * k}}>
				<Title t={ov.title} ink={ink} accent={theme.accent} family={fontFamily(theme.displayFont)} k={k} frame={frame} fps={fps} />
				<div style={{display: 'flex', flexDirection: 'column', gap: 0, marginTop: 30 * k}}>
					{steps.map((st, i) => {
						const f0 = at(st, i, stagger);
						const p = popIn(frame - f0, fps, 0, 13);
						const line = i < steps.length - 1 ? progress(frame, at(steps[i + 1], i + 1, stagger) - 8, at(steps[i + 1], i + 1, stagger)) : 0;
						return (
							<div key={i} style={{display: 'flex', gap: 28 * k, opacity: frame >= f0 ? 1 : 0.18}}>
								<div style={{display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
									<div
										style={{
											width: 96 * k,
											height: 96 * k,
											borderRadius: 999,
											background: frame >= f0 ? theme.accent : 'transparent',
											border: `${4 * k}px solid ${theme.accent}`,
											color: '#fff',
											fontFamily: fontFamily(theme.font),
											fontWeight: 900,
											fontSize: 48 * k,
											display: 'flex',
											alignItems: 'center',
											justifyContent: 'center',
											transform: `scale(${frame >= f0 ? p : 0.9})`,
										}}
									>
										{i + 1}
									</div>
									{i < steps.length - 1 ? (
										<div style={{width: 6 * k, height: 70 * k, background: `${theme.accent}33`, position: 'relative'}}>
											<div style={{position: 'absolute', top: 0, width: '100%', height: `${line * 100}%`, background: theme.accent}} />
										</div>
									) : null}
								</div>
								<div style={{paddingTop: 16 * k}}>
									<div style={{fontFamily: fontFamily(theme.font), fontWeight: 800, fontSize: 56 * k, color: ink, unicodeBidi: 'isolate'}}>
										{text(st)}
									</div>
									{typeof st !== 'string' && st.sub ? (
										<div style={{fontFamily: fontFamily(theme.font), fontSize: 34 * k, color: `${ink}AA`, unicodeBidi: 'isolate'}}>{st.sub}</div>
									) : null}
								</div>
							</div>
						);
					})}
				</div>
			</div>
		</AbsoluteFill>
	);
};

/** Grid of emoji / icons / logos popping in (tools, features, platforms). */
export const IconGridScene: React.FC<SceneProps> = ({ov, theme, ink}) => {
	const frame = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const k = Math.min(width, height) / 1080;
	const stage = stageWidth(width, height);
	const items = (Array.isArray(ov.items) ? ov.items : []) as Array<string | {src?: string; icon?: string; text?: string; startFrame?: number}>;
	const landscape = width > height;
	const cols = num(ov.cols, landscape ? Math.min(items.length, 4) : items.length > 4 ? 3 : 2);
	const rows = Math.ceil(items.length / cols);
	// fit the width AND the height (a 2×2 grid in a 1920×1080 frame would otherwise overflow):
	// a row is ~0.72 cell (the tile) + ~85 px (padding and label), under a ~110 px title
	const cell = Math.min((stage * 0.84) / cols, ((height * 0.7 - 110 * k) / rows - 85 * k) / 0.72);
	return (
		<AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
			<div dir="rtl" style={{width: stage * 0.84, marginTop: -100 * k}}>
				<Title t={ov.title} ink={ink} accent={theme.accent} family={fontFamily(theme.displayFont)} k={k} frame={frame} fps={fps} />
				<div style={{display: 'flex', flexWrap: 'wrap', justifyContent: 'center', marginTop: 24 * k, width: cell * cols, marginInline: 'auto'}}>
					{items.map((it, i) => {
						const f0 = typeof it !== 'string' && it.startFrame !== undefined ? it.startFrame : 6 + i * 4;
						const p = popIn(frame - f0, fps, 0, 9);
						const label = typeof it === 'string' ? undefined : it.text;
						return (
							<div
								key={i}
								style={{
									width: cell,
									boxSizing: 'border-box',
									display: 'flex',
									flexDirection: 'column',
									alignItems: 'center',
									padding: 14 * k,
									transform: `scale(${frame >= f0 ? p : 0}) translateY(${bob(frame + i * 7, fps, 6)}px)`,
								}}
							>
								<div
									style={{
										width: cell * 0.72,
										height: cell * 0.72,
										borderRadius: 32 * k,
										background: ink === '#FFFFFF' ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.05)',
										border: `${2 * k}px solid ${theme.accent}44`,
										display: 'flex',
										alignItems: 'center',
										justifyContent: 'center',
										fontSize: cell * 0.38,
									}}
								>
									{typeof it !== 'string' && it.src ? (
										<Img src={url(it.src)} style={{width: '62%', height: '62%', objectFit: 'contain'}} />
									) : typeof it === 'string' ? (
										it
									) : (
										it.icon
									)}
								</div>
								{label ? (
									<div style={{fontFamily: fontFamily(theme.font), fontWeight: 800, fontSize: 36 * k, color: ink, marginTop: 10 * k, textAlign: 'center', unicodeBidi: 'isolate'}}>
										{label}
									</div>
								) : null}
							</div>
						);
					})}
				</div>
			</div>
		</AbsoluteFill>
	);
};

/** Full-screen footage/photo with a title on a soft bottom gradient (Ken Burns on stills). */
export const MediaScene: React.FC<SceneProps> = ({ov, theme}) => {
	const frame = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const k = Math.min(width, height) / 1080;
	const src = str(ov.src, '');
	const isVideo = /\.(mp4|mov|webm|m4v)$/i.test(src);
	const kb = interpolate(frame, [0, ov.durationInFrames], [1.0, 1.1]);
	return (
		<AbsoluteFill>
			{src ? (
				isVideo ? (
					<Video src={url(src)} muted trimBefore={Math.round(num(ov.trim, 0) * fps)} objectFit="cover" style={{position: 'absolute', inset: 0, width: '100%', height: '100%'}} />
				) : (
					<Img src={url(src)} style={{width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${kb})`}} />
				)
			) : null}
			<AbsoluteFill style={{background: `linear-gradient(to top, ${theme.bg}EE 0%, transparent 45%)`}} />
			{ov.title ? (
				<div
					dir="rtl"
					style={{
						position: 'absolute',
						left: width * 0.08,
						right: width * 0.08,
						top: height * num(ov.titleY, 0.16),
						textAlign: 'center',
						fontFamily: fontFamily(theme.displayFont),
						fontSize: num(ov.size, 100) * k,
						lineHeight: 1.08,
						color: '#fff',
						textShadow: '0 6px 30px rgba(0,0,0,0.6)',
						transform: `translateY(${(1 - popIn(frame, fps, 4, 14)) * 40 * k}px)`,
						opacity: progress(frame, 4, 12),
						unicodeBidi: 'isolate',
					}}
				>
					{String(ov.title)
						.split('*')
						.map((part, i) => (
							<span key={i} style={{color: i % 2 ? theme.accent : undefined}}>
								{part}
							</span>
						))}
				</div>
			) : null}
		</AbsoluteFill>
	);
};

/** Animated bar chart: bars grow (each on its word via `at`), values count up, the biggest glows. */
export const ChartScene: React.FC<SceneProps> = ({ov, theme, ink}) => {
	const frame = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const k = Math.min(width, height) / 1080;
	const stage = stageWidth(width, height);
	const bars = (Array.isArray(ov.bars) ? ov.bars : []) as Array<{label: string; value: number; startFrame?: number}>;
	const max = Math.max(1, ...bars.map((b) => b.value));
	const chartH = height * 0.34;
	const stagger = Math.round(num(ov.stagger, 0.35) * fps);
	return (
		<AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
			<div dir="rtl" style={{width: stage * 0.86, marginTop: -100 * k}}>
				<Title t={ov.title} ink={ink} accent={theme.accent} family={fontFamily(theme.displayFont)} k={k} frame={frame} fps={fps} />
				<div style={{display: 'flex', alignItems: 'flex-end', gap: 26 * k, height: chartH, marginTop: 40 * k, borderBottom: `${3 * k}px solid ${ink}44`}}>
					{bars.map((b, i) => {
						const f0 = b.startFrame !== undefined ? b.startFrame : 8 + i * stagger;
						const p = interpolate(frame, [f0, f0 + 16], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
						// highlight: a bar label ("הקורס") or by default the biggest value
						const top = typeof ov.highlight === 'string' ? b.label === ov.highlight : b.value === max;
						return (
							<div key={i} style={{flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end', height: '100%'}}>
								<div dir="ltr" style={{fontFamily: fontFamily(theme.font), fontWeight: 900, fontSize: 44 * k, color: top ? theme.accent : ink, opacity: p}}>
									{str(ov.prefix, '')}
									{Math.round(b.value * p).toLocaleString('en-US')}
									{str(ov.suffix, '')}
								</div>
								<div
									style={{
										width: '100%',
										height: (b.value / max) * (chartH - 70 * k) * p,
										borderRadius: `${16 * k}px ${16 * k}px 0 0`,
										background: top ? theme.accent : `${ink}33`,
										boxShadow: top ? `0 0 ${40 * k}px ${theme.accent}88` : undefined,
									}}
								/>
							</div>
						);
					})}
				</div>
				<div style={{display: 'flex', gap: 26 * k, marginTop: 14 * k}}>
					{bars.map((b, i) => (
						<div key={i} style={{flex: 1, textAlign: 'center', fontFamily: fontFamily(theme.font), fontWeight: 700, fontSize: 34 * k, color: ink, unicodeBidi: 'isolate'}}>
							{b.label}
						</div>
					))}
				</div>
			</div>
		</AbsoluteFill>
	);
};
