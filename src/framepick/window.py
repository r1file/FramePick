"""Native desktop workflow: play, move a fixed window, collect, export."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QSettings, QSize, QStandardPaths, Qt, QTimer, QUrl
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDesktopServices,
    QIcon,
    QKeySequence,
    QPixmap,
    QShortcut,
)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from framepick import __version__
from framepick.controls import button
from framepick.i18n import (
    LANGUAGES,
    current_language,
    retranslate_tree,
    set_language,
    system_language,
    tr,
    translate_existing,
)
from framepick.media import MediaInfo, Tools
from framepick.model import Clip, ExportSettings, Project, fit_window, parse_timecode, timecode
from framepick.runtime import app_preferences, state_directory
from framepick.theme import STYLE
from framepick.workers import ExportWorker, ProbeWorker, SnapshotWorker, ThumbnailWorker


class MainWindow(QMainWindow):
    def __init__(self, *, preferences: QSettings | None = None, recovery_file: Path | None = None):
        super().__init__()
        self.preferences = preferences if preferences is not None else app_preferences()
        default_language = system_language() if preferences is None else current_language()
        set_language(self.preferences.value("language", default_language))
        self.setWindowTitle(tr("FramePick {p0} · 长视频精彩片段", p0=__version__))
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1330, screen.width() - 60), min(920, screen.height() - 60))
        self.setMinimumSize(900, 600)
        self.setAcceptDrops(True)
        self.setStyleSheet(STYLE)
        self._recovery_file = recovery_file
        self.media: MediaInfo | None = None
        self.project: Project | None = None
        self.project_path: Path | None = None
        self.selection_start = 0
        self.selection_duration = 5000
        self.follow_position = True
        self.previewing = False
        self._poster_pending = False
        self._poster_priming = False
        self._poster_restore_muted = False
        self.dirty = False
        self.export_worker: ExportWorker | None = None
        self.snapshot_worker: SnapshotWorker | None = None
        self.probe_worker: ProbeWorker | None = None
        self.clip_status: dict[str, str] = {}
        self.exported_paths: dict[str, str] = {}
        self._thumbnail_queue: dict[str, int] = {}
        self.thumbnail_worker: ThumbnailWorker | None = None
        self.last_log: str | None = None
        self._batch_ids: list[str] = []
        self._completed_ids: set[str] = set()
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(0.35)
        self.player.setAudioOutput(self.audio)
        self._build_ui()
        self._build_menu()
        self._build_shortcuts()
        for child in self.findChildren(QWidget):
            child.setAcceptDrops(True)
        QApplication.instance().installEventFilter(self)
        self.video.videoSink().videoFrameChanged.connect(self._first_frame)
        self.poster_timeout = QTimer(self)
        self.poster_timeout.setSingleShot(True)
        self.poster_timeout.timeout.connect(self._finish_poster)
        self.player.positionChanged.connect(self._position_changed)
        self.player.playbackStateChanged.connect(self._playback_state)
        self.player.errorOccurred.connect(self._playback_error)
        self.player.mediaStatusChanged.connect(self._media_status)
        self.recovery_timer = QTimer(self)
        self.recovery_timer.setSingleShot(True)
        self.recovery_timer.timeout.connect(self._save_recovery)
        self._sync_controls()
        self.statusBar().showMessage(tr("打开视频，移动 5 秒窗口，按 A 收集片段。"))

    def change_language(self, code):
        if code == current_language():
            return
        previous = current_language()
        set_language(code)
        self.preferences.setValue("language", code)
        retranslate_tree(self, previous)
        self.setWindowTitle(tr("FramePick {p0} · 长视频精彩片段", p0=__version__))
        self.clip_status = {
            key: translate_existing(value, previous) for key, value in self.clip_status.items()
        }
        if self.project:
            for clip in self.project.clips:
                self._update_item(clip.id)
        self._refresh_timelines()
        self._playback_state(self.player.playbackState())
        self.volume_control._sync()
        self.statusBar().showMessage(
            tr("打开视频，移动 5 秒窗口，按 A 收集片段。")
            if not self.media
            else tr("已打开。点击时间轴定位，拖动窗口选取，按 A 收集。")
        )
        self.language_picker.blockSignals(True)
        self.language_picker.setCurrentIndex(self.language_picker.findData(code))
        self.language_picker.blockSignals(False)
        for action in self.language_actions:
            action.setChecked(action.data() == code)

    def _build_ui(self):
        from framepick.ui import build_ui

        build_ui(self)

    def _build_menu(self):
        file_menu = self.menuBar().addMenu(tr("文件"))
        for text, shortcut, callback in (
            (tr("打开视频…"), "Ctrl+O", self.open_video),
            (tr("打开工程…"), "Ctrl+Shift+O", self.open_project),
            (tr("保存工程"), "Ctrl+S", self.save_project),
            (tr("工程另存为…"), "Ctrl+Shift+S", lambda: self.save_project(save_as=True)),
        ):
            action = QAction(text, self)
            action.setShortcut(shortcut)
            action.triggered.connect(callback)
            file_menu.addAction(action)
        file_menu.addAction(tr("恢复上次选段"), self.restore_session)
        tools_menu = self.menuBar().addMenu(tr("工具"))
        tools_menu.addAction(tr("FFmpeg 工具设置…"), self.configure_tools)
        tools_menu.addAction(tr("打开上次导出日志"), self.open_log)
        help_menu = self.menuBar().addMenu(tr("帮助"))
        help_menu.addAction(tr("快捷键"), self.show_shortcuts)
        help_menu.addAction(
            tr("关于 FramePick"),
            lambda: QMessageBox.information(
                self,
                "FramePick",
                tr("FramePick {p0}\n长视频片段收集与独立 GIF 导出\nMIT License", p0=__version__),
            ),
        )
        languages = self.menuBar().addMenu("Language / 语言 / 言語")
        self.language_actions = []
        for code, name in LANGUAGES.items():
            action = languages.addAction(name)
            action.setData(code)
            action.setCheckable(True)
            action.setChecked(code == current_language())
            action.triggered.connect(lambda _checked=False, code=code: self.change_language(code))
            self.language_actions.append(action)

    def _build_shortcuts(self):
        self._shortcuts = []
        mappings = {
            "Space": self.toggle_play,
            "A": self.add_clip,
            "S": self.take_snapshot,
            "L": self.toggle_preview,
            "M": self.toggle_mute,
            "Up": lambda: self.navigate_clip(-1),
            "Down": lambda: self.navigate_clip(1),
            "Left": lambda: self.seek_relative(-1000),
            "Right": lambda: self.seek_relative(1000),
            "Shift+Left": lambda: self.seek_relative(-10000),
            "Shift+Right": lambda: self.seek_relative(10000),
            "[": lambda: self.nudge_window(-100),
            "]": lambda: self.nudge_window(100),
            ",": lambda: self.step_frame(-1),
            ".": lambda: self.step_frame(1),
        }
        for key, callback in mappings.items():
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(lambda action=callback: self._shortcut(action))
            self._shortcuts.append(shortcut)
        QApplication.instance().focusChanged.connect(self._shortcut_focus_changed)
        self._shortcut_focus_changed(None, QApplication.focusWidget())

    def _shortcut_focus_changed(self, _old, current):
        editing = isinstance(current, (QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QSlider))
        for shortcut in self._shortcuts:
            shortcut.setEnabled(not editing)

    def _shortcut(self, action):
        focus = QApplication.focusWidget()
        if isinstance(focus, (QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QSlider)):
            return
        action()

    def _tools(self) -> Tools | None:
        try:
            custom = self.preferences.value("external_tools", False, type=bool)
            return Tools.discover(
                self.preferences.value("tools_dir", "") if custom else None,
                prefer_bundled=not custom,
            )
        except FileNotFoundError as exc:
            self._error(str(exc))
            return None

    def _error(self, message: str):
        QMessageBox.warning(self, "FramePick", message[:5000])

    def _sync_controls(self):
        loaded = self.media is not None
        busy = self.export_worker is not None
        for widget in (
            self.play_button,
            self.preview_button,
            self.add_button,
            self.snapshot_button,
            self.window_seconds,
            self.anchor,
        ):
            widget.setEnabled(loaded)
        self.snapshot_button.setEnabled(loaded and self.snapshot_worker is None)
        has_clips = bool(self.project and self.project.clips)
        self.export_button.setEnabled(has_clips and not busy)
        self.retry_button.setEnabled(has_clips and not busy)
        self.cancel_button.setEnabled(busy)
        self.update_button.setEnabled(has_clips and not busy)
        self.remove_button.setEnabled(has_clips and not busy)
        self.open_button.setEnabled(not busy and self.probe_worker is None)

    def _can_replace(self) -> bool:
        if self.export_worker or self.snapshot_worker or self.probe_worker:
            self._error(tr("请先完成或取消正在运行的任务。"))
            return False
        if not self.dirty:
            return True
        answer = QMessageBox.question(
            self,
            tr("保存当前选段？"),
            tr("当前工程尚未保存。是否先保存？"),
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        return self.save_project() if answer == QMessageBox.StandardButton.Save else True

    def open_video(self):
        if not self._can_replace():
            return
        filename, _ = QFileDialog.getOpenFileName(
            self,
            tr("打开本地视频"),
            self.preferences.value("last_directory", ""),
            tr("视频 (*.mp4 *.mkv *.mov *.webm *.avi *.m4v *.ts *.mts *.wmv);;所有文件 (*)"),
        )
        if filename:
            self.load_video(Path(filename))

    def load_video(
        self, path: Path, project: Project | None = None, project_path: Path | None = None
    ):
        if self.probe_worker or self.export_worker or self.snapshot_worker:
            return
        tools = self._tools()
        if not tools:
            return
        worker = ProbeWorker(path, tools, self)
        self.probe_worker = worker
        worker.ready.connect(lambda info: self._loaded(info, project, project_path))
        worker.failed.connect(self._error)
        worker.finished.connect(lambda: self._probe_finished(worker))
        self.statusBar().showMessage(tr("正在读取视频元数据…"))
        self._sync_controls()
        worker.start()

    def _probe_finished(self, worker):
        if self.probe_worker is worker:
            self.probe_worker = None
        worker.deleteLater()
        self._sync_controls()

    def _loaded(self, info: MediaInfo, project: Project | None, project_path: Path | None):
        if project and any(clip.end_ms > info.duration_ms + 100 for clip in project.clips):
            self._error(tr("工程中的片段超出当前视频时长；请选择原始视频。"))
            return
        self._finish_poster()
        self.player.stop()
        self.media = info
        self.project = project or Project(info.path)
        self.project.source = info.path
        self.project_path = project_path
        self.clip_status.clear()
        self.exported_paths.clear()
        self._thumbnail_queue.clear()
        if self.thumbnail_worker:
            self.thumbnail_worker.cancel_event.set()
        self.clip_list.clear()
        for clip in self.project.clips:
            self._append_item(clip)
        for widget, value in (
            (self.window_seconds, self.project.window_ms / 1000),
            (self.size_spin, self.project.settings.max_size),
            (self.fps_spin, self.project.settings.fps),
        ):
            widget.blockSignals(True)
            widget.setValue(value)
            widget.blockSignals(False)
        self.anchor.blockSignals(True)
        self.anchor.setCurrentIndex(self.anchor.findData(self.project.mode))
        self.anchor.blockSignals(False)
        self.selection_start, self.selection_duration = fit_window(
            0, self.project.window_ms, info.duration_ms, self.project.mode
        )
        self.follow_position = True
        self.previewing = False
        self.dirty = False
        self._poster_pending = True
        self.player.setSource(QUrl.fromLocalFile(str(info.path)))
        self.video_stack.setCurrentWidget(self.video)
        self.preferences.setValue("last_directory", str(info.path.parent))
        self.file_label.setText(
            f"{info.path.name}   ·   {info.width} × {info.height}   ·   "
            f"{timecode(info.duration_ms, precision=False)}"
        )
        self.file_label.setToolTip(str(info.path))
        self.statusBar().showMessage(tr("已打开。点击时间轴定位，拖动窗口选取，按 A 收集。"))
        self._refresh_timelines()
        self._sync_controls()

    def _media_status(self, status):
        if (
            status == QMediaPlayer.MediaStatus.LoadedMedia
            and self._poster_pending
            and not self._poster_priming
        ):
            self._poster_priming = True
            self._poster_restore_muted = self.audio.isMuted()
            self.audio.setMuted(True)
            self.poster_timeout.start(8000)
            self.player.play()
        if status == QMediaPlayer.MediaStatus.EndOfMedia and self.previewing:
            self.player.setPosition(self.selection_start)
            self.player.play()

    def _playback_error(self, _error, message):
        if message:
            self._finish_poster()
            self.statusBar().showMessage(tr("播放失败：{p0}", p0=message))
            self.previewing = False
            self.preview_button.setText(tr("循环预览"))

    def _playback_state(self, state):
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.play_button.set_symbol("pause" if playing else "play")
        self.play_button.setAccessibleName(tr("暂停") if playing else tr("播放"))
        self.play_button.setToolTip(tr("暂停（Space）") if playing else tr("播放（Space）"))

    def _first_frame(self, frame):
        if self._poster_pending and self._poster_priming and frame.isValid():
            self._finish_poster()

    def _start_thumbnail(self):
        if self.thumbnail_worker or not self.media or not self._thumbnail_queue:
            return
        tools = self._tools()
        if not tools:
            self._thumbnail_queue.clear()
            return
        clip_id = next(iter(self._thumbnail_queue))
        start = self._thumbnail_queue.pop(clip_id)
        worker = ThumbnailWorker(tools, self.media.path, clip_id, start, self)
        self.thumbnail_worker = worker
        worker.ready.connect(
            lambda cid, stamp, image: self._thumbnail_ready(worker, cid, stamp, image)
        )
        worker.finished.connect(lambda: self._thumbnail_finished(worker))
        worker.start()

    def _thumbnail_ready(self, worker, clip_id, start, image):
        if not self.project or worker.source != self.project.source:
            return
        clip = next((clip for clip in self.project.clips if clip.id == clip_id), None)
        item = self._item_for(clip_id)
        if clip and item and clip.start_ms == start:
            item.setIcon(QIcon(QPixmap.fromImage(image)))

    def _thumbnail_finished(self, worker):
        if self.thumbnail_worker is worker:
            self.thumbnail_worker = None
        worker.deleteLater()
        self._start_thumbnail()

    def _finish_poster(self):
        # Pause can synchronously re-emit LoadedMedia; clear the flag first.
        self._poster_pending = False
        if self._poster_priming:
            self._poster_priming = False
            self.player.pause()
            self.player.setPosition(0)
            self.audio.setMuted(self._poster_restore_muted)
        if hasattr(self, "poster_timeout"):
            self.poster_timeout.stop()

    def _position_changed(self, position):
        if not self.media:
            return
        if self.previewing and position >= self.selection_start + self.selection_duration:
            self.player.setPosition(self.selection_start)
            return
        if self.follow_position and not self.previewing:
            self.selection_start, self.selection_duration = fit_window(
                position,
                round(self.window_seconds.value() * 1000),
                self.media.duration_ms,
                self.anchor.currentData(),
            )
        self.position_label.setText(
            f"{timecode(position)} / {timecode(self.media.duration_ms, precision=False)}"
        )
        self._refresh_timelines()

    def _refresh_timelines(self):
        total = self.media.duration_ms if self.media else 0
        clips = self.project.clips if self.project else []
        for timeline in (self.overview, self.detail):
            timeline.set_state(
                total, self.player.position(), self.selection_start, self.selection_duration, clips
            )
        self.selection_label.setText(
            f"{timecode(self.selection_start)} → "
            f"{timecode(self.selection_start + self.selection_duration)}"
        )
        self.count_label.setText(tr("{p0} 段", p0=len(clips)))
        self.empty_clip_hint.setVisible(not clips)

    def _stop_preview(self):
        self.previewing = False
        self.preview_button.setText(tr("循环预览"))

    def toggle_play(self):
        if not self.media:
            return
        self._finish_poster()
        self._stop_preview()
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def toggle_mute(self):
        self.volume_control.toggle()

    def seek(self, position: int):
        if not self.media:
            return
        self._finish_poster()
        self._stop_preview()
        self.follow_position = True
        position = max(0, min(position, self.media.duration_ms - 1))
        self.selection_start, self.selection_duration = fit_window(
            position,
            round(self.window_seconds.value() * 1000),
            self.media.duration_ms,
            self.anchor.currentData(),
        )
        self.player.setPosition(position)
        self._refresh_timelines()

    def seek_relative(self, offset: int):
        self.seek(self.player.position() + offset)

    def step_frame(self, direction: int):
        if self.media:
            self.player.pause()
            self.seek_relative(round(1000 / self.media.fps) * direction)

    def jump_to_time(self):
        try:
            self.seek(parse_timecode(self.jump_input.text()))
            self.jump_input.clearFocus()
        except ValueError as exc:
            self.statusBar().showMessage(str(exc), 5000)

    def move_window(self, start: int):
        if not self.media:
            return
        self._stop_preview()
        self.follow_position = False
        self.player.pause()
        self.selection_start = max(0, min(start, self.media.duration_ms - self.selection_duration))
        self.player.setPosition(self.selection_start)
        self._refresh_timelines()

    def nudge_window(self, offset: int):
        self.move_window(self.selection_start + offset)

    def toggle_preview(self):
        if not self.media:
            return
        if self.previewing:
            self._stop_preview()
            self.player.pause()
        else:
            self.follow_position = False
            self.previewing = True
            self.preview_button.setText(tr("停止预览"))
            self.player.setPosition(self.selection_start)
            self.player.play()

    def _window_options_changed(self):
        if self.media:
            self._stop_preview()
            self.selection_start, self.selection_duration = fit_window(
                self.player.position(),
                round(self.window_seconds.value() * 1000),
                self.media.duration_ms,
                self.anchor.currentData(),
            )
            self.follow_position = True
            if self.project:
                self.project.window_ms = round(self.window_seconds.value() * 1000)
                self.project.mode = self.anchor.currentData()
                self._mark_dirty()
            self._refresh_timelines()

    def _settings_changed(self):
        if self.project:
            self.project.settings = ExportSettings(self.size_spin.value(), self.fps_spin.value())
            self._mark_dirty()

    def _append_item(self, clip: Clip, icon: QIcon | None = None):
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, clip.id)
        item.setSizeHint(QSize(250, 82))
        if icon:
            item.setIcon(icon)
        if icon is None or icon.isNull():
            self._thumbnail_queue[clip.id] = clip.start_ms
            QTimer.singleShot(0, self._start_thumbnail)
        self.clip_list.addItem(item)
        self._update_item(clip.id)

    def _item_for(self, clip_id: str) -> QListWidgetItem | None:
        for index in range(self.clip_list.count()):
            item = self.clip_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == clip_id:
                return item
        return None

    def _update_item(self, clip_id: str):
        if not self.project:
            return
        item = self._item_for(clip_id)
        for index, clip in enumerate(self.project.clips):
            if clip.id == clip_id and item:
                state = self.clip_status.get(clip.id, tr("待导出"))
                item.setText(
                    tr(
                        "{p0:02d}   {p1}\n{p2:g} 秒   ·   {p3}",
                        p0=index + 1,
                        p1=timecode(clip.start_ms),
                        p2=clip.duration_ms / 1000,
                        p3=state.splitlines()[0][:38],
                    )
                )
                item.setToolTip(f"{timecode(clip.start_ms)} → {timecode(clip.end_ms)}\n{state}")
                break

    def add_clip(self):
        if not self.project or self.selection_duration < 100:
            return
        if any(
            c.start_ms == self.selection_start and c.duration_ms == self.selection_duration
            for c in self.project.clips
        ):
            self.statusBar().showMessage(tr("这一范围已经在列表中。"), 3000)
            return
        clip = Clip(self.selection_start, self.selection_duration)
        self.project.clips.append(clip)
        self._append_item(clip)
        self.clip_list.scrollToBottom()
        self._mark_dirty()
        self._refresh_timelines()
        self._sync_controls()
        self.statusBar().showMessage(
            tr("已收集第 {p0} 段，继续选择其他位置。", p0=len(self.project.clips)), 4000
        )

    def _activate_clip(self, item: QListWidgetItem):
        if not self.project:
            return
        clip_id = item.data(Qt.ItemDataRole.UserRole)
        clip = next(c for c in self.project.clips if c.id == clip_id)
        self._stop_preview()
        self.player.pause()
        self.follow_position = False
        self.selection_start, self.selection_duration = clip.start_ms, clip.duration_ms
        self.window_seconds.blockSignals(True)
        self.window_seconds.setValue(clip.duration_ms / 1000)
        self.window_seconds.blockSignals(False)
        self.player.setPosition(clip.start_ms)
        self._refresh_timelines()

    def navigate_clip(self, direction: int):
        if not self.clip_list.count():
            return
        row = self.clip_list.currentRow()
        row = 0 if row < 0 else max(0, min(self.clip_list.count() - 1, row + direction))
        self.clip_list.setCurrentRow(row)
        item = self.clip_list.item(row)
        self.clip_list.scrollToItem(item)
        self._activate_clip(item)

    def update_clip(self):
        if not self.project or self.export_worker:
            return
        selected = self.clip_list.selectedItems()
        if len(selected) != 1:
            self.statusBar().showMessage(tr("请选择一个片段，再用当前窗口更新它。"), 4000)
            return
        item = selected[0]
        clip_id = item.data(Qt.ItemDataRole.UserRole)
        for index, clip in enumerate(self.project.clips):
            if clip.id == clip_id:
                self.project.clips[index] = Clip(
                    self.selection_start, self.selection_duration, clip.id
                )
                break
        self.clip_status.pop(clip_id, None)
        self.exported_paths.pop(clip_id, None)
        item.setIcon(QIcon())
        self._thumbnail_queue[clip_id] = self.selection_start
        self._start_thumbnail()
        self._update_item(clip_id)
        self._mark_dirty()
        self._refresh_timelines()

    def remove_clips(self):
        if not self.project or self.export_worker:
            return
        ids = {item.data(Qt.ItemDataRole.UserRole) for item in self.clip_list.selectedItems()}
        for clip_id in ids:
            self._thumbnail_queue.pop(clip_id, None)
        self.project.clips = [clip for clip in self.project.clips if clip.id not in ids]
        for index in range(self.clip_list.count() - 1, -1, -1):
            if self.clip_list.item(index).data(Qt.ItemDataRole.UserRole) in ids:
                self.clip_list.takeItem(index)
        for clip in self.project.clips:
            self._update_item(clip.id)
        self._mark_dirty()
        self._refresh_timelines()
        self._sync_controls()

    def output_directory(self) -> Path:
        text = self.output_input.text().strip()
        if text:
            return Path(text).expanduser().resolve()
        if self.media:
            return self.media.path.parent / "FramePick"
        return Path.home() / "Pictures" / "FramePick"

    def choose_output(self):
        directory = QFileDialog.getExistingDirectory(
            self, tr("选择输出文件夹"), str(self.output_directory())
        )
        if directory:
            self.output_input.setText(directory)
            self.preferences.setValue("output_dir", directory)

    def reveal_output(self):
        path = self.output_directory()
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def take_snapshot(self):
        if not self.media or self.snapshot_worker:
            return
        tools = self._tools()
        if not tools:
            return
        # Capture the timestamp at the moment of the shortcut, even during playback.
        position = min(self.player.position(), max(0, self.media.duration_ms - 100))
        worker = SnapshotWorker(tools, self.media.path, position, self.output_directory(), self)
        self.snapshot_worker = worker
        worker.succeeded.connect(
            lambda path: self.statusBar().showMessage(tr("截图已保存：{p0}", p0=path), 10000)
        )
        worker.failed.connect(self._error)
        worker.finished.connect(lambda: self._snapshot_finished(worker))
        self._sync_controls()
        self.statusBar().showMessage(tr("正在保存原分辨率 PNG 截图…"))
        worker.start()

    def _snapshot_finished(self, worker):
        if self.snapshot_worker is worker:
            self.snapshot_worker = None
        worker.deleteLater()
        self._sync_controls()

    def export_all(self):
        if self.project:
            self._export(self.project.clips)

    def export_selected(self):
        if not self.project:
            return
        ids = {item.data(Qt.ItemDataRole.UserRole) for item in self.clip_list.selectedItems()}
        if not ids:
            ids = {
                cid
                for cid, status in self.clip_status.items()
                if status.startswith((tr("失败"), tr("已取消")))
            }
        clips = [clip for clip in self.project.clips if clip.id in ids]
        if clips:
            self._export(clips)
        else:
            self.statusBar().showMessage(tr("请先选中片段，或使用“全部导出”。"), 4000)

    def _export(self, clips: list[Clip]):
        if not self.media or not clips or self.export_worker:
            return
        tools = self._tools()
        if not tools:
            return
        self._save_recovery()
        worker = ExportWorker(
            tools,
            self.media.path,
            clips,
            ExportSettings(self.size_spin.value(), self.fps_spin.value()),
            self.output_directory(),
            self,
        )
        self.export_worker = worker
        self._batch_ids = [clip.id for clip in clips]
        self._completed_ids.clear()
        for clip in clips:
            self.clip_status[clip.id] = tr("等待导出")
            self._update_item(clip.id)
        worker.progress.connect(self._export_progress)
        worker.succeeded.connect(self._export_succeeded)
        worker.failed.connect(self._export_failed)
        worker.summary.connect(self._export_summary)
        worker.finished.connect(lambda: self._export_finished(worker))
        self.progress.setValue(0)
        self._sync_controls()
        worker.start()

    def _export_progress(self, clip_id: str, stage: str, value: float):
        self.clip_status[clip_id] = f"{stage} {value:.0%}"
        self._update_item(clip_id)
        number = self._batch_ids.index(clip_id) + 1
        self.progress_label.setText(
            tr(
                "第 {p0}/{p1} 段 · {p2} {p3:.0%}",
                p0=number,
                p1=len(self._batch_ids),
                p2=stage,
                p3=value,
            )
        )
        self.progress.setValue(
            round((len(self._completed_ids) + value) / len(self._batch_ids) * 1000)
        )

    def _export_succeeded(self, clip_id: str, path: str):
        self.clip_status[clip_id] = tr("已导出")
        self.exported_paths[clip_id] = path
        self._completed_ids.add(clip_id)
        self._update_item(clip_id)

    def _export_failed(self, clip_id: str, message: str):
        if not clip_id:
            self._error(message)
            return
        self.clip_status[clip_id] = (
            tr("已取消") if message.startswith(tr("已取消")) else tr("失败")
        ) + f"\n{message}"
        self._completed_ids.add(clip_id)
        self._update_item(clip_id)

    def _export_summary(self, succeeded: int, failed: int, cancelled: bool, log_path: str):
        self.last_log = log_path
        if cancelled:
            for clip_id in self._batch_ids:
                if clip_id not in self._completed_ids:
                    self.clip_status[clip_id] = tr("已取消，尚未开始")
                    self._update_item(clip_id)
        text = tr(
            "{p0} · 成功 {p1} 段 · 失败 {p2} 段",
            p0=tr("已取消") if cancelled else tr("导出完成"),
            p1=succeeded,
            p2=failed,
        )
        self.progress_label.setText(text)
        self.progress.setValue(0 if cancelled else 1000)
        self.statusBar().showMessage(text + tr("。日志保存在输出目录。"), 15000)

    def _export_finished(self, worker):
        if self.export_worker is worker:
            self.export_worker = None
        worker.deleteLater()
        self._sync_controls()

    def cancel_export(self):
        if self.export_worker:
            self.export_worker.cancel_event.set()
            self.cancel_button.setEnabled(False)
            self.progress_label.setText(tr("正在取消；已完成的 GIF 会保留。"))

    def _open_clip_output(self):
        item = self.clip_list.currentItem()
        if item:
            path = self.exported_paths.get(item.data(Qt.ItemDataRole.UserRole))
            if path:
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def open_log(self):
        if self.last_log and Path(self.last_log).is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.last_log))
        else:
            self.statusBar().showMessage(tr("本次还没有导出日志。"), 4000)

    def _mark_dirty(self):
        self.dirty = True
        self.recovery_timer.start(700)

    @staticmethod
    def recovery_path() -> Path:
        return state_directory() / "recovery.framepick.json"

    def _save_recovery(self):
        if self.project:
            try:
                self.project.save(self._recovery_file or self.recovery_path())
            except OSError as exc:
                self.statusBar().showMessage(tr("自动恢复记录保存失败：{p0}", p0=exc), 5000)

    def save_project(self, _checked=False, *, save_as=False) -> bool:
        if not self.project:
            return False
        destination = None if save_as else self.project_path
        if destination is None:
            initial = self.project.source.with_suffix(".framepick.json")
            filename, _ = QFileDialog.getSaveFileName(
                self, tr("保存选段工程"), str(initial), tr("FramePick 工程 (*.framepick.json)")
            )
            if not filename:
                return False
            destination = Path(filename)
        try:
            self.project.save(destination)
            self.project_path = destination
            self.dirty = False
            self.statusBar().showMessage(tr("工程已保存：{p0}", p0=destination), 6000)
            return True
        except (OSError, ValueError) as exc:
            self._error(str(exc))
            return False

    def open_project(self):
        if not self._can_replace():
            return
        filename, _ = QFileDialog.getOpenFileName(
            self, tr("打开选段工程"), "", tr("FramePick 工程 (*.framepick.json);;JSON (*.json)")
        )
        if filename:
            self.load_project(Path(filename))

    def load_project(self, path: Path, *, as_recovery: bool = False):
        try:
            project = Project.load(path)
            if not project.source.is_file():
                filename, _ = QFileDialog.getOpenFileName(
                    self, tr("原视频已移动，请重新定位"), "", tr("视频 (*)")
                )
                if not filename:
                    return
                project.source = Path(filename)
            self.load_video(project.source, project, None if as_recovery else path)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self._error(tr("无法打开工程：{p0}", p0=exc))

    def restore_session(self):
        if self._can_replace():
            path = self._recovery_file or self.recovery_path()
            if not path.is_file() and not self._recovery_file:
                path = (
                    Path(
                        QStandardPaths.writableLocation(
                            QStandardPaths.StandardLocation.AppDataLocation
                        )
                    )
                    / "recovery.framepick.json"
                )
            if path.is_file():
                self.load_project(path, as_recovery=True)
            else:
                self.statusBar().showMessage(tr("没有可恢复的选段。"), 4000)

    def configure_tools(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("FFmpeg 工具设置"))
        dialog.resize(720, 260)
        layout = QVBoxLayout(dialog)
        try:
            custom = self.preferences.value("external_tools", False, type=bool)
            tools = Tools.discover(
                self.preferences.value("tools_dir", "") if custom else None,
                prefer_bundled=not custom,
            )
            current = tr(
                "当前来源：{p0}\nFFmpeg：{p1}\nffprobe：{p2}",
                p0=tools.ffmpeg_origin,
                p1=tools.ffmpeg,
                p2=tools.ffprobe,
            )
        except FileNotFoundError:
            current = tr("尚未找到工具。开发版可选择外部工具目录。")
        label = QLabel(current + tr("\n\n便携版默认使用包内固定版本，无需安装或配置 PATH。"))
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(label)
        external = QCheckBox(tr("使用外部 FFmpeg（高级）"))
        external.setChecked(self.preferences.value("external_tools", False, type=bool))
        layout.addWidget(external)
        row = QHBoxLayout()
        field = QLineEdit(self.preferences.value("tools_dir", ""))
        field.setEnabled(external.isChecked())
        external.toggled.connect(field.setEnabled)
        row.addWidget(field)

        def browse():
            directory = QFileDialog.getExistingDirectory(
                dialog, tr("选择 FFmpeg 目录"), field.text()
            )
            if directory:
                field.setText(directory)

        row.addWidget(button(tr("浏览…"), browse))
        layout.addLayout(row)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        def accept():
            try:
                Tools.discover(
                    field.text() if external.isChecked() else None,
                    prefer_bundled=not external.isChecked(),
                )
            except FileNotFoundError as exc:
                self._error(str(exc))
                return
            self.preferences.setValue("tools_dir", field.text())
            self.preferences.setValue("external_tools", external.isChecked())
            dialog.accept()

        buttons.accepted.connect(accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def show_shortcuts(self):
        QMessageBox.information(
            self,
            tr("快捷键"),
            (
                tr(
                    "Space    播放 / 暂停\nA    收集当前窗口\nS    保存当前位置截图\nL    循环预览当前窗口\nM    静音 / 取消静音\n↑ / ↓    上一个 / 下一个已收集片段\n← / →    跳转 1 秒\nShift + ← / →    跳转 10 秒\n[ / ]    整体微移窗口 0.1 秒\n, / .    按标称帧率微调位置\nCtrl+O    打开视频\nCtrl+S    保存工程\nCtrl+Shift+O    打开工程\n\n点击时间轴定位，拖动青色窗口整体平移，局部时间轴滚轮缩放。"
                )
            ),
        )

    def eventFilter(self, watched, event):
        if isinstance(watched, QWidget) and (watched is self or self.isAncestorOf(watched)):
            if event.type() in (QEvent.Type.DragEnter, QEvent.Type.DragMove, QEvent.Type.Drop):
                urls = [url for url in event.mimeData().urls() if url.isLocalFile()]
                if urls:
                    event.acceptProposedAction()
                    if event.type() == QEvent.Type.Drop:
                        path = Path(urls[0].toLocalFile())
                        QTimer.singleShot(0, lambda: self._open_dropped(path))
                    return True
        return super().eventFilter(watched, event)

    def _open_dropped(self, path: Path):
        if self._can_replace():
            if path.name.endswith(".framepick.json"):
                self.load_project(path)
            else:
                self.load_video(path)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = [url for url in event.mimeData().urls() if url.isLocalFile()]
        if not urls:
            return
        self._open_dropped(Path(urls[0].toLocalFile()))
        event.acceptProposedAction()

    def closeEvent(self, event: QCloseEvent):
        workers = [worker for worker in (self.export_worker, self.snapshot_worker) if worker]
        if workers:
            answer = QMessageBox.question(
                self,
                tr("退出 FramePick？"),
                tr("退出会取消尚未完成的导出和截图。"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            for worker in workers:
                worker.cancel_event.set()
            for worker in workers:
                if not worker.wait(6000):
                    event.ignore()
                    self.statusBar().showMessage(tr("正在结束后台任务，请稍后关闭。"))
                    return
        if self.probe_worker and self.probe_worker.isRunning():
            event.ignore()
            self.statusBar().showMessage(tr("正在读取元数据，请稍后关闭。"))
            return
        self._thumbnail_queue.clear()
        if self.thumbnail_worker:
            self.thumbnail_worker.cancel_event.set()
            if not self.thumbnail_worker.wait(6000):
                event.ignore()
                return
        self._save_recovery()
        self._finish_poster()
        self.volume_control.popup.hide()
        QApplication.instance().removeEventFilter(self)
        self.player.stop()
        self.player.setSource(QUrl())
        self.preferences.sync()
        event.accept()
