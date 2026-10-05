import type {Overlay, Theme} from '../types';

/** ink = the text color that reads on this scene's background (white on dark, ink on light). */
export type SceneProps = {ov: Overlay; theme: Required<Theme>; ink: string};
