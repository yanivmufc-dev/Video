// Mixed Hebrew + English, done right.
// Words are laid out one by one in an RTL flex row, so a run of English words would come
// out reversed ("Code Claude"). Consecutive LTR words are grouped into one left-to-right
// run instead. Never reverse strings or use row-reverse to "fix" order — that double-flips.
// A token is "LTR" when it has Latin letters/digits and no Hebrew ("Claude", "2026", "MD.").
const HEBREW = /[\u0590-\u05FF]/;
const LATIN = /[A-Za-z0-9]/;
export const isLtr = (text: string) => LATIN.test(text) && !HEBREW.test(text);

/** Split tokens into runs; consecutive LTR tokens form one run that is laid out left-to-right. */
export const toRuns = <T extends {text: string}>(tokens: T[]): Array<{ltr: boolean; items: Array<{t: T; i: number}>}> => {
	const runs: Array<{ltr: boolean; items: Array<{t: T; i: number}>}> = [];
	tokens.forEach((t, i) => {
		const ltr = isLtr(t.text);
		const last = runs[runs.length - 1];
		if (last && ltr && last.ltr) {
			last.items.push({t, i});
		} else {
			runs.push({ltr, items: [{t, i}]});
		}
	});
	return runs;
};


/** "Code," -> ["Code", ","]: trailing punctuation must stay OUTSIDE an LTR run, or it lands
 *  on the wrong side in Hebrew ("Claude Code," would read as ",Claude Code"). */
export const splitTrailingPunct = (text: string): [string, string] => {
	const m = /^(.*?)([.,!?;:…"'”)]+)$/u.exec(text);
	return m && m[1] ? [m[1], m[2]] : [text, ''];
};
