# Build on each target OS. No WebEngine, browser runtime, QML UI, or network server.
import os
import sys
from importlib.metadata import distribution
from pathlib import Path
from PySide6.QtCore import QLibraryInfo

root = Path(SPECPATH).parent
tool_binaries = []
if os.environ.get("FRAMEPICK_BUNDLE_TOOLS", "1") == "1":
    suffix = ".exe" if sys.platform == "win32" else ""
    for name in ("ffmpeg", "ffprobe"):
        path = root / "vendor" / "bin" / f"{name}{suffix}"
        if not path.is_file():
            raise SystemExit(f"Missing vendored tool: {path}")
        tool_binaries.append((str(path), "bin"))
    if not (root / "vendor" / "NOTICE.txt").is_file():
        raise SystemExit("Bundled builds require vendor/NOTICE.txt with provenance and source links.")

datas = [(str(root / "LICENSE"), "licenses"),
         (str(root / "THIRD_PARTY_NOTICES.md"), "licenses"),
         (str(root / "licenses"), "licenses/qt"),
         (str(root / "README.md"), ".")]
if (root / "assets" / "framepick.png").is_file():
    datas.append((str(root / "assets" / "framepick.png"), "assets"))
datas.append((str(root / "assets" / "fonts"), "assets/fonts"))
datas.append((str(root / "src" / "framepick" / "locales"), "framepick/locales"))
translations = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
for language in ("en", "zh_CN", "ja"):
    datas.append((str(translations / f"qtbase_{language}.qm"), "PySide6/translations"))
for package in ("PySide6-Essentials", "PySide6-Addons", "shiboken6", "pyinstaller"):
    metadata = distribution(package)
    for file in metadata.files or []:
        if "licenses/" in str(file).replace("\\", "/"):
            datas.append((str(metadata.locate_file(file)), f"licenses/{package}"))
python_license = Path(sys.base_prefix) / "LICENSE.txt"
if python_license.is_file():
    datas.append((str(python_license), "licenses/python"))
if tool_binaries:
    datas.append((str(root / "vendor" / "NOTICE.txt"), "licenses"))
    if (root / "vendor" / "licenses").is_dir():
        datas.append((str(root / "vendor" / "licenses"), "licenses/ffmpeg"))

a = Analysis(
    [str(root / "packaging" / "entrypoint.py")],
    pathex=[str(root / "src")],
    binaries=tool_binaries,
    datas=datas,
    hiddenimports=[],
    excludes=["PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
              "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtQml", "PySide6.QtQuick",
              "PySide6.QtQuickWidgets", "PySide6.QtDesigner", "PySide6.QtUiTools",
              "PySide6.Qt3DCore", "PySide6.QtCharts", "PySide6.QtDataVisualization",
              "tkinter", "pytest", "PIL", "ruff"],
    noarchive=False,
)
if sys.platform == "win32" and any(Path(entry[0]).name.lower() == "icuuc.dll" for entry in a.binaries):
    raise SystemExit("Foreign icuuc.dll was collected. Use scripts/build.py with its isolated build PATH.")
pyz = PYZ(a.pure)
icon = str(root / "assets" / ("framepick.ico" if sys.platform == "win32" else "framepick.icns"))
onefile = os.environ.get("FRAMEPICK_BUNDLE_MODE", "onefile") == "onefile"
options = dict(name="FramePick", debug=False, bootloader_ignore_signals=False,
               strip=False, upx=False, console=os.environ.get("FRAMEPICK_CONSOLE") == "1",
               icon=icon if Path(icon).exists() else None)
if onefile:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], **options)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **options)
    collection = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="FramePick")
if sys.platform == "darwin" and not onefile:
    app = BUNDLE(collection, name="FramePick.app", icon=icon if Path(icon).exists() else None,
                 bundle_identifier="io.framepick.desktop", info_plist={
                     "NSHighResolutionCapable": True,
                     "CFBundleShortVersionString": "0.3.0",
                 })
