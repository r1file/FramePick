from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
from dataclasses import asdict
from pathlib import Path

from framepick import __version__


def main() -> int:
    parser = argparse.ArgumentParser(description="FramePick: collect moments, export bounded GIFs.")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--open", type=Path, help="Open a local video")
    parser.add_argument("--project", type=Path, help="Open a saved .framepick.json project")
    subparsers = parser.add_subparsers(dest="command")
    doctor = subparsers.add_parser("doctor", help="Print tool locations and metadata")
    doctor.add_argument("--video", type=Path)
    export = subparsers.add_parser("export", help="Export a project without starting Qt")
    export.add_argument("project_file", type=Path)
    export.add_argument("--output", type=Path, required=True)
    smoke = subparsers.add_parser("self-test", help="Exercise packaged Qt playback and export")
    smoke.add_argument("--video", type=Path, required=True)
    smoke.add_argument("--report", type=Path, required=True)
    smoke.add_argument("--screenshot", type=Path)
    args = parser.parse_args()
    if args.command == "self-test":
        from framepick.smoke import run

        return run(args.video, args.report, args.screenshot)
    if args.command:
        from framepick.encoding import Cancelled, export_gif
        from framepick.media import Tools, probe
        from framepick.model import Project

        try:
            tools = Tools.discover()
            if args.command == "doctor":
                data = {
                    "version": __version__,
                    "ffmpeg": str(tools.ffmpeg),
                    "ffprobe": str(tools.ffprobe),
                }
                if args.video:
                    data["media"] = asdict(probe(args.video, tools))
                print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
                return 0
            project = Project.load(args.project_file)
            info = probe(project.source, tools)
            if any(clip.end_ms > info.duration_ms + 100 for clip in project.clips):
                raise ValueError("A clip extends beyond the source video.")
            cancel = threading.Event()
            signal.signal(signal.SIGINT, lambda *_: cancel.set())
            failed = False
            for clip in project.clips:
                try:
                    output = export_gif(
                        tools, project.source, clip, project.settings, args.output, cancel
                    )
                    print(str(output), flush=True)
                except Cancelled:
                    return 130
                except Exception as exc:
                    failed = True
                    print(f"{clip.id}: {exc}", file=sys.stderr)
            return 1 if failed else 0
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            return 1

    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from framepick.window import MainWindow

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs)
    app = QApplication(sys.argv[:1])
    from framepick.theme import configure_application

    configure_application(app)
    app.setApplicationName("FramePick")
    app.setOrganizationName("FramePick")
    app.setApplicationVersion(__version__)
    resource_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    icon = resource_root / "assets" / "framepick.png"
    if icon.is_file():
        app.setWindowIcon(QIcon(str(icon)))
    window = MainWindow()
    window.show()
    if args.open:
        QTimer.singleShot(0, lambda: window.load_video(args.open))
    elif args.project:
        QTimer.singleShot(0, lambda: window.load_project(args.project))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
