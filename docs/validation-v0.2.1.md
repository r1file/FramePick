# FramePick 0.2.1 — follow-up fixes, 2026-11-10

0.2.1 includes the 0.2.0 portable/UI work and addresses feedback from the visible 0.2.0 window.

## Timeline edges

The first and last tick labels previously used a centered, fixed 88-pixel rectangle. Half of the text could extend beyond the timeline's clipping region. Tick labels now use the active font's measured width, clamp their entire rectangles inside the axis, and give the two boundaries priority over intermediate labels. Nearby labels are omitted when they would collide. The exact end time is displayed even when it is not a whole second or a regular tick interval.

Regression cases cover a 30-second source, a 2h49m source ending at `.221`, and a 3-hour source. Both boundary labels remain inside the axis and do not overlap other labels.

## Editable controls and shortcuts

Plain-key shortcuts are disabled while a text input, spin box, combo box, or volume slider has focus. This prevents letters such as A/S/L/M from being swallowed and preserves normal up/down editing in numeric controls. Outside editable controls, up/down recalls collected clips as requested.

## Validation

The full suite passed **45 tests**. The window title now includes `0.2.1`, so the corrected build is distinguishable from an already running 0.2.0 instance. The release uses the same pinned embedded media tools and interface fonts as 0.2.0; the frozen executable is checked again with only the single file present, PATH cleared, and developer tool overrides removed. Linux/macOS workflows remain configured but not locally executed on this Windows host.
