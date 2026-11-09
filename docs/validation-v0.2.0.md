# FramePick 0.2.0 validation — 2026-11-10

## Requested behavior

- Layout uses independent scrollable panes, explicit splitter spacing, and a styled menu bar. The 900×600, 1024×700 and 1330×920 layouts have no horizontal content overflow or overlap; numeric editors remain readable inside their frames.
- Buttons paint scalable icons and keyboard keycaps. Timecodes use JetBrains Mono, and the main interface uses Noto Sans SC. Both are loaded from application resources without system font installation.
- Play/pause and mute are icon buttons with shortcut tooltips. Hovering the volume icon opens a separate slider without changing the playback row's width.
- Local file drops are routed from the video widget, collected-clip viewport and output input to the video/project loader, without replacing input text with dropped URLs.
- First import silently decodes one frame and pauses, preserving the previous mute setting. Tests cover both initially muted and initially unmuted states.
- Up/down shortcuts recall collected clips. Text inputs retain their normal editing shortcuts.

## Checks completed on Windows

- **41 tests passed**, including real FFmpeg, native Qt decoding, first-frame behavior, drag/drop routing, keyboard navigation, hover volume, and the original three-hour bounded-read regression.
- Layout tests separately passed at Qt scale factors **1.0, 1.5, and 2.0**, with the three window sizes above.
- Ruff lint and format checks passed.
- Desktop inspection of the actual 0.2.0 executable confirmed the unobstructed menu/panel layout and a visible paused first frame of the non-private demo video at 00:00:00.

## Self-contained executable

The Windows artifact is `dist/FramePick-0.2.0-windows-amd64.exe`, approximately **166.3 MiB**. It contains CPython, Qt, playback libraries, the interface fonts, and independent ffmpeg/ffprobe executables. The media tools are the pinned LGPL n9.0.2-48-gd4070a14ce build; hashes, source URLs and recipe information are recorded in `packaging/media-tools.json` and the embedded provenance notice.

`scripts/check_bundle.py` copied **only the executable** into a separate directory, cleared PATH and developer tool overrides, and ran the frozen application's self-test. The report confirmed:

- `ffmpeg_origin` and `ffprobe_origin` were both **内置工具**.
- The tool path was inside the executable's temporary `_MEI.../bin` extraction directory.
- Required ASCII, numeric and Chinese interface glyphs were present in the bundled font.
- The first frame appeared without a play click.
- Actual 960×540 video frames decoded successfully.
- Two independent GIFs and one PNG screenshot were produced.

The single file extracts its runtime into a temporary directory at startup. Persistent portable settings are stored beside the executable in `FramePick.data/`, with a user-data fallback for read-only locations.

## Remaining platform validation

The Linux workflow produces a self-contained single executable using a pinned static LGPL tool build, and macOS supports single-file and `.app` directory builds. These configurations have not been run on Linux/macOS in this Windows session. A Linux desktop/display service and compatible glibc remain operating-system requirements. Corresponding platform execution and signing/notarization are still separate release checks.
