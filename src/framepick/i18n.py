"""Small offline catalogues. Keys are source strings; placeholders are named.

Qt's own catalogue translates standard dialog buttons. Application catalogues
have no network/runtime dependency and can be extended with another JSON file.
"""

from __future__ import annotations

import json
import os
import re
import string
from pathlib import Path

_ROOT = Path(__file__).with_name("locales")
CATALOGS = {
    code: json.loads((_ROOT / f"{code}.json").read_text(encoding="utf-8")) for code in ("en", "ja")
}
LANGUAGES = {"en": "English", "zh_CN": "简体中文", "ja": "日本語"}
_language = "zh_CN"
_qt_translator = None


def current_language() -> str:
    return _language


def system_language() -> str:
    from PySide6.QtCore import QLocale

    code = os.environ.get("FRAMEPICK_LANGUAGE") or QLocale.system().name()
    return "zh_CN" if code.startswith("zh") else "ja" if code.startswith("ja") else "en"


def tr(source: str, **values) -> str:
    translated = CATALOGS.get(_language, {}).get(source, source)
    return translated.format(**values) if values else translated


def set_language(code: str):
    global _language, _qt_translator
    if code not in LANGUAGES:
        code = system_language()
    _language = code
    from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app:
        if _qt_translator:
            app.removeTranslator(_qt_translator)
        _qt_translator = QTranslator(app)
        location = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        locale = "zh_CN" if code == "zh_CN" else "ja" if code == "ja" else "en_US"
        qt_locale = "en" if code == "en" else locale
        if _qt_translator.load(f"qtbase_{qt_locale}", location):
            app.installTranslator(_qt_translator)
        QLocale.setDefault(QLocale(locale))
        from framepick.theme import apply_language_font

        apply_language_font(app, code)


def translate_existing(text: str, previous: str) -> str:
    old = CATALOGS.get(previous, {})
    source = next((key for key, value in old.items() if value == text), text)
    if source != text or source in CATALOGS["en"]:
        return tr(source)
    # Refresh already-formatted status messages on an immediate language switch.
    # Preserve their displayed numeric formatting and translate embedded states.
    formatter = string.Formatter()
    for key in CATALOGS["en"]:
        template = old.get(key, key)
        parts = list(formatter.parse(template))
        fields = [name for _, name, _, _ in parts if name is not None]
        if not fields:
            continue
        pattern = "".join(
            re.escape(literal) + ("(.+?)" if name is not None else "")
            for literal, name, _, _ in parts
        )
        match = re.fullmatch(pattern, text, re.DOTALL)
        if match:
            values = {
                name: tr(next((k for k, v in old.items() if v == value), value))
                for name, value in zip(fields, match.groups(), strict=True)
            }
            return "".join(
                literal + (values[name] if name is not None else "")
                for literal, name, _, _ in formatter.parse(tr(key))
            )
    return text


def retranslate_tree(root, previous: str):
    """Retranslate static labels without rebuilding the player or editing state.

    User text (paths, time input, file labels) is deliberately excluded.
    Dynamic labels are refreshed by the owning controller afterwards.
    """
    from PySide6.QtCore import QObject
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import (
        QAbstractButton,
        QComboBox,
        QDoubleSpinBox,
        QLabel,
        QLineEdit,
        QMenu,
    )

    for obj in [root, *root.findChildren(QObject)]:
        if isinstance(obj, (QLabel, QAbstractButton, QAction)):
            obj.setText(translate_existing(obj.text(), previous))
        if isinstance(obj, QMenu):
            obj.setTitle(translate_existing(obj.title(), previous))
        if isinstance(obj, QComboBox):
            for i in range(obj.count()):
                obj.setItemText(i, translate_existing(obj.itemText(i), previous))
        if isinstance(obj, QLineEdit):
            obj.setPlaceholderText(translate_existing(obj.placeholderText(), previous))
        if isinstance(obj, QDoubleSpinBox):
            obj.setSuffix(translate_existing(obj.suffix(), previous))
        if hasattr(obj, "toolTip"):
            obj.setToolTip(translate_existing(obj.toolTip(), previous))
        if hasattr(obj, "accessibleName"):
            obj.setAccessibleName(translate_existing(obj.accessibleName(), previous))
