# Contributing

FramePick deliberately focuses on fast, manual selection from long local videos. Changes should preserve a simple sliding-window workflow.

## Development

Use Python 3.11 or newer, a virtual environment, and `pip install -e '.[dev]'`. Use PowerShell 7 for Windows commands. Run `python -m ruff check .`, `python -m ruff format --check .`, and `python -m pytest -q` before submitting changes. Integration tests require FFmpeg / ffprobe; GUI tests use Qt's offscreen plugin and a generated non-private fixture.

## Invariants

1. Never scan/decode a whole video to open it, generate a whole-video proxy, or pre-extract all frames for a GIF workspace.
2. Source encoding inputs must have input-side `-ss` and `-t`. Palette generation must receive an already-bounded range. Keep the three-hour regression test.
3. Drain stdout and stderr while a subprocess is running. A full stderr pipe must not deadlock export.
4. Cancellation terminates the actual child process and removes unpublished files. Completed GIFs survive cancellation.
5. Run only one GIF encoder at a time by default. Changes to threading and buffering need measurements on long, high-resolution sources.
6. Use argument arrays, never shell interpolation, for source paths. Test Unicode, spaces and quotes.
7. Keep domain logic and the FFmpeg engine independent from Qt. GUI code should not block on decoding, ffprobe or export.
8. Do not commit personal media, project files, logs, generated output or credentials.
9. Translate all UI strings with `tr` and update both catalogues. Keep named placeholders and format specifiers identical. Verify English, Chinese and Japanese at small window sizes and high DPI, including standard dialogs and the first-run screen.

## Releases

Build on each target OS using `python scripts/build.py`. Verify the resulting **frozen** application with `self-test` and a non-private local sample before publishing. Run a separate high-resolution long-video check; a low-resolution test does not establish 4K performance. Record package hashes and platform details. Keep third-party notices and required licenses with bundles.

CI tests Windows/macOS/Linux, while tagged builds upload artifacts for review. Default builds are self-contained single executables; `scripts/check_bundle.py` tests a copy of only that executable with an empty PATH. `--mode onedir` remains available for development and replacing dynamic libraries. Publishing a public GitHub release and signing/notarizing installers are separate maintainer steps. Update the version in `pyproject.toml`, `src/framepick/__init__.py`, and the macOS plist in `packaging/FramePick.spec`; the build script reads the package version automatically. Update pinned media providers/hashes in `packaging/media-tools.json` and retain the staged source/license provenance.
