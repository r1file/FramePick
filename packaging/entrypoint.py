"""PyInstaller entry point; keep the application entry point in the package."""

import tempfile
import traceback
from pathlib import Path

try:
    from framepick.__main__ import main

    raise SystemExit(main())
except Exception:
    # This also works if importing Qt fails before the application can show a UI.
    log = Path(tempfile.gettempdir()) / "FramePick-startup-error.log"
    log.write_text(traceback.format_exc(), encoding="utf-8")
    raise
