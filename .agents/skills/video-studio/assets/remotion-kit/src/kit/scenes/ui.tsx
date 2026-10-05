// App/UI scenes: a chat conversation, a terminal typing commands, and a device (phone or
// browser) showing a screenshot/screen recording — or a landing page that "builds itself".
import {loadFont as loadMono} from '@remotion/google-fonts/JetBrainsMono';
import {Video} from '@remotion/media';
import React from 'react';
import {AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {num, popIn, progress, str, stageWidth} from '../anim';
import {fontFamily} from '../theme';
import type {SceneProps} from './types';

const {fontFamily: MONO} = loadMono('normal', {weights: ['500', '700'], subsets: ['latin']});
const url = (s: string) => (s.startsWith('http') ? s : staticFile(s));
type Timed = {startFrame?: number};

/** Chat bubbles (WhatsApp-like). messages: [{from: "me"|"them", text, at}] — "them" shows typing dots first. */
export const ChatScene: React.FC<SceneProps> = ({ov, theme}) => {
	const frame = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const k = Math.min(width, height) / 1080;
	const msgs = (Array.isArray(ov.messages) ? ov.messages : []) as Array<{from?: string; text: string} & Timed>;
	const stagger = Math.round(num(ov.stagger, 0.9) * fps);
	const times = msgs.map((m, i) => (m.startFrame !== undefined ? m.startFrame : 10 + i * stagger));
	const visible = msgs.map((m, i) => ({...m, f0: times[i]})).filter((m) => frame >= m.f0 - (m.from === 'me' ? 0 : 14));
	const w = Math.min(width * 0.82, height * 0.62);
	return (
		<AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
			<div
				style={{
					width: w,
					height: height * 0.44,
					marginTop: -60 * k,
					borderRadius: 44 * k,
					overflow: 'hidden',
					background: '#0B141A',
					boxShadow: '0 40px 90px rgba(0,0,0,0.5)',
					display: 'flex',
					flexDirection: 'column',
					transform: `scale(${0.9 + 0.1 * popIn(frame, fps)})`,
				}}
			>
				<div dir="rtl" style={{display: 'flex', alignItems: 'center', gap: 20 * k, padding: `${24 * k}px ${30 * k}px`, background: '#1F2C34'}}>
					<div style={{width: 70 * k, height: 70 * k, borderRadius: 999, background: theme.accent, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 40 * k}}>
						{str(ov.avatar, '🤖')}
					</div>
					<div>
						<div style={{fontFamily: fontFamily(theme.font), fontWeight: 800, fontSize: 40 * k, color: '#E9EDEF', unicodeBidi: 'isolate'}}>{str(ov.name, 'סוכן AI')}</div>
						<div style={{fontFamily: fontFamily(theme.font), fontSize: 28 * k, color: '#8696A0'}}>{str(ov.status, 'מחובר')}</div>
					</div>
				</div>
				<div style={{flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', gap: 16 * k, padding: 26 * k}}>
					{visible.slice(-6).map((m, i) => {
						const me = m.from === 'me';
						const typing = !me && frame < m.f0;
						const p = popIn(frame - (typing ? m.f0 - 14 : m.f0), fps, 0, 14);
						return (
							<div key={`${m.f0}-${i}`} style={{display: 'flex', justifyContent: me ? 'flex-start' : 'flex-end'}}>
								<div
									dir="rtl"
									style={{
										maxWidth: '78%',
										background: me ? '#005C4B' : '#202C33',
										color: '#E9EDEF',
										borderRadius: 28 * k,
										padding: `${18 * k}px ${26 * k}px`,
										fontFamily: fontFamily(theme.font),
										fontSize: num(ov.size, 46) * k,
										lineHeight: 1.3,
										transform: `scale(${p})`,
										transformOrigin: me ? 'left bottom' : 'right bottom',
										unicodeBidi: 'isolate',
									}}
								>
									{typing ? <span style={{letterSpacing: 6 * k}}>{'•••'.slice(0, 1 + (Math.floor(frame / 5) % 3))}</span> : m.text}
								</div>
							</div>
						);
					})}
				</div>
			</div>
		</AbsoluteFill>
	);
};

/** Terminal: lines [{text, kind: "cmd"|"out"|"ok", at}] — commands type out, output appears. */
export const TerminalScene: React.FC<SceneProps> = ({ov, theme}) => {
	const frame = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const k = Math.min(width, height) / 1080;
	const stage = stageWidth(width, height);
	const lines = (Array.isArray(ov.lines) ? ov.lines : []) as Array<{text: string; kind?: string} & Timed>;
	const cps = num(ov.charsPerSecond, 28);
	let cursor = 8;
	const timed = lines.map((l) => {
		const f0 = l.startFrame !== undefined ? l.startFrame : cursor;
		const dur = l.kind === 'cmd' || l.kind === undefined ? Math.ceil((l.text.length / cps) * fps) : 2;
		cursor = f0 + dur + 8;
		return {...l, f0, dur};
	});
	const shown = timed.filter((l) => frame >= l.f0);
	return (
		<AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
			<div
				style={{
					width: stage * 0.88,
					height: height * 0.5,
					marginTop: -120 * k,
					borderRadius: 28 * k,
					overflow: 'hidden',
					background: '#141414',
					border: `${2 * k}px solid #2a2a2a`,
					boxShadow: `0 40px 90px rgba(0,0,0,0.55), 0 0 0 ${2 * k}px ${theme.accent}22`,
					transform: `scale(${0.92 + 0.08 * popIn(frame, fps)})`,
				}}
			>
				<div style={{display: 'flex', alignItems: 'center', gap: 12 * k, padding: `${18 * k}px ${22 * k}px`, background: '#1d1d1d'}}>
					{['#FF5F57', '#FEBC2E', '#28C840'].map((c) => (
						<div key={c} style={{width: 20 * k, height: 20 * k, borderRadius: 99, background: c}} />
					))}
					<div style={{flex: 1, textAlign: 'center', fontFamily: MONO, fontSize: 26 * k, color: '#999'}}>{str(ov.title, 'Terminal')}</div>
				</div>
				<div dir="ltr" style={{padding: `${26 * k}px ${30 * k}px`, fontFamily: MONO, fontSize: num(ov.size, 34) * k, lineHeight: 1.5}}>
					{shown.slice(-9).map((l, i) => {
						const isCmd = l.kind === 'cmd' || l.kind === undefined;
						const n = isCmd ? Math.floor(interpolate(frame, [l.f0, l.f0 + l.dur], [0, l.text.length], {extrapolateRight: 'clamp'})) : l.text.length;
						const typingNow = isCmd && n < l.text.length;
						const color = l.kind === 'ok' ? '#4ADE80' : l.kind === 'out' ? '#C9C9C9' : '#FFFFFF';
						return (
							<div key={`${l.f0}-${i}`} style={{color, whiteSpace: 'pre-wrap', unicodeBidi: 'plaintext'}}>
								{isCmd ? <span style={{color: theme.accent}}>{'> '}</span> : l.kind === 'ok' ? '✓ ' : ''}
								{l.text.slice(0, n)}
								{typingNow || (i === shown.slice(-9).length - 1 && Math.floor(frame / 15) % 2 === 0) ? (
									<span style={{background: '#fff', color: '#000'}}> </span>
								) : null}
							</div>
						);
					})}
				</div>
			</div>
		</AbsoluteFill>
	);
};

type Mock = {brand?: string; title?: string; subtitle?: string; cta?: string; features?: string[]; price?: string; banner?: string; stats?: string[]; quote?: string};

/** A landing page that assembles itself block by block (for "the AI built this page"). */
const MockPage: React.FC<{mock: Mock; accent: string; font: string; display: string; k: number; build: boolean}> = ({
	mock,
	accent,
	font,
	display,
	k,
	build,
}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const step = Math.round(0.2 * fps); // the whole page is built in ~2 s
	const show = (i: number) => (build ? popIn(frame - 6 - i * step, fps, 0, 14) : 1);
	const titleChars = build
		? Math.floor(interpolate(frame, [6 + step, 6 + step * 3], [0, (mock.title ?? '').length], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}))
		: (mock.title ?? '').length;
	return (
		<div dir="rtl" style={{width: '100%', height: '100%', background: '#FBFAF7', fontFamily: font, overflow: 'hidden'}}>
			<div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: `${22 * k}px ${30 * k}px`, opacity: show(0), borderBottom: '1px solid #eee'}}>
				<div style={{fontWeight: 900, fontSize: 30 * k, color: '#111'}}>{mock.brand ?? 'המותג'}</div>
				<div style={{background: accent, color: '#fff', borderRadius: 99, padding: `${8 * k}px ${22 * k}px`, fontWeight: 800, fontSize: 22 * k}}>{mock.cta ?? 'להצטרפות'}</div>
			</div>
			<div style={{padding: `${40 * k}px ${34 * k}px ${20 * k}px`, textAlign: 'center'}}>
				<div style={{fontFamily: display, fontSize: 58 * k, lineHeight: 1.1, color: '#111', minHeight: 64 * k, unicodeBidi: 'isolate'}}>
					{(mock.title ?? '').slice(0, titleChars)}
				</div>
				<div style={{fontSize: 28 * k, color: '#555', marginTop: 14 * k, opacity: show(3), unicodeBidi: 'isolate'}}>{mock.subtitle ?? ''}</div>
				<div style={{display: 'inline-block', marginTop: 24 * k, background: accent, color: '#fff', borderRadius: 18 * k, padding: `${16 * k}px ${40 * k}px`, fontWeight: 900, fontSize: 32 * k, transform: `scale(${show(4)})`, boxShadow: `0 10px 30px ${accent}55`}}>
					{mock.cta ?? 'להצטרפות'} {mock.price ? `· ${mock.price}` : ''}
				</div>
			</div>
			<div style={{display: 'flex', gap: 14 * k, padding: `${10 * k}px ${24 * k}px`}}>
				{(mock.features ?? []).slice(0, 3).map((f, i) => (
					<div key={i} style={{flex: 1, background: '#fff', border: '1px solid #eee', borderRadius: 18 * k, padding: 16 * k, textAlign: 'center', fontSize: 24 * k, fontWeight: 700, color: '#222', transform: `translateY(${(1 - show(5 + i)) * 40 * k}px)`, opacity: show(5 + i), unicodeBidi: 'isolate'}}>
						<div style={{width: 46 * k, height: 46 * k, borderRadius: 12 * k, background: `${accent}22`, margin: `0 auto ${10 * k}px`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 26 * k}}>
							{['⚡', '📊', '🤖'][i % 3]}
						</div>
						{f}
					</div>
				))}
			</div>
			<div style={{margin: `${18 * k}px ${24 * k}px`, borderRadius: 22 * k, height: 190 * k, background: `linear-gradient(135deg, ${accent}, #2b1b12)`, opacity: show(8), transform: `scale(${0.9 + 0.1 * show(8)})`, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontFamily: display, fontSize: 44 * k, unicodeBidi: 'isolate'}}>
				{mock.banner ?? mock.title ?? ''}
			</div>
			{/* stats and quote only when given — never invent numbers, ratings or testimonials */}
			<div style={{display: mock.stats?.length ? 'flex' : 'none', gap: 12 * k, padding: `0 ${24 * k}px`, opacity: show(9)}}>
				{(mock.stats ?? []).slice(0, 3).map((t, i) => (
					<div key={i} style={{flex: 1, textAlign: 'center', fontWeight: 900, fontSize: 26 * k, color: accent, unicodeBidi: 'isolate'}}>
						{t}
					</div>
				))}
			</div>
			{mock.quote ? (
				<div style={{margin: `${18 * k}px ${24 * k}px`, background: '#fff', border: '1px solid #eee', borderRadius: 18 * k, padding: 18 * k, fontSize: 22 * k, color: '#444', opacity: show(10), unicodeBidi: 'isolate'}}>
					{mock.quote}
				</div>
			) : null}
		</div>
	);
};

