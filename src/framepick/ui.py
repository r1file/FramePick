"""Responsive QWidget layout. Each pane can scroll instead of clipping controls."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from framepick.controls import (
    ClipDelegate,
    ComboBox,
    DoubleSpinBox,
    SpinBox,
    VolumeControl,
    button,
    time_font,
)
from framepick.i18n import LANGUAGES, current_language, tr
from framepick.timeline import Timeline


def scroll_pane(content: QWidget, name: str, minimum_width: int) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setObjectName(name)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setMinimumWidth(minimum_width)
    scroll.setWidget(content)
    return scroll


def build_ui(self):
    root = QWidget()
    root.setObjectName("workspace")
    layout = QVBoxLayout(root)
    layout.setContentsMargins(18, 12, 18, 8)
    layout.setSpacing(12)
    header = QHBoxLayout()
    header.setSpacing(12)
    brand = QLabel("FRAMEPICK")
    brand.setObjectName("brand")
    header.addWidget(brand)
    subtitle = QLabel(tr("让精彩停留几秒"))
    subtitle.setObjectName("subtitle")
    subtitle.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    header.addWidget(subtitle, 1)
    self.open_button = button(tr("打开视频"), self.open_video, keycap="Ctrl+O", symbol="folder")
    header.addWidget(self.open_button)
    header.addWidget(button(tr("保存工程"), self.save_project, keycap="Ctrl+S"))
    self.language_picker = ComboBox()
    for code, name in LANGUAGES.items():
        self.language_picker.addItem(name, code)
    self.language_picker.setCurrentIndex(self.language_picker.findData(current_language()))
    self.language_picker.setMinimumWidth(120)
    self.language_picker.setToolTip("Language / 语言 / 言語")
    self.language_picker.currentIndexChanged.connect(
        lambda: self.change_language(self.language_picker.currentData())
    )
    header.addWidget(self.language_picker)
    layout.addLayout(header)

    self.splitter = QSplitter(Qt.Orientation.Horizontal)
    self.splitter.setObjectName("workspaceSplitter")
    self.splitter.setHandleWidth(16)
    self.splitter.setChildrenCollapsible(False)
    left = QWidget()
    left_layout = QVBoxLayout(left)
    left_layout.setContentsMargins(0, 0, 4, 4)
    left_layout.setSpacing(9)
    self.file_label = QLabel(tr("打开视频或将文件拖到这里"))
    self.file_label.setObjectName("muted")
    self.file_label.setWordWrap(True)
    self.file_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    left_layout.addWidget(self.file_label)
    self.video = QVideoWidget()
    self.video.setObjectName("videoPreview")
    self.video.setMinimumSize(280, 170)
    self.video.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
    self.video.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
    self.video.setAcceptDrops(True)
    self.video.setToolTip(tr("拖入视频即可打开"))
    self.player.setVideoOutput(self.video)
    self.video_stack = QStackedWidget()
    self.video_stack.setMinimumHeight(210)
    welcome = QFrame()
    welcome.setObjectName("panel")
    welcome_layout = QVBoxLayout(welcome)
    welcome_layout.setContentsMargins(24, 24, 24, 24)
    welcome_layout.addStretch()
    for key in (
        "欢迎使用 FramePick",
        "打开或拖入视频即可开始，无需导入整个文件。",
        "1. 移动时间窗口，按 A 收集精彩片段。",
        "2. 按 L 预览；按 S 保存截图。",
        "3. 一次导出多个独立 GIF，原视频保持不变。",
    ):
        label = QLabel(tr(key))
        label.setWordWrap(True)
        label.setObjectName("section" if key == "欢迎使用 FramePick" else "muted")
        welcome_layout.addWidget(label)
    welcome_layout.addWidget(button(tr("打开视频"), self.open_video, primary=True, symbol="folder"))
    welcome_layout.addStretch()
    self.video_stack.addWidget(welcome)
    self.video_stack.addWidget(self.video)
    left_layout.addWidget(self.video_stack, 1)

    playback = QHBoxLayout()
    playback.setSpacing(8)
    self.play_button = button(
        "", self.toggle_play, symbol="play", tooltip=tr("播放 / 暂停（Space）")
    )
    self.play_button.setAccessibleName(tr("播放"))
    self.play_button.setFixedWidth(38)
    playback.addWidget(self.play_button)
    self.position_label = QLabel("00:00:00.000 / 00:00:00")
    self.position_label.setObjectName("timecode")
    self.position_label.setFont(time_font(10))
    playback.addWidget(self.position_label)
    playback.addStretch(1)
    self.jump_input = QLineEdit()
    self.jump_input.setPlaceholderText(tr("跳转时间码"))
    self.jump_input.setToolTip(tr("输入秒数或 HH:MM:SS，按 Enter 跳转"))
    self.jump_input.setFont(time_font(9))
    self.jump_input.setFixedWidth(116)
    self.jump_input.returnPressed.connect(self.jump_to_time)
    self.speed = ComboBox()
    # Include stylesheet padding and the separate arrow area at every DPI.
    self.speed.setMinimumContentsLength(4)
    self.speed.setFixedWidth(max(92, self.speed.fontMetrics().horizontalAdvance("0.5×") + 52))
    self.speed.setToolTip(tr("播放速度"))
    for rate in (0.5, 1.0, 1.5, 2.0, 4.0):
        self.speed.addItem(f"{rate:g}×", rate)
    self.speed.setCurrentIndex(1)
    self.speed.currentIndexChanged.connect(
        lambda: self.player.setPlaybackRate(self.speed.currentData())
    )
    playback.addWidget(self.speed)
    self.volume_control = VolumeControl(self.audio)
    self.mute_button = self.volume_control.mute_button
    playback.addWidget(self.volume_control)
    left_layout.addLayout(playback)

    self.overview = Timeline(overview=True)
    self.detail = Timeline()
    for timeline in (self.overview, self.detail):
        timeline.seekRequested.connect(self.seek)
        timeline.windowMoved.connect(self.move_window)
    left_layout.addWidget(self.overview)
    timeline_label = QLabel(tr("局部精调 · 滚轮缩放 · 拖动青色窗口平移"))
    timeline_label.setObjectName("muted")
    timeline_label.setWordWrap(True)
    timeline_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    timeline_heading = QHBoxLayout()
    timeline_heading.addWidget(timeline_label, 1)
    timeline_heading.addWidget(self.jump_input)
    left_layout.addLayout(timeline_heading)
    left_layout.addWidget(self.detail)

    self.selection_panel = QFrame()
    self.selection_panel.setObjectName("panel")
    selection_layout = QVBoxLayout(self.selection_panel)
    selection_layout.setContentsMargins(12, 12, 12, 12)
    selection_layout.setSpacing(9)
    options = QHBoxLayout()
    options.setSpacing(8)
    options.addWidget(QLabel(tr("窗口时长")))
    self.window_seconds = DoubleSpinBox()
    self.window_seconds.setRange(0.1, 3600)
    self.window_seconds.setDecimals(2)
    self.window_seconds.setSingleStep(0.5)
    self.window_seconds.setValue(5)
    self.window_seconds.setSuffix(tr(" 秒"))
    self.window_seconds.lineEdit().setTextMargins(8, 0, 4, 0)
    self.window_seconds.setFixedWidth(125)
    self.window_seconds.setToolTip(tr("可输入自定义时长；上下键每次调整 0.5 秒"))
    self.window_seconds.valueChanged.connect(self._window_options_changed)
    options.addWidget(self.window_seconds)
    self.anchor = ComboBox()
    for label, mode in (
        (tr("从当前位置向后"), "after"),
        (tr("刚看过的几秒"), "before"),
        (tr("以当前位置居中"), "center"),
    ):
        self.anchor.addItem(label, mode)
    self.anchor.currentIndexChanged.connect(self._window_options_changed)
    options.addWidget(self.anchor)
    options.addStretch()
    selection_layout.addLayout(options)
    self.selection_label = QLabel("00:00:00.000 → 00:00:05.000")
    self.selection_label.setObjectName("timecode")
    self.selection_label.setFont(time_font(11))
    selection_layout.addWidget(self.selection_label)
    actions = QHBoxLayout()
    actions.setSpacing(7)
    self.preview_button = button(tr("循环预览"), self.toggle_preview, keycap="L", symbol="loop")
    actions.addWidget(self.preview_button)
    self.snapshot_button = button(tr("截图"), self.take_snapshot, keycap="S", symbol="camera")
    actions.addWidget(self.snapshot_button)
    actions.addStretch()
    self.add_button = button(tr("加入片段"), self.add_clip, keycap="A", symbol="plus", primary=True)
    actions.addWidget(self.add_button)
    selection_layout.addLayout(actions)
    nudge = QHBoxLayout()
    nudge.setSpacing(7)
    nudge.addWidget(
        button(
            "−0.1s",
            lambda: self.nudge_window(-100),
            keycap="[",
            tooltip=tr("窗口向前移动 0.1 秒（[）"),
        )
    )
    nudge.addWidget(
        button(
            "+0.1s",
            lambda: self.nudge_window(100),
            keycap="]",
            tooltip=tr("窗口向后移动 0.1 秒（]）"),
        )
    )
    nudge.addStretch()
    note = QLabel(tr("金色标记：已收集片段"))
    note.setObjectName("muted")
    nudge.addWidget(note)
    selection_layout.addLayout(nudge)
    left_layout.addWidget(self.selection_panel)

    right = QWidget()
    right_layout = QVBoxLayout(right)
    right_layout.setContentsMargins(4, 0, 0, 4)
    right_layout.setSpacing(10)
    list_heading = QHBoxLayout()
    heading = QLabel(tr("已收集片段"))
    heading.setObjectName("section")
    list_heading.addWidget(heading)
    list_heading.addStretch()
    self.count_label = QLabel(tr("0 段"))
    self.count_label.setObjectName("muted")
    list_heading.addWidget(self.count_label)
    right_layout.addLayout(list_heading)
    self.empty_clip_hint = QLabel(tr("还没有片段。在视频中选好范围，按 A 添加。"))
    self.empty_clip_hint.setObjectName("muted")
    self.empty_clip_hint.setWordWrap(True)
    right_layout.addWidget(self.empty_clip_hint)
    self.clip_list = QListWidget()
    self.clip_list.setObjectName("clipList")
    self.clip_list.setMinimumHeight(100)
    self.clip_list.setItemDelegate(ClipDelegate(self.clip_list))
    self.clip_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    self.clip_list.itemClicked.connect(self._activate_clip)
    self.clip_list.itemDoubleClicked.connect(lambda _item: self.toggle_preview())
    self.clip_list.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
    reveal = QAction(tr("打开已导出的 GIF"), self.clip_list)
    reveal.triggered.connect(self._open_clip_output)
    self.clip_list.addAction(reveal)
    right_layout.addWidget(self.clip_list, 1)
    list_actions = QHBoxLayout()
    self.update_button = button(tr("更新选中"), self.update_clip)
    self.remove_button = button(tr("移除"), self.remove_clips)
    list_actions.addWidget(self.update_button)
    list_actions.addWidget(self.remove_button)
    right_layout.addLayout(list_actions)
    hint = QLabel(tr("↑ / ↓ 切换片段 · 双击循环预览\nCtrl / Shift 多选，每段导出独立 GIF"))
    hint.setObjectName("muted")
    hint.setWordWrap(True)
    right_layout.addWidget(hint)

    self.output_panel = QFrame()
    self.output_panel.setObjectName("panel")
    output_layout = QVBoxLayout(self.output_panel)
    output_layout.setContentsMargins(12, 12, 12, 12)
    output_layout.setSpacing(9)
    title = QLabel(tr("导出设置"))
    title.setObjectName("section")
    output_layout.addWidget(title)
    form = QFormLayout()
    form.setHorizontalSpacing(12)
    form.setVerticalSpacing(9)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    self.size_spin = SpinBox()
    self.size_spin.setRange(64, 1920)
    self.size_spin.setSingleStep(64)
    self.size_spin.setValue(640)
    self.size_spin.setSuffix(" px")
    self.fps_spin = SpinBox()
    self.fps_spin.setRange(1, 50)
    self.fps_spin.setValue(15)
    self.fps_spin.setSuffix(" FPS")
    for spin in (self.size_spin, self.fps_spin):
        spin.lineEdit().setTextMargins(8, 0, 4, 0)
        spin.setMinimumWidth(75)
    form.addRow(tr("GIF 最长边"), self.size_spin)
    form.addRow(tr("帧率"), self.fps_spin)
    self.size_spin.valueChanged.connect(self._settings_changed)
    self.fps_spin.valueChanged.connect(self._settings_changed)
    output_layout.addLayout(form)
    folder_row = QHBoxLayout()
    folder_row.setSpacing(7)
    self.output_input = QLineEdit(self.preferences.value("output_dir", ""))
    self.output_input.setPlaceholderText(tr("默认：视频旁 / FramePick"))
    self.output_input.setToolTip(tr("留空时保存在视频旁的 FramePick 文件夹"))
    self.output_input.setMinimumWidth(0)
    self.output_input.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
    folder_row.addWidget(self.output_input, 1)
    choose = button("…", self.choose_output, tooltip=tr("选择输出文件夹"))
    choose.setFixedWidth(38)
    folder_row.addWidget(choose)
    output_layout.addLayout(folder_row)
    self.export_button = button(tr("全部导出 GIF"), self.export_all, primary=True)
    self.retry_button = button(tr("导出选中 / 重试失败"), self.export_selected)
    output_layout.addWidget(self.export_button)
    output_layout.addWidget(self.retry_button)
    self.progress_label = QLabel(tr("尚未开始导出"))
    self.progress_label.setWordWrap(True)
    self.progress_label.setObjectName("muted")
    output_layout.addWidget(self.progress_label)
    self.progress = QProgressBar()
    self.progress.setRange(0, 1000)
    self.progress.setValue(0)
    self.progress.setFixedHeight(7)
    self.progress.setTextVisible(False)
    output_layout.addWidget(self.progress)
    footer = QHBoxLayout()
    self.cancel_button = button(tr("取消导出"), self.cancel_export)
    self.cancel_button.setObjectName("danger")
    footer.addWidget(self.cancel_button)
    footer.addWidget(button(tr("打开目录"), self.reveal_output))
    output_layout.addLayout(footer)
    right_layout.addWidget(self.output_panel)

    self.left_scroll = scroll_pane(left, "previewScroll", 480)
    self.right_scroll = scroll_pane(right, "sidebarScroll", 300)
    self.splitter.addWidget(self.left_scroll)
    self.splitter.addWidget(self.right_scroll)
    self.splitter.setStretchFactor(0, 3)
    self.splitter.setStretchFactor(1, 1)
    self.splitter.setSizes([870, 365])
    layout.addWidget(self.splitter, 1)
    self.setCentralWidget(root)
    self.menuBar().setMinimumHeight(32)
    self.statusBar().setSizeGripEnabled(False)
    self.statusBar().setMinimumHeight(26)
