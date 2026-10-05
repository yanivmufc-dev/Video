// Studio + render settings for the video studio.
// All configuration options: https://remotion.dev/docs/config
import {Config} from '@remotion/cli/config';

Config.setVideoImageFormat('jpeg');
Config.setOverwriteOutput(true);
// WebGL is needed by @remotion/effects (light leaks, grain). 'angle' is the v5 default.
// If renders hang on an old Windows PC, render with --gl=swangle instead.
Config.setChromiumOpenGlRenderer('angle');
// Phones and laptops: fonts and media sometimes need more than the 30 s default to load.
Config.setDelayRenderTimeoutInMilliseconds(120000);
Config.setPixelFormat('yuv420p');
