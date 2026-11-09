"""Portable state lives beside a frozen executable, never in its extraction dir."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths


def state_directory() -> Path:
    if getattr(sys, "frozen", False):
        path = Path(sys.executable).resolve().parent / "FramePick.data"
        try:
            path.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryFile(dir=path):
                pass
            return path
        except OSError:
            pass
    return Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))


def app_preferences() -> QSettings:
    if not getattr(sys, "frozen", False):
        return QSettings("FramePick", "FramePick")
    path = state_directory() / "settings.ini"
    exists = path.exists()
    settings = QSettings(str(path), QSettings.Format.IniFormat)
    if not exists:
        legacy = QSettings("FramePick", "FramePick")
        for key in ("output_dir", "last_directory"):
            if legacy.contains(key):
                settings.setValue(key, legacy.value(key))
    return settings
