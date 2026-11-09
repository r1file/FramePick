import sys
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase


def configure_application(app):
    app.setStyle("Fusion")
    resource_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    loaded = {}
    for filename in ("NotoSans.ttf", "NotoSansSC.ttf", "NotoSansJP.ttf", "JetBrainsMono.ttf"):
        path = resource_root / "assets" / "fonts" / filename
        if path.is_file():
            identifier = QFontDatabase.addApplicationFont(str(path))
            families = QFontDatabase.applicationFontFamilies(identifier)
            if families:
                loaded[filename] = families[0]
    if "JetBrainsMono.ttf" in loaded:
        app.setProperty("framepick.mono_family", loaded["JetBrainsMono.ttf"])
    app.setProperty("framepick.fonts", loaded)
    if "NotoSansSC.ttf" in loaded:
        apply_language_font(app, "zh_CN")
        return
    available = set(QFontDatabase.families())
    for family in ("Microsoft YaHei UI", "PingFang SC", "Noto Sans CJK SC", "Segoe UI"):
        if family in available:
            app.setFont(QFont(family, 10))
            break


def apply_language_font(app, language):
    loaded = app.property("framepick.fonts") or {}
    preferred = {
        "en": ("NotoSans.ttf", "NotoSansSC.ttf", "NotoSansJP.ttf"),
        "zh_CN": ("NotoSansSC.ttf", "NotoSans.ttf", "NotoSansJP.ttf"),
        "ja": ("NotoSansJP.ttf", "NotoSans.ttf", "NotoSansSC.ttf"),
    }
    families = [loaded[name] for name in preferred.get(language, preferred["en"]) if name in loaded]
    if families:
        font = QFont()
        font.setFamilies(families)
        font.setPointSize(10)
        font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        app.setFont(font)


STYLE = """
QWidget { background: #111821; color: #e5edf8; font-size: 13px; }
QMainWindow { background: #111821; }
QLabel#brand { font-size: 25px; font-weight: 700; letter-spacing: 1px; }
QLabel#subtitle, QLabel#muted { color: #92a1b5; }
QLabel#section { color: #b2c1d5; font-size: 12px; font-weight: 600; }
QFrame#panel { background: #171f2b; border: 1px solid #293546; border-radius: 9px; }
QFrame#panel QLabel { background: transparent; }
QPushButton { background: #243044; border: 1px solid #3a4a61; border-radius: 6px; padding: 0; min-height: 34px; }
QPushButton:hover { background: #30405a; border-color: #6b8baf; }
QPushButton:pressed { background: #182432; }
QPushButton:disabled { color: #586577; background: #1b2431; border-color: #283242; }
QPushButton#primary { background: #4cd2b4; border: none; color: #082b25; font-weight: 700; }
QPushButton#primary:hover { background: #79e4cb; }
QPushButton#primary:disabled { background: #254c46; color: #819e97; }
QPushButton#danger { color: #ffb2a6; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background: #0e151e; border: 1px solid #3c4d65; border-radius: 5px; padding: 6px 8px; min-height: 20px; selection-background-color: #317e75; }
QAbstractSpinBox QLineEdit { background: transparent; border: none; padding: 0; min-height: 0; }
QSpinBox::up-button, QDoubleSpinBox::up-button { width: 18px; background: #243044; border-left: 1px solid #3c4d65; border-top-right-radius: 4px; }
QSpinBox::down-button, QDoubleSpinBox::down-button { width: 18px; background: #243044; border-left: 1px solid #3c4d65; border-bottom-right-radius: 4px; }
QComboBox { padding-right: 22px; }
QComboBox::drop-down { width: 20px; border: none; }
QComboBox QAbstractItemView { background: #1e2b3d; selection-background-color: #315e62; }
QListWidget { background: #111821; border: 1px solid #2b384b; border-radius: 7px; outline: 0; }
QListWidget::item { border-bottom: 1px solid #233044; padding: 8px; }
QListWidget::item:selected { background: #203e42; color: #e4fff9; }
QListWidget::item:hover { background: #243044; }
QProgressBar { border: none; border-radius: 3px; background: #293547; height: 8px; text-align: center; }
QProgressBar::chunk { background: #4cd2b4; border-radius: 3px; }
QStatusBar { color: #9daec4; background: #111821; padding: 2px 8px; }
QStatusBar::item { border: none; }
QMenuBar { background: #111821; border-bottom: 1px solid #253347; padding: 0; }
QMenuBar::item { padding: 6px 14px; margin: 0; background: transparent; }
QMenuBar::item:selected, QMenu::item:selected { background: #294c50; }
QMenu { background: #1b2737; border: 1px solid #35445a; padding: 4px; }
QMenu::item { padding: 7px 22px; }
QToolTip { background: #26364a; color: #e5edf8; border: 1px solid #54718d; padding: 5px; }
QSplitter::handle { background: #111821; }
QScrollArea { background: #111821; border: none; }
QScrollBar:vertical { background: #131d2a; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #3b506b; min-height: 28px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QLabel#timecode { font-size: 14px; font-weight: 600; color: #dcefff; }
QFrame#volumePopup { background: #1b2839; border: 1px solid #516881; border-radius: 7px; }
QSlider::groove:horizontal { height: 4px; background: #334258; border-radius: 2px; }
QSlider::handle:horizontal { width: 12px; background: #74d7c3; margin: -4px 0; border-radius: 6px; }
"""
