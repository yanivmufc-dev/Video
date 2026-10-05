// Kinetic typography: the speaker disappears and the spoken words hit the screen, big,
// on the exact frame they're said (build_edit.py passes the words of the scene's time range).
import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {num, popIn, str, stageWidth} from '../anim';
import {isLtr, splitTrailingPunct, toRuns} from '../bidi';
import {fontFamily, OUTLINE} from '../theme';
import type {SceneProps} from './types';

type W = {text: string; startFrame: number; endFrame: number; keyword?: boolean};

/** Group words into beats: a keyword stands alone, a beat ends after punctuation or 3 words. */
const beats = (words: W[], maxWords: number): W[][] => {
	const out: W[][] = [];
	let cur: W[] = [];
	for (const w of words) {
		const prev = cur[cur.length - 1];
		if (cur.length && (cur.length >= maxWords || w.keyword || prev?.keyword || /[.,!?:…]$/.test(prev?.text ?? ''))) {
			out.push(cur);
			cur = [];
		}
		cur.push(w);
	}
	if (cur.length) {
		out.push(cur);
	}
	return out;
};

export const KineticScene: React.FC<SceneProps> = ({ov, theme, ink}) => {
	const frame = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const k = Math.min(width, height) / 1080;
	const stage = stageWidth(width, height);
	const words = ((ov.words as W[]) ?? []).filter((w) => w.text.trim());
	const mode = str(ov.mode, 'beat');
	const groups = beats(words, num(ov.maxWords, 3));
	const family = fontFamily(str(ov.font, theme.displayFont));

	if (mode === 'stack') {
		// lines build up; the newest line is bright, older ones dim; keeps the last 4 lines
		const shown = groups.filter((g) => frame >= g[0].startFrame);
		const visible = shown.slice(-4);
		return (
			<AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
				<div dir="rtl" style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18 * k, width: stage * 0.84}}>
					{visible.map((g, i) => {
						const latest = i === visible.length - 1;
						const p = popIn(frame - g[0].startFrame, fps, 0, 12);
						return (
							<div
								key={g[0].startFrame}
								style={{
									fontFamily: family,
									fontSize: num(ov.size, 110) * k,
									lineHeight: 1.05,
									color: latest ? ink : `${ink}66`,
									transform: `translateY(${(1 - p) * 60 * k}px) scale(${latest ? 1 : 0.92})`,
									opacity: Math.min(1, p * 1.5),
									textAlign: 'center',
									unicodeBidi: 'isolate',
								}}
							>
								{g.map((w, j) => (
									<span key={j} style={{color: w.keyword ? theme.accent : undefined}}>
										{(j ? ' ' : '') + w.text}
									</span>
								))}
							</div>
						);
					})}
				</div>
			</AbsoluteFill>
		);
	}

	// 'beat' mode: one beat at a time, each word slams in on its frame
	const idx = groups.findIndex((g, i) => frame >= g[0].startFrame && (i === groups.length - 1 || frame < groups[i + 1][0].startFrame));
	const g = idx >= 0 ? groups[idx] : null;
	if (!g) {
		return null;
	}
	const chars = g.map((w) => w.text).join(' ').length;
	const size = Math.min(num(ov.size, 170), (0.9 * 1080) / Math.max(4, chars * 0.52)) * k;
	return (
		<AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
			<div
				dir="rtl"
				style={{
					display: 'flex',
					flexWrap: 'wrap',
					justifyContent: 'center',
					alignItems: 'baseline',
					columnGap: size * 0.28,
					width: stage * 0.88,
					marginTop: -height * 0.04,
				}}
			>
				{toRuns(g).map((run, r) => {
					// consecutive English words form one left-to-right run (else "Claude Code" flips)
					const items = run.items.map(({t: w, i: j}) => {
						const s = spring({frame: frame - w.startFrame, fps, config: {damping: 11, stiffness: 220, mass: 0.5}});
						const shown = frame >= w.startFrame;
						const [core, punct] = isLtr(w.text) ? splitTrailingPunct(w.text) : [w.text, ''];
						return (
							<span
								key={j}
								style={{
									unicodeBidi: 'isolate',
									display: 'inline-block',
									fontFamily: family,
									fontSize: w.keyword ? size * 1.15 : size,
									lineHeight: 1.05,
									color: w.keyword ? theme.accent : ink,
									opacity: shown ? 1 : 0.12,
									transform: `scale(${shown ? interpolate(s, [0, 1], [1.35, 1]) : 1}) rotate(${shown ? (1 - s) * (j % 2 ? 4 : -4) : 0}deg)`,
									...(ink === '#FFFFFF' ? OUTLINE(Math.round(size / 28)) : {}),
								}}
							>
								{core}
								{punct}
							</span>
						);
					});
					return run.ltr && run.items.length > 1 ? (
						<span key={`r${r}`} dir="ltr" style={{display: 'inline-flex', columnGap: size * 0.28}}>
							{items}
						</span>
					) : (
						items
					);
				})}
			</div>
		</AbsoluteFill>
	);
};

/** A fixed statement (not synced word-by-word): lines rise in, accent words colored. */
export const StatementScene: React.FC<SceneProps> = ({ov, theme, ink}) => {
	const frame = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const k = Math.min(width, height) / 1080;
	const stage = stageWidth(width, height);
	const lines = str(ov.text, '').split('\n');
	const accent = (Array.isArray(ov.accentWords) ? ov.accentWords : []) as string[];
	const size = num(ov.size, 120) * k;
	return (
		<AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
			<div dir="rtl" style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 * k, width: stage * 0.86}}>
				{ov.kicker ? (
					<div
						style={{
							fontFamily: fontFamily(theme.font),
							fontWeight: 800,
							fontSize: 44 * k,
							color: theme.accent,
							letterSpacing: 1,
							opacity: popIn(frame, fps),
							unicodeBidi: 'isolate',
						}}
					>
						{str(ov.kicker, '')}
					</div>
				) : null}
				{lines.map((line, i) => {
					const p = popIn(frame, fps, 4 + i * 5, 14);
					return (
						<div
							key={i}
							style={{
								fontFamily: fontFamily(str(ov.font, theme.displayFont)),
								fontSize: size,
								lineHeight: 1.08,
								color: ink,
								textAlign: 'center',
								transform: `translateY(${(1 - p) * 50 * k}px)`,
								opacity: Math.min(1, p * 1.4),
								unicodeBidi: 'isolate',
							}}
						>
							{line.split('*').map((part, j) => (
								// *word* = accent, and any accentWords are accented too
								<span key={j}>
									{part.split(' ').map((w, m) => (
										<span key={m} style={{color: j % 2 || accent.some((a) => w.includes(a)) ? theme.accent : undefined}}>
											{(m ? ' ' : '') + w}
										</span>
									))}
								</span>
							))}
						</div>
					);
				})}
			</div>
		</AbsoluteFill>
	);
};
