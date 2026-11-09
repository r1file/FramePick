"""Build a self-contained portable executable, or an optional directory bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

from framepick import __version__

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--mode", choices=("onefile", "onedir"), default="onefile")
parser.add_argument(
    "--no-tools", action="store_true", help="Developer-only build without media tools"
)
args = parser.parse_args()
if not args.no_tools:
    from prepare_media import prepare

    prepare(from_system=sys.platform == "darwin")
build_environment = os.environ.copy()
build_environment["FRAMEPICK_BUNDLE_MODE"] = args.mode
build_environment["FRAMEPICK_BUNDLE_TOOLS"] = "0" if args.no_tools else "1"
if sys.platform == "win32":
    # PyInstaller resolves native dependencies through PATH. A developer's tools
    # (e.g. Poppler/Conda) can supply an unrelated icuuc.dll that shadows Windows
    # system ICU and breaks QtCore only in the frozen app. Keep this build hermetic.
    import PySide6
    import shiboken6

    windows = Path(os.environ.get("SystemRoot", "C:/Windows"))
    build_environment["PATH"] = os.pathsep.join(
        map(
            str,
            [
                Path(sys.executable).parent,
                Path(sys.base_prefix),
                Path(PySide6.__file__).parent,
                Path(shiboken6.__file__).parent,
                windows / "System32",
                windows,
            ],
        )
    )
subprocess.run([sys.executable, str(root / "scripts" / "make_icon.py")], check=True)
subprocess.run(
    [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        str(root / "packaging" / "FramePick.spec"),
    ],
    cwd=root,
    check=True,
    env=build_environment,
)
name = f"FramePick-{__version__}-{platform.system().lower()}-{platform.machine().lower()}"
dist = root / "dist"
source = (
    dist / ("FramePick.exe" if sys.platform == "win32" else "FramePick")
    if args.mode == "onefile"
    else dist / ("FramePick.app" if sys.platform == "darwin" else "FramePick")
)
manifest = {
    "app_version": __version__,
    "python": platform.python_version(),
    "system": platform.platform(),
    "bundled_tools": not args.no_tools,
    "mode": args.mode,
    "runtime_packages": {
        name: version(name)
        for name in ("PySide6-Essentials", "PySide6-Addons", "shiboken6", "pyinstaller")
    },
}
(dist / f"{name}.build-info.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
if args.mode == "onefile":
    archive = dist / (f"{name}.exe" if sys.platform == "win32" else name)
    shutil.copy2(source, archive)
    archive.chmod(0o755)
else:
    archive = Path(shutil.make_archive(str(dist / name), "zip", dist, source.name))
with archive.open("rb") as stream:
    digest = hashlib.file_digest(stream, "sha256").hexdigest()
(dist / f"{archive.name}.sha256").write_text(f"{digest}  {archive.name}\n", encoding="ascii")
print(f"Built {archive} ({archive.stat().st_size / 1024**2:.1f} MiB)")
