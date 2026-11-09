# Third-party components

FramePick's own source is MIT licensed. That license does not replace dependency licenses.

## Runtime

- **PySide6 / Qt 6.12.0 / shiboken6**: The open-source distributions include LGPLv3/GPLv3 and third-party components. FramePick uses dynamically loaded Qt libraries and does not modify or prohibit replacing them. Single-file packages temporarily extract these libraries; the MIT application source and `--mode onedir` build remain available for rebuilding and library replacement. License texts are under `licenses/` in the extracted package. Sources and license information: <https://code.qt.io/cgit/pyside/pyside-setup.git/> (v6.12.0), <https://download.qt.io/archive/qt/6.12/>, <https://doc.qt.io/qtforpython-6/licenses.html>, <https://doc.qt.io/qt-6/licenses-used-in-qt.html>.
- **Qt Multimedia's FFmpeg libraries**: These come from the selected PySide6 wheel, independently of an FFmpeg executable found on PATH. Preserve the wheel's available license/source notices and document the exact wheel version in release build records. Sources: <https://code.qt.io/cgit/qtmultimedia.git/>, <https://ffmpeg.org/download.html>.
- **CPython**: PSF License; <https://docs.python.org/3/license.html>.
- **PyInstaller bootloader**: GPL with the PyInstaller distribution exception; <https://pyinstaller.org/en/stable/license.html>.

## External FFmpeg / ffprobe executables

Default portable builds include ffmpeg and ffprobe as independent subprocesses. Windows/Linux use the LGPL variant pinned in `packaging/media-tools.json`, with a dated asset URL and verified SHA-256. `scripts/prepare_media.py` records binary hashes, version/configuration, upstream revision and build recipe in `vendor/NOTICE.txt`, and copies the provider's license texts into the package. The pinned build is n9.0.2-48-gd4070a14ce from 2026-11-09. Qt's playback libraries remain separate from the command-line tools. Upstream license information: <https://ffmpeg.org/legal.html>.

For a different provider or local/macOS build, retain these materials under `vendor/` before public distribution:

- The exact ffmpeg and ffprobe binaries in `vendor/bin/`.
- `vendor/NOTICE.txt`: build provider, version, SHA-256 values, upstream source version, complete build configuration, exact corresponding source/download location, and license information.
- Applicable license texts and corresponding source/build materials required by that particular build. Include these materials in the distributed package, not only in a private working directory.

The build rejects missing tools or provenance notices and verifies pinned archive/binary hashes. Local/system builds must retain their provider's corresponding source, build and license materials. Choosing a different build does not change that build's license.

## Interface fonts

Noto Sans, Noto Sans SC, Noto Sans JP and JetBrains Mono are included under the SIL Open Font License 1.1. Their license texts and exact upstream URLs, revisions and SHA-256 hashes are kept in `assets/fonts/` and copied into the executable. The application loads the fonts directly, without installing them into the operating system. UI font order follows the selected language to preserve Japanese/Chinese glyph forms; other scripts use Qt's system fallback when absent from these bundled families. No single font is claimed to cover every Unicode script. Qt's standard English, Chinese and Japanese dialog translations are included with their Qt license notices.

## Development tooling

pytest (MIT), Ruff (MIT), Pillow (MIT-CMU), setuptools (MIT), and packaging tooling are development dependencies; FramePick does not import them at runtime. Their licenses apply when distributing those tools themselves.
