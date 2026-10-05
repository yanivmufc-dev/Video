// Energy overlays: particle bursts (confetti / sparkles / emoji rain) and voice-reactive bars.
import React from 'react';
import {AbsoluteFill, random, useCurrentFrame, useVideoConfig} from 'remotion';
import {num, str} from '../anim';
import {useVoice} from '../voice';
import type {OverlayProps} from './types';

const CONFETTI = ['#FF3B30', '#FFCC00', '#34C759', '#0A84FF', '#FF2D92', '#FFFFFF'];

/**
 * Particle burst from a point. kind: confetti | sparkles | emoji (uses `emoji`, e.g. "💰" or "🔥❤️").
 * Deterministic (seeded) physics: launch up/out, gravity, spin, fade.
 */
export const Burst: React.FC<OverlayProps> = ({ov, theme}) => {
	const frame = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const k = Math.min(width, height) / 1080;
	const kind = str(ov.kind, 'confetti');
	const n = Math.round(num(ov.count, kind === 'emoji' ? 18 : 60));
	const ox = width * num(ov.x, 0.5);
	const oy = height * num(ov.y, 0.92); // from below the frame edge, so the face stays clear
	const t = frame / fps;
	const emojis = Array.from(str(ov.emoji, '✨'));
	const gravity = num(ov.gravity, kind === 'sparkles' ? 400 : 1600) * k;
	return (
		<AbsoluteFill style={{pointerEvents: 'none'}}>
			{Array.from({length: n}, (_, i) => {
				const r = (s: string) => random(`${ov.startFrame}-${i}-${s}`);
				const angle = -Math.PI / 2 + (r('a') - 0.5) * Math.PI * num(ov.spread, 0.9);
				const speed = (1100 + r('s') * 1100) * k * num(ov.power, 1);
				const x = ox + Math.cos(angle) * speed * t;
				const y = oy + Math.sin(angle) * speed * t + 0.5 * gravity * t * t;
				const life = 0.9 + r('l') * 0.8;
				const fade = Math.max(0, 1 - t / life);
				const spin = (r('r') - 0.5) * 900 * t;
				const size = (kind === 'emoji' ? 80 : kind === 'sparkles' ? 38 : 30) * k * (0.6 + r('z') * 0.8);
				if (fade <= 0) {
					return null;
				}
				const common: React.CSSProperties = {
					position: 'absolute',
					left: x,
					top: y,
					transform: `translate(-50%, -50%) rotate(${spin}deg)`,
					opacity: fade,
				};
				if (kind === 'emoji') {
					return (
						<div key={i} style={{...common, fontSize: size}}>
							{emojis[i % emojis.length]}
						</div>
					);
				}
				if (kind === 'sparkles') {
					const tw = 0.6 + 0.4 * Math.sin(frame * 0.8 + i);
					return (
						<div key={i} style={{...common, fontSize: size * tw, color: i % 3 ? '#FFF6C8' : theme.accent, textShadow: `0 0 ${10 * k}px #fff`}}>
							✦
						</div>
					);
				}
				return (
					<div
						key={i}
						style={{
							...common,
							width: size,
							height: size * 0.45,
							borderRadius: 3 * k,
							background: i % 5 === 0 ? theme.accent : CONFETTI[i % CONFETTI.length],
						}}
					/>
				);
			})}
		</AbsoluteFill>
	);
};

/** Bars that dance with the speaker's voice (mode "bars") or a pulsing ring (mode "ring"). */
export const Waveform: React.FC<OverlayProps> = ({ov, theme}) => {
	const frame = useCurrentFrame();
	const {width, height} = useVideoConfig();
	const k = Math.min(width, height) / 1080;
	const voiceAt = useVoice();
	const abs = frame + ov.startFrame;
	const level = voiceAt(abs);
	const color = str(ov.color, theme.accent);
	if (str(ov.mode, 'bars') === 'ring') {
		const r = Math.min(width, height) * num(ov.size, 0.3) * (1 + level * 0.25);
		return (
			<AbsoluteFill>
				<div
					style={{
						position: 'absolute',
						left: width * num(ov.x, 0.5) - r / 2,
						top: height * num(ov.y, 0.4) - r / 2,
						width: r,
						height: r,
						borderRadius: '50%',
						border: `${(6 + level * 18) * k}px solid ${color}`,
						boxShadow: `0 0 ${(20 + level * 60) * k}px ${color}`,
						opacity: 0.35 + level * 0.65,
					}}
				/>
			</AbsoluteFill>
		);
	}
	const bars = Math.round(num(ov.bars, 28));
	const w = width * num(ov.width, 0.7);
	const maxH = height * num(ov.height, 0.08);
	return (
		<AbsoluteFill>
			<div
				style={{
					position: 'absolute',
					left: width * num(ov.x, 0.5) - w / 2,
					top: height * num(ov.y, 0.86) - maxH / 2,
					width: w,
					height: maxH,
					display: 'flex',
					alignItems: 'center',
					gap: w / bars / 3,
				}}
			>
				{Array.from({length: bars}, (_, i) => {
					const shape = 0.35 + 0.65 * Math.abs(Math.sin(i * 1.7 + abs * 0.35)) * (1 - Math.abs(i - bars / 2) / (bars / 1.6));
					const h = Math.max(4 * k, maxH * Math.min(1, voiceAt(abs - (i % 4)) * 1.4) * shape);
					return <div key={i} style={{flex: 1, height: h, borderRadius: 99, background: color, boxShadow: `0 0 ${10 * k}px ${color}88`}} />;
				})}
			</div>
		</AbsoluteFill>
	);
};
