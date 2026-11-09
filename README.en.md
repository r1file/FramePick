# FramePick

[简体中文](README.md) · English · [日本語](README.ja.md)

Collect moments from long local videos using an adjustable time window, then export each clip as a separate GIF. Native Qt desktop UI, FFmpeg subprocesses, no server, account, video upload, full-video import or scene scan.

## Get started

Download the Windows single-file portable executable from [Releases](https://github.com/r1file/FramePick/releases). It includes Python, Qt, FFmpeg/ffprobe and interface fonts. Run it directly; nothing needs installing. The self-extracting executable needs temporary disk space at startup. Settings and recovery data live in `FramePick.data` beside it, with a user-data fallback for read-only locations.

1. Open or drop a video. Its first frame appears automatically, paused.
2. Move the default **5-second** window; change its duration or anchor as needed.
3. Press **A** to collect, **L** to loop, **S** to save a full-resolution PNG.
4. Collect several clips and choose **Export all GIFs**. Each gets its own file.

**Space** plays/pauses; **M** mutes; hover over the speaker for volume. **↑ / ↓** recalls collected clips. Zoom the detail timeline with the wheel; hold a dragged window at an edge to scroll. A background single-frame extraction supplies thumbnails even for unvisited clips restored from a project.

English, Simplified Chinese and Japanese are built in. The language picker switches immediately without losing your work. First launch follows the system language (other languages fall back to English). Noto Sans / SC / JP and JetBrains Mono are bundled under SIL OFL; other scripts can use Qt's system font fallback. This is not a claim of coverage for every Unicode script.

## Bounded exports

Both palette and encode passes seek **before** opening the source (`-ss START -t DURATION -i SOURCE`), then trim before filtering. Playback reads on demand. Seeking compressed video still involves container metadata and decoding near a preceding keyframe. No full-video frame extraction is performed. GIF is silent; HDR tone mapping, subtitles and DRM are not currently supported.

## Develop

Python 3.11+ (CI: 3.12), PowerShell 7 on Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m framepick
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/build.py
```

On Linux/macOS use `.venv/bin/python`. The build downloads hash-pinned Windows/Linux media tools; source runs can use system FFmpeg or staged tools. Build on the target OS; Linux needs a compatible desktop stack and glibc. The build workflow supplies Windows/Linux/macOS jobs; see their actual status before assuming platform support. macOS packages are unsigned.

```text
python -m ruff check .
python -m ruff format --check .
python scripts/check_bundle.py --language en
```

The bundle check copies only the executable into isolation, clears PATH and tool overrides, and checks the welcome screen, fonts, first frame, playback, clip thumbnails, two GIF exports and a snapshot. `--language zh_CN` and `--language ja` exercise the other catalogues.

See [architecture](docs/architecture.md), [contributing](CONTRIBUTING.md), and [third-party notices](THIRD_PARTY_NOTICES.md). Application code is [MIT](LICENSE); dependency licenses are separate.
