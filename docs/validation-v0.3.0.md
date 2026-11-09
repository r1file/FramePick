# FramePick 0.3.0 validation — 2026-11-10

Windows 11 x64, Python 3.12, PySide6 6.12.0, pinned embedded FFmpeg/ffprobe.

- Full source suite: **58 passed**. Ruff lint and formatting checked.
- English, Simplified Chinese and Japanese OOBE/layout checks cover 900×600, 1024×700 and 1330×920 logical pixels. The locale/layout cases also pass at 150% and 200% scale.
- Playback-speed edit rectangles hold every available rate, including `0.5×`, while reserving the separate arrow area. Combo/spin arrows are painted as native vectors.
- Restoring three unvisited red/green/blue clips generates correctly colored thumbnails without seeking the player to those clips. The delegate's painted pixels are also checked, preventing a model-only false positive.
- A held drag scrolls the detail timeline continuously in both directions; release stops the timer. Source/selection bounds are enforced.
- English/Japanese catalogues cover all statically translated UI strings; named placeholders/format specifiers match. Qt dialog button catalogues and required language glyphs are tested.
- Switching language preserves clip data, selected row and playback position. Settings persist the selected language.

The frozen bundle check is run separately for all three languages, using only a copied executable, an empty PATH, isolated preferences and no developer media-tool overrides. It verifies the first-run welcome, font glyphs, paused first frame, playback, thumbnails, two independent GIFs and a PNG snapshot. Reports remain local under `artifacts/portable-v030-*` and contain no private video assets.

These checks exercise Windows. Cross-platform CI/build workflows are provided; their current run results are the authority for Linux/macOS packaging status. Platform media/display behavior still warrants real-device testing.
