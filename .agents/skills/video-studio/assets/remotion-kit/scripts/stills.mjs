// Render many single frames with ONE bundle (much faster than `remotion still` per frame).
// Usage (from remotion/):  node scripts/stills.mjs <outDir> <scale> <compositionId>@<frame> ...
// Prints one output path per line. Used by `studio stills` and `studio styles`.
import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
import fs from 'node:fs';
import path from 'node:path';

const [outDir, scaleArg, ...jobs] = process.argv.slice(2);
if (!outDir || !jobs.length) {
	console.error('usage: node scripts/stills.mjs <outDir> <scale> <id>@<frame> ...');
	process.exit(2);
}
fs.mkdirSync(outDir, {recursive: true});
const scale = Number(scaleArg) || 0.5;
const chromiumOptions = {gl: 'angle'}; // same GPU backend as remotion.config.ts (effects need WebGL)
const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts'), onProgress: () => undefined});
const comps = new Map();
for (const job of jobs) {
	const at = job.lastIndexOf('@');
	const id = job.slice(0, at);
	const frame = Number(job.slice(at + 1));
	if (!comps.has(id)) {
		comps.set(id, await selectComposition({serveUrl, id, chromiumOptions, timeoutInMilliseconds: 120000}));
	}
	const composition = comps.get(id);
	const output = path.resolve(outDir, `${id}_${String(frame).padStart(5, '0')}.png`);
	await renderStill({
		composition,
		serveUrl,
		output,
		frame: Math.min(composition.durationInFrames - 1, Math.max(0, frame)),
		scale,
		imageFormat: 'png',
		chromiumOptions,
		timeoutInMilliseconds: 120000,
		overwrite: true,
	});
	console.log(output);
}
