// Your own animations live here. Each component receives {ov, theme}:
//   ov    = the overlay entry from edit.json (startFrame, durationInFrames + your props)
//   theme = resolved colors/fonts
// Use useCurrentFrame() for timing — frame 0 is the overlay's first frame.
// Register it below, then in plan.json: {"type": "custom", "component": "MyThing", "at": ..., "dur": ...}
import type React from 'react';
import type {OverlayProps} from '../kit/overlays/types';

export const CUSTOM: Record<string, React.FC<OverlayProps>> = {};
