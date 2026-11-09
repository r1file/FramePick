"""Exercise the frozen executable, including its actual media plugins."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--video", type=Path, default=Path("artifacts/demo/Evening Lake.mp4"))
parser.add_argument("--report-dir", type=Path, default=Path("artifacts/package-check"))
parser.add_argument("--mode", choices=("onefile", "onedir"), default="onefile")
parser.add_argument("--language", choices=("en", "zh_CN", "ja"), default="zh_CN")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
if args.mode == "onefile":
    executable = root / "dist" / ("FramePick.exe" if sys.platform == "win32" else "FramePick")
elif sys.platform == "darwin":
    executable = root / "dist" / "FramePick.app" / "Contents" / "MacOS" / "FramePick"
else:
    executable = (
        root / "dist" / "FramePick" / ("FramePick.exe" if sys.platform == "win32" else "FramePick")
    )
args.report_dir.mkdir(parents=True, exist_ok=True)
if args.mode == "onefile":
    # Copy ONLY the executable, and remove PATH and developer overrides from the child.
    isolated = args.report_dir.resolve() / "isolated"
    isolated.mkdir(exist_ok=True)
    copied = isolated / executable.name
    shutil.copy2(executable, copied)
    copied.chmod(0o755)
    executable = copied
report = args.report_dir.resolve() / "report.json"
environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
environment["FRAMEPICK_TEST_LANGUAGE"] = args.language
if args.mode == "onefile":
    environment["PATH"] = ""
    for key in ("FRAMEPICK_FFMPEG", "FRAMEPICK_FFPROBE", "PYTHONPATH", "PYTHONHOME"):
        environment.pop(key, None)
result = subprocess.run(
    [
        str(executable),
        "self-test",
        "--video",
        str(args.video.resolve()),
        "--report",
        str(report),
        "--screenshot",
        str(args.report_dir.resolve() / "window.png"),
    ],
    env=environment,
    timeout=180,
    **({"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}),
)
if not report.is_file():
    raise SystemExit(f"Bundle exited {result.returncode} without a self-test report")
data = json.loads(report.read_text(encoding="utf-8"))
print(json.dumps(data, ensure_ascii=True, indent=2))
if result.returncode or not data["ok"]:
    raise SystemExit(1)
if args.mode == "onefile" and (
    data["ffmpeg_origin"] not in ("内置工具", "Embedded tools", "同梱ツール")
    or data["ffprobe_origin"] not in ("内置工具", "Embedded tools", "同梱ツール")
):
    raise SystemExit("Portable executable did not use its bundled media tools")
