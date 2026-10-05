// The speaker track: every kept segment of the raw footage, back to back, with the
// transitions between them. Voice lives here and runs continuously from frame 0 —
// overlays only ever cover pixels, never replace this track.
import {Video} from '@remotion/media';
import {TransitionSeries} from '@remotion/transitions';
import React from 'react';
import {AbsoluteFill, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {lookEffects} from './looks';
import {cutEntryStyle, cutExitStyle, presentationFor, timingFor} from './transitions';
import type {EditData, Segment} from './types';

const src = (s: string) => (s.startsWith('http') ? s : staticFile(s));
// @remotion/media draws video on a canvas: give it an explicit box or it keeps its own size
const FILL: React.CSSProperties = {position: 'absolute', inset: 0, width: '100%', height: '100%'};

const CoverBox: React.FC<{sw: number; sh: number; fx: number; fy: number; children: React.ReactNode}> = ({
	sw,
	sh,
	fx,
	fy,
	children,
}) => {
	const {width, height} = useVideoConfig();
	const scale = Math.max(width / sw, height / sh);
	const w = sw * scale;
	const h = sh * scale;
	return (
		<div style={{position: 'absolute', width: w, height: h, left: (width - w) * fx, top: (height - h) * fy}}>
			{children}
		</div>
	);
};

const SegmentView: React.FC<{seg: Segment; next?: Segment; fadeIn: number; fadeOut: number; look?: string}> = ({
	seg,
	next,
	fadeIn,
	fadeOut,
	look,
}) => {
	const effects = lookEffects(look);
	const frame = useCurrentFrame();
	const dur = seg.durationInFrames;
	const entry = cutEntryStyle(seg.transitionIn, frame);
	const exit = cutExitStyle(next?.transitionIn, dur - 1 - frame);
	const fit = seg.fit ?? 'cover';
	const [fx, fy] = seg.focus ?? [0.5, 0.5];

	// Short audio ramps at every seam kill the "click" a hard audio cut makes.
	// Overlap transitions get a real crossfade as long as the transition.
	const volume = (f: number) =>
		seg.volume *
		Math.min(
			interpolate(f, [0, Math.max(1, fadeIn)], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
			interpolate(f, [dur - Math.max(1, fadeOut), dur], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
		);

	// Punch-in = a static scale (a jump cut), never an animated zoom on the speaker.
	const transforms = [entry.transform, exit.transform, seg.zoom !== 1 ? `scale(${seg.zoom})` : undefined]
		.filter(Boolean)
		.join(' ');
	const filter = [entry.filter, exit.filter].filter(Boolean).join(' ') || undefined;

	return (
		<AbsoluteFill style={{overflow: 'hidden'}}>
			{fit === 'blur' ? (
				<AbsoluteFill style={{transform: 'scale(1.15)', filter: 'blur(40px) brightness(0.6)'}}>
					<Video src={src(seg.src)} trimBefore={seg.trimBefore} muted objectFit="cover" style={FILL} />
				</AbsoluteFill>
			) : null}
			<AbsoluteFill style={{transform: transforms || undefined, transformOrigin: seg.zoomOrigin, filter}}>
				{fit === 'cover' && seg.srcWidth && seg.srcHeight ? (
					// Manual cover so `focus` can pick which part of a wider frame stays visible
					// (the video is drawn to a canvas, so CSS object-position would be ignored).
					<CoverBox sw={seg.srcWidth} sh={seg.srcHeight} fx={fx} fy={fy}>
						<Video
							src={src(seg.src)}
							trimBefore={seg.trimBefore}
							volume={volume}
							objectFit="fill"
							style={FILL}
							effects={effects}
						/>
					</CoverBox>
				) : (
					<Video
						src={src(seg.src)}
						trimBefore={seg.trimBefore}
						volume={volume}
						objectFit={fit === 'cover' ? 'cover' : 'contain'}
						style={FILL}
						effects={effects}
					/>
				)}
			</AbsoluteFill>
		</AbsoluteFill>
	);
};

export const ARoll: React.FC<{data: EditData}> = ({data}) => {
	const {segments, width, height} = data;
	return (
		<TransitionSeries>
			{segments.map((seg, i) => {
				const next = segments[i + 1];
				const tIn = seg.transitionIn;
				const fadeIn = tIn?.overlap ? tIn.durationInFrames : 1;
				const fadeOut = next?.transitionIn?.overlap ? next.transitionIn.durationInFrames : 1;
				return (
					<React.Fragment key={`seg-${i}`}>
						{i > 0 && tIn?.overlap ? (
							<TransitionSeries.Transition presentation={presentationFor(tIn, width, height)} timing={timingFor(tIn)} />
						) : null}
						<TransitionSeries.Sequence durationInFrames={seg.durationInFrames} name={`segment ${i + 1}`}>
							<SegmentView seg={seg} next={next} fadeIn={fadeIn} fadeOut={fadeOut} look={data.look} />
						</TransitionSeries.Sequence>
					</React.Fragment>
				);
			})}
		</TransitionSeries>
	);
};
