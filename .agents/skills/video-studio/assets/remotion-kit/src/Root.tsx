// Every project built with tools/build_edit.py shows up here as its own composition.
// Open the Studio (./studio preview) to scrub, tweak and render any of them.
import React from 'react';
import {Composition} from 'remotion';
import {Edit} from './kit/Edit';
import {fontFamily} from './kit/theme';
import type {EditData} from './kit/types';
import {projects} from './projects';

// Load each font a project uses once, up front (fonts must be ready before frames render).
for (const p of projects) {
	fontFamily(p.theme?.font);
	fontFamily(p.theme?.displayFont, 'Secular One');
	fontFamily(p.captions?.font ?? p.theme?.font);
}

const EditComposition: React.FC<{data: EditData}> = ({data}) => <Edit data={data} />;

export const RemotionRoot: React.FC = () => {
	return (
		<>
			{projects.map((p) => (
				<Composition
					key={p.id}
					id={p.id}
					component={EditComposition}
					durationInFrames={p.durationInFrames}
					fps={p.fps}
					width={p.width}
					height={p.height}
					defaultProps={{data: p}}
				/>
			))}
		</>
	);
};
