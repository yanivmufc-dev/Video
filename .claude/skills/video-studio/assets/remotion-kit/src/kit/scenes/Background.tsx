// Animated backgrounds for full-screen scenes. Everything is procedural (no assets), slow and
// subtle: the background is a stage, the content is the show.
import React from 'react';
import {AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Video} from '@remotion/media';

export type BgKind = 'gradient' | 'grid' | 'dots' | 'spotlight' | 'light' | 'solid' | 'media';

const url = (s: string) => (s.startsWith('http') ? s : staticFile(s));

/** Mix a hex color with black/white. amount 0..1 */
export const shade = (hex: string, amount: number, toward = '#000000') => {
	const p = (h: string) => [1, 3, 5].map((i) => parseInt(h.replace('#', '').padEnd(6, '0').slice(i - 1, i + 1), 16));
	const [a, b] = [p(hex), p(toward)];
	const c = a.map((v, i) => Math.round(v + (b[i] - v) * amount));
	return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
};

export const SceneBackground: React.FC<{
	kind: BgKind;
	accent: string;
	base?: string;
	src?: string;
}> = ({kind, accent, base, src}) => {
	const frame = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const t = frame / fps;
	const k = Math.min(width, height) / 1080;
	const dark = base ?? '#0B0B10';

	if (kind === 'media' && src) {
		const isVideo = /\.(mp4|mov|webm|m4v)$/i.test(src);
		return (
			<AbsoluteFill style={{backgroundColor: '#000'}}>
				<AbsoluteFill style={{transform: `scale(${1.08 + t * 0.01})`, filter: 'blur(18px) brightness(0.45)'}}>
					{isVideo ? (
						<Video src={url(src)} muted objectFit="cover" style={{position: 'absolute', inset: 0, width: '100%', height: '100%'}} />
					) : (
						<Img src={url(src)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
					)}
				</AbsoluteFill>
			</AbsoluteFill>
		);
	}
	if (kind === 'solid') {
		const c = base ?? accent;
		return (
			<AbsoluteFill style={{backgroundColor: c}}>
				{/* a slow soft light drift keeps it alive (and out of the "frozen picture" check) */}
				<AbsoluteFill style={{background: `radial-gradient(circle at ${50 + Math.sin(t * 0.8) * 25}% ${40 + Math.cos(t * 0.6) * 15}%, rgba(255,255,255,0.12) 0%, transparent 50%)`}} />
			</AbsoluteFill>
		);
	}
	if (kind === 'light') {
		const paper = base ?? '#F4F1E9';
		return (
			<AbsoluteFill style={{backgroundColor: paper}}>
				<AbsoluteFill
					style={{
						backgroundImage: `linear-gradient(${shade(paper, 0.07)} 1px, transparent 1px), linear-gradient(90deg, ${shade(paper, 0.07)} 1px, transparent 1px)`,
						backgroundSize: `${60 * k}px ${60 * k}px`,
						backgroundPosition: `0 ${(t * 12 * k) % (60 * k)}px`,
					}}
				/>
				<AbsoluteFill
					style={{
						background: `radial-gradient(circle at ${50 + Math.sin(t * 0.6) * 20}% ${30 + Math.cos(t * 0.5) * 10}%, ${accent}33 0%, transparent 45%)`,
					}}
				/>
			</AbsoluteFill>
		);
	}
	// dark variants share an animated two-blob glow
	const blobs = (
		<>
			<AbsoluteFill
				style={{
					background: `radial-gradient(circle at ${30 + Math.sin(t * 0.7) * 18}% ${25 + Math.cos(t * 0.5) * 12}%, ${accent}66 0%, transparent 42%)`,
				}}
			/>
			<AbsoluteFill
				style={{
					background: `radial-gradient(circle at ${72 + Math.cos(t * 0.6) * 15}% ${78 + Math.sin(t * 0.4) * 10}%, ${shade(accent, 0.35, '#6b3cff')}55 0%, transparent 45%)`,
				}}
			/>
		</>
	);
	return (
		<AbsoluteFill style={{backgroundColor: dark}}>
			{kind !== 'spotlight' ? blobs : null}
			{kind === 'grid' ? (
				<AbsoluteFill
					style={{
						backgroundImage: `linear-gradient(rgba(255,255,255,0.07) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.07) 1px, transparent 1px)`,
						backgroundSize: `${72 * k}px ${72 * k}px`,
						backgroundPosition: `0 ${(t * 18 * k) % (72 * k)}px`,
						maskImage: 'radial-gradient(ellipse at center, black 30%, transparent 80%)',
						WebkitMaskImage: 'radial-gradient(ellipse at center, black 30%, transparent 80%)',
					}}
				/>
			) : null}
			{kind === 'dots' ? (
				<AbsoluteFill
					style={{
						backgroundImage: `radial-gradient(rgba(255,255,255,0.14) ${2 * k}px, transparent ${2.5 * k}px)`,
						backgroundSize: `${40 * k}px ${40 * k}px`,
						backgroundPosition: `${(t * 10 * k) % (40 * k)}px 0`,
					}}
				/>
			) : null}
			{kind === 'spotlight' ? (
				<AbsoluteFill
					style={{
						background: `radial-gradient(ellipse at 50% ${-10 + Math.sin(t) * 3}%, ${accent}88 0%, ${accent}22 35%, transparent 65%)`,
					}}
				/>
			) : null}
			<AbsoluteFill style={{background: 'radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.55) 100%)'}} />
		</AbsoluteFill>
	);
};
