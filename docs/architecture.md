# Architecture and bounded reads

## Components

- `model.py`: integer-millisecond windows, clips, validated export settings, versioned portable JSON projects, atomic project saves.
- `media.py`: configurable tool discovery and a bounded-time metadata probe. `ffprobe` reads container/stream metadata; it does not enumerate frames or packets.
- `encoding.py`: GUI-independent FFmpeg command construction, two-pass GIF encoding, PNG extraction, pipe draining, cancellation, atomic output publication and collision handling.
- `workers.py`: sequential background encoding and asynchronous metadata/screenshot workers, connected to Qt signals. Thumbnail jobs read one bounded frame at each collected clip's start, one at a time; restore/update/source-switch results are checked against clip identity and timestamp before display.
- `timeline.py`: two-scale native painter widget. Timeline drawing uses timestamps only; selecting or opening a video does not spawn decoding jobs for a filmstrip.
- `window.py`: Qt Widgets UI, `QMediaPlayer` + `QVideoWidget`, a fixed-duration selection, collected clips, recovery and settings.
- `ui.py` / `controls.py`: independently scrollable panes, vector button/keycap painting, timecode typography, a hover-volume popup and clip delegate.
- `runtime.py`: persistent portable state beside the executable, separate from temporary single-file extraction.
- `i18n.py` / `locales/`: offline English/Japanese catalogues with Chinese source strings, named placeholders, Qt standard-dialog translations, language-aware bundled fonts, and immediate switching without rebuilding media playback.
- `smoke.py`: opt-in frozen-app end-to-end acceptance test with isolated settings.

The application uses Qt Multimedia's FFmpeg backend for playback and external FFmpeg/ffprobe for export/probing. No browser runtime, local HTTP server, OpenCV, NumPy, Electron, or full-video intermediate files are needed.

The detail timeline's drag timer pans its visible timestamp range while the pointer is held near either edge. It stops on release/hide, clamps to source bounds and keeps the fixed-duration selection intact. It does not request filmstrip frames or scan the source.

In portable releases, the independent FFmpeg/ffprobe processes are bundled in the executable and preferred over PATH. Input/output range limits are identical to source builds. Source probing and first-frame decoding remain asynchronous. On first load, playback is briefly muted to decode a first frame, then paused with the original mute setting restored. Drag/drop routing covers workspace child widgets. The default single-file build also includes interface fonts so rendering does not depend on installed font families; the application does not install fonts into the OS.

## Selection

All persisted times are integer milliseconds. `fit_window` clamps the entire selection at the video boundaries, preserving its duration whenever the video is long enough. Selection modes are current position → future, recent past → current position, and centered. Moving a window does not resize it. A local timeline can zoom between 5 seconds and 10 minutes while the overview retains the whole duration.

Clicking a queued clip restores its selection for preview or editing. Updating a queued clip is explicit. Adding a new clip copies the current start and duration; later movement does not change queued clips. An active batch takes a snapshot of the clip list and encoding settings, so the user can keep collecting new moments during export.

## GIF encoding

Each pass starts with the following **input options**:

```text
-threads 2 -ss START_SECONDS -t DURATION_SECONDS -i SOURCE
```

Input-side seeking is FFmpeg's accurate seek by default when transcoding: FFmpeg seeks near the target keyframe and discards the short preroll needed to reach the requested timestamp. Reading container metadata and indexed keyframe preroll is normal. Non-indexed/damaged files can seek more slowly; no whole-video indexing fallback is automatically started.

Pass 1:

```text
trim=duration=DURATION,setpts=PTS-STARTPTS,fps=FPS,scale=...,palettegen=stats_mode=full
```

Pass 2 reads the same bounded source range and the palette PNG:

```text
[0:v]trim=duration=DURATION,setpts=PTS-STARTPTS,fps=FPS,scale=...[v];
[v][1:v]paletteuse=dither=sierra2_4a:diff_mode=rectangle[out]
```

There is no `split` connecting a whole-video palette branch and buffered frame branch. The palette file is tiny; the second pass has a ready palette from the beginning. The longest output side is capped, with no upscaling. Audio/subtitles/data tracks are excluded. Output-side `-t` is an additional safeguard, not the input bound.

Palette generation emits its palette near the end of the selected range, so progress can remain at the beginning of the named **palette** phase for a short time. The UI always states the phase and clip number. GIF encoding then reports output timestamps through `-progress pipe:1`.

## Processes, cancellation, and failures

Jobs use subprocess argument arrays and no shell. Two reader threads continuously drain stdout/stderr, with a bounded stderr tail for actionable errors. Cancellation is polled every 50 ms, sends terminate to the active process, then kills it after a three-second grace period if necessary. Each pass has a defensive 30-minute timeout. Screenshots have a two-minute timeout.

Each job reserves a unique output name without overwriting an existing file, encodes in its own output-directory temporary folder, and publishes only after success. Unpublished reservations and temporary files are removed on handled errors/cancellation. A process/power crash can leave a zero-byte reservation or `.framepick-*` folder; the application does not recursively delete unknown folders on startup.

The GUI's recovery project and durable per-batch log make selected timestamps and errors inspectable. Logs can contain personal file paths and should be redacted before sharing. A failed clip does not abort later clips; batch cancellation does. Already completed files are retained.

## Testing scope

Tests generate a 60-second colored video with Unicode and quoted paths, and a three-hour 160×90 / 1 FPS video. They check boundaries, project round trips, exact output GIF duration and frames, selected scene color, original-resolution screenshots, duplicate output protection, live cancellation, large stderr drainage, and a regression that counts frames entering palette generation from the three-hour source. A native Qt test also loads and decodes a video, collects two clips, exports both and takes a screenshot.

These tests establish functional bounds; the tiny three-hour fixture does not imply a universal export-speed guarantee for high-resolution or unusual codecs. Native packages must be tested on their corresponding platforms. CI configuration is not evidence that an unrun remote job passed.
