// Overlay registry: plan.json "type" -> component. To add your own animation, put the
// component in src/custom/ and register it in src/custom/index.ts, then use
// {"type": "custom", "component": "<Name>", ...props} in plan.json.
import React from 'react';
import {CUSTOM} from '../../custom';
import {Scene} from '../scenes/Scene';
import {Flash, Glitch, LightLeak, Vignette, Wash} from './fx';
import {Burst, Waveform} from './fun';
import {Arrow, Circle, Counter, ProgressBar} from './graphics';
import {BRoll, Emoji, Sticker} from './media';
import {Callout, Cta, Hook, List, LowerThird, Title} from './text';
import type {OverlayProps} from './types';

export const OVERLAYS: Record<string, React.FC<OverlayProps>> = {
	hook: Hook,
	title: Title,
	callout: Callout,
	lowerthird: LowerThird,
	cta: Cta,
	list: List,
	counter: Counter,
	arrow: Arrow,
	circle: Circle,
	progress: ProgressBar,
	broll: BRoll,
	image: Sticker,
	sticker: Sticker,
	emoji: Emoji,
	flash: Flash,
	lightleak: LightLeak,
	glitch: Glitch,
	vignette: Vignette,
	wash: Wash,
	scene: Scene,
	burst: Burst,
	waveform: Waveform,
};

// Default stacking (low = further back). Captions render at 50 — above all of these
// except full-frame transition effects, which briefly cover everything on a cut.
export const DEFAULT_Z: Record<string, number> = {
	broll: 10,
	scene: 30,
	burst: 58,
	vignette: 12,
	wash: 14,
	progress: 40,
	flash: 60,
	lightleak: 60,
	glitch: 60,
};

export const OverlayView: React.FC<OverlayProps> = (props) => {
	const {ov} = props;
	if (ov.type === 'custom') {
		const name = String(ov.component ?? '');
		const Comp = CUSTOM[name];
		if (!Comp) {
			throw new Error(`Custom component "${name}" is not registered in src/custom/index.ts`);
		}
		return <Comp {...props} />;
	}
	const Comp = OVERLAYS[ov.type];
	if (!Comp) {
		throw new Error(`Unknown overlay type "${ov.type}". Known: ${Object.keys(OVERLAYS).join(', ')}, custom`);
	}
	return <Comp {...props} />;
};
