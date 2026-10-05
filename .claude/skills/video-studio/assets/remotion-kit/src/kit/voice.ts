// Speech loudness per output frame (0–1), computed by build_edit.py from the kept audio.
// Lets anything react to the voice: a pulsing ring, waveform bars, a breathing glow.
import {createContext, useContext} from 'react';

export const VoiceContext = createContext<number[]>([]);

/** Smoothed loudness at an absolute frame of the edit. */
export const useVoice = () => {
	const voice = useContext(VoiceContext);
	return (absFrame: number, smooth = 2) => {
		if (!voice.length) {
			return 0;
		}
		let sum = 0;
		let n = 0;
		for (let f = absFrame - smooth; f <= absFrame + smooth; f++) {
			if (f >= 0 && f < voice.length) {
				sum += voice[f];
				n++;
			}
		}
		return n ? sum / n : 0;
	};
};
