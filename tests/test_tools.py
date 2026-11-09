from framepick import media
from framepick.media import Tools


def test_frozen_tools_prefer_bundled_paths_over_host_path(tmp_path, monkeypatch):
    bundled = tmp_path / "extract" / "bin"
    custom = tmp_path / "custom"
    bundled.mkdir(parents=True)
    custom.mkdir()
    suffix = ".exe" if media.sys.platform == "win32" else ""
    for directory in (bundled, custom):
        for name in ("ffmpeg", "ffprobe"):
            (directory / f"{name}{suffix}").touch()
    monkeypatch.setattr(media.sys, "frozen", True, raising=False)
    monkeypatch.setattr(media.sys, "_MEIPASS", str(bundled.parent), raising=False)
    monkeypatch.setattr(media.sys, "executable", str(tmp_path / "FramePick.exe"))
    monkeypatch.delenv("FRAMEPICK_FFMPEG", raising=False)
    monkeypatch.delenv("FRAMEPICK_FFPROBE", raising=False)
    monkeypatch.setattr(media.shutil, "which", lambda _name: str(tmp_path / "wrong-system-tool"))
    tools = Tools.discover(custom)
    assert tools.ffmpeg == (bundled / f"ffmpeg{suffix}").resolve()
    assert tools.ffmpeg_origin == tools.ffprobe_origin == "内置工具"
    external = Tools.discover(custom, prefer_bundled=False)
    assert external.ffmpeg == (custom / f"ffmpeg{suffix}").resolve()
    assert external.ffmpeg_origin == "自定义目录"
