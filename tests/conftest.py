from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from framepick.media import Tools, hidden_process_options


@pytest.fixture(scope="session")
def tools():
    try:
        return Tools.discover()
    except FileNotFoundError:
        pytest.skip("FFmpeg and ffprobe are required for integration tests")


@pytest.fixture(scope="session")
def video(tmp_path_factory, tools) -> Path:
    directory = tmp_path_factory.mktemp("media")
    output = directory / "sample space ' unicode_测试.mp4"
    graph = (
        "color=c=red:s=160x90:r=10:d=20[r];"
        "color=c=green:s=160x90:r=10:d=20[g];"
        "color=c=blue:s=160x90:r=10:d=20[b];"
        "[r][g][b]concat=n=3:v=1:a=0"
    )
    subprocess.run(
        [
            str(tools.ffmpeg),
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            graph,
            "-c:v",
            "mpeg4",
            "-q:v",
            "3",
            "-g",
            "20",
            str(output),
        ],
        check=True,
        capture_output=True,
        timeout=40,
        **hidden_process_options(),
    )
    return output


@pytest.fixture(scope="session")
def long_video(tmp_path_factory, tools) -> Path:
    output = tmp_path_factory.mktemp("long-media") / "three-hours.mp4"
    subprocess.run(
        [
            str(tools.ffmpeg),
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=yellow:s=160x90:r=1:d=10800",
            "-c:v",
            "mpeg4",
            "-g",
            "10",
            str(output),
        ],
        check=True,
        capture_output=True,
        timeout=60,
        **hidden_process_options(),
    )
    return output


@pytest.fixture(scope="session")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from framepick.theme import configure_application

    configure_application(app)
    app.setApplicationName("FramePickTests")
    app.setOrganizationName("FramePickTests")
    # Tests must never write production settings.
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    yield app
