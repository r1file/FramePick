# Validation record — 2026-11-10

Initial local validation on Windows 11 x64, Python 3.12.10, PySide6 6.12.0, external FFmpeg 9.0.1. These are observed results on one machine, not general performance guarantees.

## Functional suite

`python -m pytest -q`: **30 passed**, including native Qt playback/selection/export/screenshot tests and real FFmpeg integration tests. Ruff lint and format checks pass.

The three-hour synthetic source is 160×90 at 1 FPS. Requesting five seconds near its beginning fed only **5 source frames** into palette generation. Exporting five seconds near 2h38m also produced a 25-frame, five-second GIF at 5 FPS. This guards the whole-remainder palette-processing regression without interpreting the small fixture as a high-resolution benchmark.

The cross-scene test selects a subsecond start before a known color transition and checks the resulting GIF frames. `palettegen=stats_mode=diff` dropped a scene color in the tested FFmpeg build; the default is therefore `stats_mode=full`, still confined to the selected range.

## Real long-source export

Source: local 1920×1080 HEVC, 29.97 FPS, duration **10,154.221 seconds** (about 2h49m). The source filename, content and output are not included in the repository.

Request: start 2,291.154 seconds, duration 5 seconds, maximum side 480px, 15 FPS.

| Measurement | Observed |
| --- | --- |
| Output duration | 5,000 ms |
| Output dimensions | 480×270 |
| Output size | 3,921,289 bytes |
| Total two-pass export time | 3.468 seconds |
| Palette process peak working set | 119,799,808 bytes (114.3 MiB) |
| GIF process peak working set | 135,204,864 bytes (128.9 MiB) |

`scripts/benchmark.py` can repeat this measurement with another source. The memory values are the **FFmpeg child processes'** peak working sets, not total desktop/application memory.

## Frozen Windows bundle

The final windowed PyInstaller executable passed `scripts/check_bundle.py`: actual 960×540 decoded frames, two independent two-second GIFs, and one PNG screenshot, with no reported errors. ZIP size is approximately **51.3 MiB**; independent FFmpeg / ffprobe command-line tools are discovered from the local system and are not included in that ZIP.

An initial frozen build failed because dependency resolution copied an unrelated `icuuc.dll` from the development host's Poppler PATH entry. Qt requires Windows system ICU. The Windows build now uses an isolated PATH and rejects a collected foreign `icuuc.dll`. Rebuilding and rerunning the frozen-app self-test passed.

Desktop automation was stopped by the user's physical Escape key, so manual mouse/keyboard inspection of the final native window was not completed. Programmatic native Qt and frozen-app checks above were completed afterward without desktop input automation.

## Other platforms

Windows/macOS/Linux test and package workflows are supplied in `.github/workflows/`. Remote GitHub Actions were not run during this local session. macOS/Linux build, playback, packaging, signing and platform-specific dependencies still require validation on those platforms before a public release.
