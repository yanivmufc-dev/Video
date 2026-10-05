// "Looks": a color grade on the speaker footage (GPU effects from @remotion/effects, rendered
// with the angle GL backend set in remotion.config.ts). plan.json: "look": "cinematic".
import {chromaticAberration} from '@remotion/effects/chromatic-aberration';
import {colorCorrection} from '@remotion/effects/color-correction';
import {grayscale} from '@remotion/effects/grayscale';
import {scanlines} from '@remotion/effects/scanlines';
import {vignette} from '@remotion/effects/vignette';
import {whiteNoise} from '@remotion/effects/white-noise';

export const LOOKS = ['none', 'natural', 'punchy', 'cinematic', 'warm', 'cool', 'bw', 'vintage', 'vhs', 'neon'] as const;

// Note: no `vibrance` — it boosts low-saturation areas unevenly and turns dark, noisy hair
// green/magenta on phone footage. Uniform `saturation` is safe.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const lookEffects = (look: string | undefined): any[] => {
	switch (look) {
		case 'natural':
			return [colorCorrection({contrast: 1.04, saturation: 1.04})];
		case 'punchy':
			return [colorCorrection({contrast: 1.12, saturation: 1.12, blacks: -0.03})];
		case 'cinematic':
			return [
				colorCorrection({contrast: 1.12, saturation: 0.86, temperature: 0.08, highlights: -0.08, blacks: -0.04}),
				vignette({amount: 0.4, radius: 0.62, feather: 0.45}),
			];
		case 'warm':
			return [colorCorrection({temperature: 0.18, saturation: 1.05, highlights: -0.05, contrast: 1.04}), vignette({amount: 0.25})];
		case 'cool':
			return [colorCorrection({temperature: -0.16, contrast: 1.05, saturation: 1.02})];
		case 'bw':
			return [grayscale({amount: 1}), colorCorrection({contrast: 1.2, blacks: -0.05}), vignette({amount: 0.35})];
		case 'vintage':
			return [
				colorCorrection({saturation: 0.72, temperature: 0.16, contrast: 0.92, blacks: 0.07}),
				whiteNoise({amount: 0.05, seed: 3}),
				vignette({amount: 0.45}),
			];
		case 'vhs':
			return [
				colorCorrection({saturation: 1.12, contrast: 1.04, blacks: 0.05, temperature: 0.05}),
				chromaticAberration({amount: 0.35}),
				scanlines({amount: 0.18}),
				whiteNoise({amount: 0.07, seed: 7}),
			];
		case 'neon':
			return [colorCorrection({contrast: 1.1, saturation: 1.12, temperature: -0.12, highlights: -0.15}), vignette({amount: 0.35})];
		default:
			return [];
	}
};
