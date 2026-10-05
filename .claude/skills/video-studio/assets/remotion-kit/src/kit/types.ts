// The timeline format tools/build_edit.py writes and <Edit> renders.
// All times are in FRAMES of the output video. Human-facing docs: references/edit-plan.md

export type Theme = {
	accent?: string; // keyword / banner color — take it from the SUBJECT, not from a brand
	text?: string; // caption base color
	bg?: string; // canvas background (visible behind 'contain'/'blur' footage)
	font?: string; // caption + UI font (a key of FONT_LOADERS in theme.ts)
	displayFont?: string; // titles / hook font
};

export type TransitionSpec = {
	type: string; // see kit/transitions.tsx
	durationInFrames: number;
	direction?: 'from-left' | 'from-right' | 'from-top' | 'from-bottom';
	overlap: boolean; // true = real crossfade between clips (shortens the timeline)
};

export type Segment = {
	src: string; // staticFile path, e.g. p/my-reel/clip01.mp4
	startFrame: number;
	durationInFrames: number;
	trimBefore: number; // source frame where this segment starts
	zoom: number; // 1 = none; punch-ins 1.1–1.25 (never more — the forehead must stay in frame)
	zoomOrigin: string; // CSS transform-origin, top-weighted by default
	volume: number;
	fit?: 'cover' | 'contain' | 'blur'; // blur = landscape footage on a blurred fill (repurposing)
	focus?: [number, number]; // 0–1 which part stays visible in 'cover' (reframing landscape -> vertical)
	srcWidth?: number; // source pixel size (filled in by build_edit.py from the proxy)
	srcHeight?: number;
	transitionIn?: TransitionSpec; // transition from the previous segment into this one
};

export type CaptionToken = {text: string; startFrame: number; endFrame: number; keyword: boolean; emoji?: string};
export type CaptionPage = {startFrame: number; endFrame: number; tokens: CaptionToken[]};

export type CaptionStyle = 'karaoke' | 'pop' | 'box' | 'chips' | 'plain' | 'punch' | 'hormozi' | 'glow' | 'typewriter' | 'clean'; // hormozi = 1.0 name of punch

export type Captions = {
	style?: CaptionStyle;
	y?: number; // vertical center of the caption block, 0–1 of height (default 0.6 — keeps it above the app UI)
	size?: number; // font size in px at 1080 wide (default 78)
	color?: string;
	highlight?: string; // active-word / keyword color (default theme.accent)
	font?: string;
	uppercase?: boolean;
	pages: CaptionPage[];
};

export type Overlay = {
	type: string; // key in kit/overlays/index.tsx, or 'custom'
	startFrame: number;
	durationInFrames: number;
	z?: number; // stacking order; captions sit at 50, overlays default 20
	[key: string]: unknown;
};

export type SfxCue = {src: string; startFrame: number; volume: number};

export type Music = {src: string; volume?: number; duck?: number; fadeOut?: number};

export type EditData = {
	id: string;
	fps: number;
	width: number;
	height: number;
	durationInFrames: number;
	theme: Theme;
	segments: Segment[];
	captions: Captions | null;
	overlays: Overlay[];
	sfx: SfxCue[]; // normally ONE pre-mixed track of all the effect sounds (build_edit premix)
	sfxCues?: {src: string; startFrame: number}[]; // where each sound sits (for reading, not played)
	music: Music | null;
	look?: string; // color grade on the speaker footage (kit/looks.ts)
	letterbox?: boolean; // cinema bars top and bottom
	voice?: number[]; // speech loudness per output frame, 0–1 (audio-reactive elements)
};
