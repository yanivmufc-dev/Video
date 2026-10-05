// Word-synced Hebrew captions. Pages (1–4 words) come from build_edit.py and never cross
// a cut. Rendered ABOVE every overlay: most viewers watch muted, so captions must win.
//
// RTL rules that matter (each one produced a visibly broken caption once):
//  - the container is dir="rtl"; the words stay in LOGICAL order — never reverse strings,
//    never use flex row-reverse (double reversal scrambles punctuation);
//  - every word is its own span with unicode-bidi: isolate, so "Claude", "ב-2026" and
//    "(בחינם!)" keep their internal order inside Hebrew text.
import React from 'react';
import {AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig} from 'remotion';
import {popIn} from './anim';
import {splitTrailingPunct, toRuns} from './bidi';
import {fontFamily, OUTLINE, resolveTheme} from './theme';
import type {CaptionPage, Captions as CaptionsData, Theme} from './types';

const Page: React.FC<{page: CaptionPage; cfg: CaptionsData; theme: Required<Theme>}> = ({page, cfg, theme}) => {
	const frame = useCurrentFrame(); // relative to page start
	const {fps, width, height} = useVideoConfig();
	const abs = frame + page.startFrame;
	const k = Math.min(width, height) / 1080;
	const style = cfg.style === 'hormozi' ? 'punch' : cfg.style ?? 'karaoke'; // 1.0 name
	const size = (cfg.size ?? (style === 'chips' ? 54 : 78)) * k;
	const base = cfg.color ?? theme.text;
	const hi = cfg.highlight ?? theme.accent;
	const family = fontFamily(cfg.font ?? theme.font);
	const enter = popIn(frame, fps, 0, 14);

	const renderToken = (t: (typeof page.tokens)[number], i: number, textOverride?: string) => {
		const active = abs >= t.startFrame && abs < Math.max(t.endFrame, t.startFrame + 2);
		const spoken = abs >= t.startFrame;
		const wordPop = popIn(abs - t.startFrame, fps, 0, 10);
		let color = base;
		let scale = 1;
		let opacity = 1;
		let background: string | undefined;
		let rotate = 0;
		let textShadow: string | undefined;
		let shown = t.text;
		if (style === 'karaoke') {
			color = t.keyword ? hi : active ? hi : base;
			scale = active && !t.keyword ? 1.05 : 1;
		} else if (style === 'pop') {
			opacity = spoken ? 1 : 0;
			scale = spoken ? 0.6 + 0.4 * wordPop : 0.6;
			color = t.keyword ? hi : base;
		} else if (style === 'box') {
			background = active ? hi : undefined;
			color = active ? '#111' : t.keyword ? hi : base;
		} else if (style === 'plain') {
			color = t.keyword ? hi : base;
		} else if (style === 'chips') {
			color = t.keyword ? hi : base;
		} else if (style === 'punch') {
			// each word punches in when spoken, the spoken word in the accent color
			opacity = spoken ? 1 : 0;
			scale = spoken ? 0.5 + 0.5 * wordPop : 0.5;
			scale *= active ? 1.08 : 1;
			rotate = spoken ? (1 - wordPop) * (i % 2 ? 6 : -6) : 0;
			color = active || t.keyword ? hi : base;
		} else if (style === 'glow') {
			color = active || t.keyword ? hi : base;
			const g = active ? 1 : 0.45;
			textShadow = `0 0 ${12 * k}px ${hi}${active ? 'FF' : '88'}, 0 0 ${36 * k * g}px ${hi}AA`;
		} else if (style === 'typewriter') {
			// characters appear as the word is spoken
			const len = t.text.length;
			const span = Math.max(2, t.endFrame - t.startFrame);
			const n = abs < t.startFrame ? 0 : Math.min(len, Math.ceil(((abs - t.startFrame + 1) / span) * len));
			shown = t.text.slice(0, n);
			color = t.keyword ? hi : base;
		} else if (style === 'clean') {
			color = t.keyword ? hi : base;
			opacity = spoken ? 1 : 0.55;
			textShadow = `0 ${2 * k}px ${14 * k}px rgba(0,0,0,0.65)`;
		}
		const emoji = typeof (t as {emoji?: string}).emoji === 'string' ? (t as {emoji?: string}).emoji : undefined;
		return (
			<span
				key={i}
				style={{
					unicodeBidi: 'isolate',
					display: 'inline-block',
					whiteSpace: 'pre',
					color,
					opacity,
					transform: `scale(${scale}) rotate(${rotate}deg)`,
					transformOrigin: '50% 60%',
					textShadow,
					position: emoji ? 'relative' : undefined,
					background,
					borderRadius: background ? 14 * k : undefined,
					padding: background ? `${4 * k}px ${14 * k}px` : undefined,
					// keywords are bigger by FONT SIZE (a transform would overlap the neighbours)
					fontSize: t.keyword && style !== 'plain' ? size * 1.2 : undefined,
				}}
			>
				{style === 'typewriter' ? shown : cfg.uppercase ? (textOverride ?? t.text).toUpperCase() : (textOverride ?? t.text)}
				{emoji && spoken ? (
					<span
						style={{
							position: 'absolute',
							left: '50%',
							bottom: '88%',
							transform: `translateX(-50%) scale(${wordPop})`,
							fontSize: size * 0.9,
							WebkitTextStroke: '0px',
							textShadow: 'none',
						}}
					>
						{emoji}
					</span>
				) : null}
			</span>
		);
	};

	const gap = size * 0.26;
	const words = toRuns(page.tokens).map((run, r) => {
		if (!run.ltr || run.items.length < 2) {
			return run.items.map(({t, i}) => renderToken(t, i));
		}
		const last = run.items[run.items.length - 1];
		const [lastText, punct] = splitTrailingPunct(last.t.text);
		return (
			// rtl wrapper: [English run][punctuation] — the punctuation ends up on the run's left,
			// which is its END in Hebrew reading order.
			<span key={`run-${r}`} dir="rtl" style={{display: 'inline-flex', alignItems: 'baseline', unicodeBidi: 'isolate'}}>
				<span dir="ltr" style={{display: 'inline-flex', alignItems: 'baseline', columnGap: gap, unicodeBidi: 'isolate'}}>
					{run.items.map(({t, i}) => renderToken(t, i, i === last.i ? lastText : undefined))}
				</span>
				{punct ? <span>{punct}</span> : null}
			</span>
		);
	});

	const outlined = !['chips', 'glow', 'clean', 'typewriter'].includes(style);
	const boxed = style === 'typewriter';
	return (
		<AbsoluteFill style={{pointerEvents: 'none'}}>
			<div
				dir="rtl"
				style={{
					position: 'absolute',
					// x 11–89% clears the Reels/TikTok UI. y: build_edit.py places captions just under the
					// chin (0.60–0.74) from `studio framing`; keep the block's bottom above ~75% of height.
					left: width * 0.11,
					right: width * 0.11,
					top: height * (cfg.y ?? 0.6),
					transform: `translateY(-50%) scale(${0.85 + 0.15 * enter})`,
					display: 'flex',
					flexWrap: 'wrap',
					justifyContent: 'center',
					alignItems: 'baseline',
					columnGap: gap,
					rowGap: 6 * k,
					fontFamily: family,
					fontWeight: 900,
					fontSize: size,
					color: base,
					lineHeight: 1.15,
					textAlign: 'center',
					...(outlined ? OUTLINE(Math.max(4, Math.round(size / (style === 'punch' ? 7 : 10)))) : {}),
					...(style === 'clean' ? {fontWeight: 700} : {}),
					...(boxed ? {background: 'rgba(10,10,10,0.82)', borderRadius: 16 * k, padding: `${10 * k}px ${22 * k}px`} : {}),
				}}
			>
				{style === 'chips' ? (
					<div
						dir="rtl"
						style={{
							background: 'rgba(12,12,12,0.92)',
							borderRadius: 18 * k,
							padding: `${10 * k}px ${22 * k}px`,
							display: 'flex',
							flexWrap: 'wrap',
							justifyContent: 'center',
							columnGap: gap,
							fontWeight: 800,
						}}
					>
						{words}
					</div>
				) : (
					words
				)}
			</div>
		</AbsoluteFill>
	);
};

export const Captions: React.FC<{data: CaptionsData; theme?: Theme}> = ({data, theme}) => {
	const t = resolveTheme(theme);
	return (
		<>
			{data.pages.map((page, i) => (
				<Sequence
					key={i}
					from={page.startFrame}
					durationInFrames={Math.max(1, page.endFrame - page.startFrame)}
					name={`captions: ${page.tokens.map((x) => x.text).join(' ')}`}
					layout="none"
				>
					<Page page={page} cfg={data} theme={t} />
				</Sequence>
			))}
		</>
	);
};
