// The whole edit: speaker track -> overlays -> captions -> transition effects, plus sound.
// Rendered from the timeline tools/build_edit.py writes (src/projects/<id>.json).
import {Audio} from '@remotion/media';
import React from 'react';
import {AbsoluteFill, interpolate, Sequence, staticFile} from 'remotion';
import {ARoll} from './ARoll';
import {Captions} from './Captions';
import {DEFAULT_Z, OverlayView} from './overlays';
import {resolveTheme} from './theme';
import type {EditData, Music} from './types';
import {VoiceContext} from './voice';

const url = (s: string) => (s.startsWith('http') ? s : staticFile(s));
const CAPTIONS_Z = 50;

/** Music under the voice: low, and lower still while someone is speaking. */
const musicVolume = (music: Music, speech: Array<[number, number]>, total: number) => {
	const base = music.volume ?? 0.12;
	const duck = music.duck ?? 0.5; // multiplier while speaking
	const fadeOut = Math.round((music.fadeOut ?? 1.5) * 30);
	return (f: number) => {
		const speaking = speech.some(([s, e]) => f >= s - 4 && f <= e + 4);
		const end = interpolate(f, [total - fadeOut, total], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
		return base * (speaking ? duck : 1) * end;
	};
};

export const Edit: React.FC<{data: EditData}> = ({data}) => {
	const theme = resolveTheme(data.theme);
	const layered = data.overlays.map((ov) => ({ov, z: typeof ov.z === 'number' ? ov.z : DEFAULT_Z[ov.type] ?? 20}));
	const below = layered.filter((l) => l.z < CAPTIONS_Z).sort((a, b) => a.z - b.z);
	const above = layered.filter((l) => l.z >= CAPTIONS_Z).sort((a, b) => a.z - b.z);
	const speech: Array<[number, number]> = (data.captions?.pages ?? []).map((p) => [p.startFrame, p.endFrame]);

	const renderOverlay = ({ov}: {ov: (typeof data.overlays)[number]}, i: number) => (
		<Sequence
			key={`${ov.type}-${i}`}
			from={ov.startFrame}
			durationInFrames={Math.max(1, ov.durationInFrames)}
			name={`${ov.type}${typeof ov.text === 'string' ? `: ${ov.text.slice(0, 24)}` : ''}`}
		>
			<OverlayView ov={ov} theme={theme} />
		</Sequence>
	);

	return (
		<VoiceContext.Provider value={data.voice ?? []}>
		<AbsoluteFill style={{backgroundColor: theme.bg}}>
			<ARoll data={data} />
			{below.map(renderOverlay)}
			{data.letterbox ? (
				<>
					<AbsoluteFill style={{top: 0, bottom: 'auto', height: '9%', background: '#000'}} />
					<AbsoluteFill style={{top: 'auto', bottom: 0, height: '9%', background: '#000'}} />
				</>
			) : null}
			{data.captions ? <Captions data={data.captions} theme={data.theme} /> : null}
			{above.map(renderOverlay)}
			{data.music ? (
				<Audio
					src={url(data.music.src)}
					loop
					volume={musicVolume(data.music, speech, data.durationInFrames)}
				/>
			) : null}
			{data.sfx.map((cue, i) => (
				<Sequence key={`sfx-${i}`} from={cue.startFrame} name={`sfx ${cue.src.split('/').pop()}`} layout="none">
					<Audio src={url(cue.src)} volume={cue.volume} />
				</Sequence>
			))}
		</AbsoluteFill>
		</VoiceContext.Provider>
	);
};