/** Phone or browser frame around media (`src`, optional `scroll` 0–1) or a mock page (`mock`). */
export const DeviceScene: React.FC<SceneProps> = ({ov, theme, ink}) => {
	const frame = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const k = Math.min(width, height) / 1080;
	const stage = stageWidth(width, height);
	const device = str(ov.device, 'phone');
	const src = str(ov.src, '');
	const isVideo = /\.(mp4|mov|webm|m4v)$/i.test(src);
	const scroll = num(ov.scroll, 0);
	const sp = interpolate(frame, [10, ov.durationInFrames - 6], [0, scroll], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const zoomIn = popIn(frame, fps, 0, 16);
	const phone = device === 'phone';
	const landscape = width > height;
	// the phone keeps its portrait layout and is scaled down to fit a landscape frame
	const W = phone ? Math.min(width, height) * 0.56 : landscape ? stage * 0.95 : width * 0.9;
	const H = phone ? W * 2.05 : landscape ? height * (ov.caption ? 0.66 : 0.76) : height * 0.5;
	const fit = phone ? Math.min(1, (height * (ov.caption ? 0.78 : 0.9)) / H) : 1;
	const shift = landscape ? (ov.caption ? height * 0.14 : 0) : phone ? -40 * k : -140 * k;
	const content = src ? (
		isVideo ? (
			<Video src={url(src)} muted objectFit="cover" style={{position: 'absolute', inset: 0, width: '100%', height: '100%'}} />
		) : (
			<Img src={url(src)} style={{width: '100%', position: 'absolute', top: 0, transform: `translateY(${-sp * 100}%)`}} />
		)
	) : (
		<MockPage mock={(ov.mock ?? {}) as Mock} accent={theme.accent} font={fontFamily(theme.font)} display={fontFamily(theme.displayFont)} k={k * (phone ? 0.95 : 1)} build={ov.build !== false} />
	);
	return (
		<AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
			<div
				style={{
					width: W,
					height: H,
					marginTop: shift,
					borderRadius: phone ? 70 * k : 26 * k,
					border: phone ? `${16 * k}px solid #111` : `${2 * k}px solid #ddd`,
					background: '#fff',
					overflow: 'hidden',
					position: 'relative',
					boxShadow: `0 50px 120px rgba(0,0,0,0.55), 0 0 ${80 * k}px ${theme.accent}33`,
					transform: `translateY(${(1 - zoomIn) * 120 * k}px) rotate(${(1 - zoomIn) * -6}deg) scale(${fit * (0.9 + 0.1 * zoomIn)})`,
					flexShrink: 0,
				}}
			>
				{!phone ? (
					<div style={{height: 56 * k, background: '#F1F1F1', display: 'flex', alignItems: 'center', gap: 10 * k, padding: `0 ${20 * k}px`, borderBottom: '1px solid #ddd'}}>
						{['#FF5F57', '#FEBC2E', '#28C840'].map((c) => (
							<div key={c} style={{width: 16 * k, height: 16 * k, borderRadius: 99, background: c}} />
						))}
						<div style={{flex: 1, margin: `0 ${20 * k}px`, height: 32 * k, borderRadius: 99, background: '#fff', fontFamily: fontFamily(theme.font), fontSize: 20 * k, color: '#777', display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
							{str(ov.url, 'www.example.co.il')}
						</div>
					</div>
				) : null}
				<div style={{position: 'absolute', top: phone ? 0 : 56 * k, left: 0, right: 0, bottom: 0, overflow: 'hidden'}}>{content}</div>
			</div>
			{ov.caption ? (
				<div
					dir="rtl"
					style={{
						position: 'absolute',
						top: height * (landscape ? 0.05 : 0.07),
						left: width * 0.08,
						right: width * 0.08,
						textAlign: 'center',
						fontFamily: fontFamily(theme.displayFont),
						fontSize: 70 * k,
						color: ink,
						textShadow: ink === '#FFFFFF' ? '0 6px 24px rgba(0,0,0,0.5)' : undefined,
						opacity: progress(frame, 6, 14),
						unicodeBidi: 'isolate',
					}}
				>
					{String(ov.caption)
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
