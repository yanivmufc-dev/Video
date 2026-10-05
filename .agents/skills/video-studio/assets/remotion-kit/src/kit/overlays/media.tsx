// Media overlays: B-roll (video or image), stickers/images, emoji (animated when available).
import {Lottie, type LottieAnimationData} from '@remotion/lottie';
import {Video} from '@remotion/media';
import React, {useEffect, useState} from 'react';
import {AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useDelayRender, useVideoConfig} from 'remotion';
import {bob, envelope, num, popIn, str} from '../anim';
import type {OverlayProps} from './types';

const url = (s: string) => (s.startsWith('http') ? s : staticFile(s));
const isVideo = (s: string) => /\.(mp4|mov|webm|m4v)$/i.test(s);

/**
 * B-roll. layout:
 *   full  — covers the whole frame (voice keeps playing underneath)
 *   band  — bottom ~38% with a SOFT feathered top edge (a hard band edge looks cheap)
 *   top   — top ~40%, feathered bottom edge
 *   pip   — rounded card at x/y
 * B-roll video is always muted: extra audio layers also break long renders on Windows.
 */
export const BRoll: React.FC<OverlayProps> = ({ov}) => {
	const frame = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const k = Math.min(width, height) / 1080;
	const src = str(ov.src, '');
	const layout = str(ov.layout, 'full');
	const dur = ov.durationInFrames;
	const fadeIn = layout === 'full' ? 4 : 6;
	const opacity = envelope(frame, dur, fadeIn, 6);
	const kenBurns = interpolate(frame, [0, dur], [1.0, 1.08]);
	const media = isVideo(src) ? (
		<Video
			src={url(src)}
			muted
			trimBefore={Math.round(num(ov.trim, 0) * fps)}
			objectFit="cover"
			style={{position: 'absolute', inset: 0, width: '100%', height: '100%'}}
		/>
	) : (
		<Img
			src={url(src)}
			style={{width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${kenBurns})`}}
		/>
	);

	if (layout === 'band' || layout === 'top') {
		const bandH = height * num(ov.size, layout === 'band' ? 0.38 : 0.4);
		const fromBottom = layout === 'band';
		const feather = fromBottom
			? 'linear-gradient(to bottom, transparent 0%, black 22%)'
			: 'linear-gradient(to top, transparent 0%, black 22%)';
		const slide = (1 - Math.min(1, frame / fadeIn)) * 40 * k * (fromBottom ? 1 : -1);
		return (
			<AbsoluteFill style={{opacity}}>
				<div
					style={{
						position: 'absolute',
						left: 0,
						right: 0,
						[fromBottom ? 'bottom' : 'top']: 0,
						height: bandH,
						overflow: 'hidden',
						WebkitMaskImage: feather,
						maskImage: feather,
						transform: `translateY(${slide}px)`,
					}}
				>
					{media}
				</div>
			</AbsoluteFill>
		);
	}
	if (layout === 'pip') {
		const p = popIn(frame, fps);
		const w = Math.min(width, height) * num(ov.size, 0.55);
		return (
			<AbsoluteFill style={{opacity}}>
				<div
					style={{
						position: 'absolute',
						left: width * num(ov.x, 0.5),
						top: height * num(ov.y, 0.3),
						width: w,
						aspectRatio: str(ov.aspect, '16 / 10'),
						transform: `translate(-50%, -50%) scale(${p}) rotate(${num(ov.rotate, -2)}deg)`,
						borderRadius: 28 * k,
						overflow: 'hidden',
						border: `${6 * k}px solid #fff`,
						boxShadow: '0 24px 60px rgba(0,0,0,0.45)',
					}}
				>
					{media}
				</div>
			</AbsoluteFill>
		);
	}
	return <AbsoluteFill style={{opacity}}>{media}</AbsoluteFill>;
};

/** Image / sticker / logo that pops in and floats. x/y = center, size = width fraction. */
export const Sticker: React.FC<OverlayProps> = ({ov}) => {
	const frame = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const p = popIn(frame, fps);
	const w = Math.min(width, height) * num(ov.size, 0.3);
	return (
		<AbsoluteFill style={{opacity: envelope(frame, ov.durationInFrames, 1, 6)}}>
			<Img
				src={url(str(ov.src, ''))}
				style={{
					position: 'absolute',
					left: width * num(ov.x, 0.5),
					top: height * num(ov.y, 0.3) + bob(frame, fps, 8),
					width: w,
					transform: `translate(-50%, -50%) scale(${p}) rotate(${num(ov.rotate, 0) + (1 - p) * -12}deg)`,
					filter: ov.shadow === false ? undefined : 'drop-shadow(0 16px 30px rgba(0,0,0,0.35))',
				}}
			/>
		</AbsoluteFill>
	);
};

const LottieFromFile: React.FC<{path: string; size: number}> = ({path, size}) => {
	const [data, setData] = useState<LottieAnimationData | null>(null);
	const {delayRender, continueRender, cancelRender} = useDelayRender();
	const [handle] = useState(() => delayRender(`Loading ${path}`));
	useEffect(() => {
		fetch(url(path))
			.then((r) => r.json())
			.then((json) => {
				setData(json);
				continueRender(handle);
			})
			.catch((err) => cancelRender(err));
	}, [path, handle, continueRender, cancelRender]);
	if (!data) {
		return null;
	}
	return <Lottie animationData={data} loop style={{width: size, height: size}} />;
};

/**
 * Emoji. build_edit.py fills `lottie` (animated Noto emoji) or `image` (static PNG) from
 * the library when they exist; otherwise the system emoji font is used — which looks
 * different on Mac and Windows, so prefer fetching the assets (tools: fetch_assets.py emoji).
 */
export const Emoji: React.FC<OverlayProps> = ({ov}) => {
	const frame = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const size = Math.min(width, height) * num(ov.size, 0.2);
	const p = popIn(frame, fps, 0, 9);
	const left = width * num(ov.x, 0.78) - size / 2;
	const top = height * num(ov.y, 0.3) - size / 2 + bob(frame, fps, 10);
	const lottie = typeof ov.lottie === 'string' ? ov.lottie : null;
	const image = typeof ov.image === 'string' ? ov.image : null;
	return (
		<AbsoluteFill style={{opacity: envelope(frame, ov.durationInFrames, 1, 6)}}>
			<div
				style={{
					position: 'absolute',
					left,
					top,
					width: size,
					height: size,
					transform: `scale(${p}) rotate(${num(ov.rotate, 0)}deg)`,
					filter: 'drop-shadow(0 12px 24px rgba(0,0,0,0.35))',
					display: 'flex',
					alignItems: 'center',
					justifyContent: 'center',
					fontSize: size * 0.82,
					lineHeight: 1,
				}}
			>
				{lottie ? (
					<LottieFromFile path={lottie} size={size} />
				) : image ? (
					<Img src={url(image)} style={{width: size, height: size}} />
				) : (
					str(ov.emoji, '🔥')
				)}
			</div>
		</AbsoluteFill>
	);
};
