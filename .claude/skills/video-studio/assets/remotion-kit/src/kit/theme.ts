// Fonts + default look. Only Hebrew+Latin subsets and the weights we use are loaded:
// loading everything makes renders time out (and Remotion 5 will require the narrowing).
import {loadFont as alef} from '@remotion/google-fonts/Alef';
import {loadFont as assistant} from '@remotion/google-fonts/Assistant';
import {loadFont as frankRuhl} from '@remotion/google-fonts/FrankRuhlLibre';
import {loadFont as heebo} from '@remotion/google-fonts/Heebo';
import {loadFont as ibmPlexHebrew} from '@remotion/google-fonts/IBMPlexSansHebrew';
import {loadFont as karantina} from '@remotion/google-fonts/Karantina';
import {loadFont as notoHebrew} from '@remotion/google-fonts/NotoSansHebrew';
import {loadFont as rubik} from '@remotion/google-fonts/Rubik';
import {loadFont as secularOne} from '@remotion/google-fonts/SecularOne';
import {loadFont as suezOne} from '@remotion/google-fonts/SuezOne';
import {loadFont as varelaRound} from '@remotion/google-fonts/VarelaRound';
import type {Theme} from './types';

const subsets: Array<'hebrew' | 'latin'> = ['hebrew', 'latin'];

// name in plan.json -> loader. Heavy weights for captions, regular for body text.
const FONT_LOADERS: Record<string, () => {fontFamily: string}> = {
	Heebo: () => heebo('normal', {weights: ['500', '700', '800', '900'], subsets}),
	Rubik: () => rubik('normal', {weights: ['500', '700', '800', '900'], subsets}),
	Assistant: () => assistant('normal', {weights: ['600', '800'], subsets}),
	'Secular One': () => secularOne('normal', {weights: ['400'], subsets}),
	'Suez One': () => suezOne('normal', {weights: ['400'], subsets}),
	'Varela Round': () => varelaRound('normal', {weights: ['400'], subsets}),
	'Frank Ruhl Libre': () => frankRuhl('normal', {weights: ['500', '800'], subsets}),
	'Noto Sans Hebrew': () => notoHebrew('normal', {weights: ['500', '800'], subsets}),
	'IBM Plex Sans Hebrew': () => ibmPlexHebrew('normal', {weights: ['500', '700'], subsets}),
	Karantina: () => karantina('normal', {weights: ['700'], subsets}),
	Alef: () => alef('normal', {weights: ['700'], subsets}),
};

const loaded: Record<string, string> = {};

export const fontFamily = (name: string | undefined, fallback = 'Heebo'): string => {
	const key = name && FONT_LOADERS[name] ? name : fallback;
	if (!loaded[key]) {
		loaded[key] = FONT_LOADERS[key]().fontFamily;
	}
	return loaded[key];
};

export const AVAILABLE_FONTS = Object.keys(FONT_LOADERS);

export const DEFAULT_THEME: Required<Theme> = {
	accent: '#FFD400',
	text: '#FFFFFF',
	bg: '#000000',
	font: 'Heebo',
	displayFont: 'Secular One',
};

export const resolveTheme = (t: Theme | undefined): Required<Theme> => ({...DEFAULT_THEME, ...(t ?? {})});

// Hebrew needs an explicit direction; Latin/number runs inside it are isolated per token.
export const RTL_TEXT: React.CSSProperties = {direction: 'rtl', unicodeBidi: 'plaintext'};

// Text that must stay readable over any footage.
export const OUTLINE = (px: number, color = '#000'): React.CSSProperties => ({
	WebkitTextStroke: `${px}px ${color}`,
	paintOrder: 'stroke fill',
	textShadow: `0 ${Math.round(px * 0.8)}px ${Math.round(px * 2)}px rgba(0,0,0,0.45)`,
});
