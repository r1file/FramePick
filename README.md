# FramePick

简体中文 · [English](README.en.md) · [日本語](README.ja.md)

[下载便携版 / Releases](https://github.com/r1file/FramePick/releases)

0.3.0 内置英语、简体中文、日语，首次启动跟随系统语言，右上角可即时切换。默认加载对应的 Noto Sans / SC / JP 开源字体，时间码使用 JetBrains Mono。首次打开有操作引导；片段缩略图在后台按需读取单帧，局部时间轴拖拽停在边缘可持续滚动。

**从长视频里，用一个可移动的时间窗口收集精彩片段。批量导出独立 GIF，一键保存截图。**

FramePick is a native, local desktop tool for picking moments from long videos. Move a fixed-duration window, collect several moments, then export one GIF per clip.

**0.3.0：便携单文件、自带 FFmpeg、可拖入工作区、首次导入自动显示首帧。** 按钮使用矢量图标与键帽，时间码使用加粗等宽字体；刻度两端向内排版，结束时间即使不是整秒也完整显示。小窗口和高 DPI 下通过独立面板与滚动布局避免重叠。

## 使用流程

1. 打开本地视频，或拖入窗口。视频按需播放，不会整体导入为图片帧。
2. 点击全片时间轴快速定位，在局部时间轴拖动青色窗口精调。
3. 窗口默认 **5 秒**，可自定义；可选择向后取、取刚看过的几秒或居中取。
4. 按 **A** 收集当前片段，继续挑选其他位置。按 **L** 循环预览当前窗口。
5. 点击「全部导出 GIF」。每段生成独立文件，可取消、重试失败项或仅导出选中项。
6. 按 **S** 将当前位置保存为原分辨率 PNG。截图和 GIF 保存到输出文件夹。
7. **↑ / ↓** 在已收集片段间快速跳转；**M** 切换静音，悬停扬声器按钮调节音量。

工程可保存为 `.framepick.json`，再次打开后继续选段。程序关闭时会写入本地恢复记录，使用「文件 → 恢复上次选段」找回。工程保存片段时间和视频路径，不复制原视频；移动视频后可重新定位。

## 为什么不会导入整个视频

- 播放使用 Qt Multimedia 的 FFmpeg 后端，直接读取本地文件；没有全片图片提取、场景扫描、代理转换或整片缩略图预生成。
- 每个 GIF 的两遍处理都使用 **输入端 `-ss` + 输入端 `-t`**，并在滤镜前执行 `trim`。
- 第一遍只为选中范围生成一个调色板；第二遍只读取同一范围并编码。没有 `split → palettegen/paletteuse` 的整段帧缓存。
- 默认单个后台导出任务，每个 FFmpeg 进程限制解码/滤镜线程数。播放和导出相互独立。
- 定位压缩视频仍需要容器索引和前一个关键帧附近的解码；「只处理片段」不表示完全没有元数据读取或关键帧预读。

3 小时低分辨率测试源的回归测试验证了：请求 5 秒时，调色板只接收该范围的源帧；另检查了输出时长、跨场景画面位置、独立文件、取消和错误管道。详见 [架构](docs/architecture.md)。

## 下载与运行

默认构建产物是**单个可执行文件**，包括 Python、Qt 播放环境、ffmpeg 和 ffprobe，不需要用户另外安装或配置 PATH。Windows、macOS、Linux 各自在对应系统构建；GitHub Actions 提供跨平台构建和 SHA-256 校验文件。

Windows / Linux 工具版本与校验值固定在 [`packaging/media-tools.json`](packaging/media-tools.json)。播放使用 Qt 随附的媒体库，导出与截图默认使用单文件内部的独立工具。在「工具 → FFmpeg 工具设置」可查看**实际来源和路径**；显式开启高级选项才优先使用外部目录。环境变量覆盖保留给开发者。运行无需联网、账号或上传。

- Windows：双击 `FramePick-0.3.0-windows-amd64.exe`，只需这一个文件。
- Linux：为 `FramePick-0.3.0-linux-x86_64` 加上执行权限后运行。构建基于 Ubuntu 22.04；仍需要系统自身的桌面/显示服务与兼容的 glibc。
- macOS：可构建单文件，或使用 `--mode onedir` 构建 `.app`；当前未签名或公证。

单文件启动时会将动态库和媒体工具释放到系统临时目录，退出后清理。因此文件体积、启动时间和临时磁盘占用会高于不带工具的目录包；它是无需安装的自解压便携程序，首次启动可能稍慢。

便携配置和恢复记录默认保存在程序旁的 `FramePick.data/`。移动程序时可一起携带该文件夹；程序目录只读时回退到用户数据目录。升级后「恢复上次选段」仍可读取旧版恢复记录。

## 从源码运行

Python 3.11+；开发和本机验证使用 Python 3.12。依赖使用 Qt 6 的 Essentials + Addons，不安装 WebEngine/PDF；界面是 QWidget，不运行浏览器或本地 Web 服务。

```powershell
# Windows / PowerShell 7
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m framepick
```

```bash
# macOS / Linux
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m framepick
```

```text
framepick --open /path/to/video.mp4
framepick --project /path/to/highlights.framepick.json
framepick doctor --video /path/to/video.mp4
framepick export /path/to/highlights.framepick.json --output /path/to/gifs
```

`FRAMEPICK_FFMPEG`、`FRAMEPICK_FFPROBE` 可指定完整的工具可执行文件路径。CLI 导出不启动 Qt 界面。未完成文件写入单独临时目录，成功后发布；不会覆盖已有输出。导出错误的详细日志位于输出目录，界面「工具」菜单也可打开最近日志。

## 快捷键

| 操作 | 快捷键 |
| --- | --- |
| 播放 / 暂停 | Space |
| 静音 / 取消静音 | M |
| 上一个 / 下一个已收集片段 | ↑ / ↓ |
| 收集当前窗口 | A |
| 一键截图 | S |
| 循环预览窗口 | L |
| 跳转 1 秒 / 10 秒 | ← → / Shift + ← → |
| 平移窗口 0.1 秒 | [ / ] |
| 按标称帧率微调播放位置 | , / . |
| 打开视频 / 保存工程 | Ctrl+O / Ctrl+S |
| 打开工程 / 工程另存为 | Ctrl+Shift+O / Ctrl+Shift+S |

输入框获得焦点时，单字母快捷键不触发。对于可变帧率视频，`, / .` 是时间微调，不保证逐个真实解码帧步进。

## 开发与打包

```text
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
python scripts/build.py
```

开发依赖包括 PyInstaller；默认构建为自带工具的 one-file 便携程序。构建脚本下载并校验固定版本的 Windows / Linux LGPL 工具，复用已校验的缓存。macOS 开发构建显式暂存本机工具并收集动态依赖。打包排除 WebEngine、PDF、QML Python 模块和测试依赖。

`python scripts/build.py --mode onedir` 保留目录分发选项，适合开发、快速启动和替换 Qt 动态库；`--no-tools` 只用于开发时生成依赖外部 FFmpeg 的包。

包内播放器和导出的端到端验收：

```text
FramePick self-test --video sample.mp4 --report check/report.json --screenshot check/window.png
```

自检会加载实际视频、等待解码画面、添加两个 2 秒片段、导出两个 GIF 和一张 PNG，然后退出；设置和恢复记录单独保存到报告目录。请使用非隐私测试素材，输出目录须为空。

`python scripts/check_bundle.py` 会将**仅一个 EXE/可执行文件**复制到隔离目录，清空 PATH 和工具覆盖变量，再验证首帧、播放、GIF、截图及内置工具来源。详见 [第三方说明](THIRD_PARTY_NOTICES.md)。

## 当前边界

- 本地有限时长视频；不支持直播流、DRM、在线下载或自动精彩识别。
- GIF 为无声格式。当前没有字幕烧录、画面裁剪、转场或复杂图层编辑。
- HDR 素材的显示和导出色彩可能因平台而不同；初版未提供专门的 HDR 色调映射。
- 内存和导出耗时随所选片段的时长、分辨率和帧率变化。默认 640px / 15 FPS；超长 GIF 应降低输出设置。
- 当前 Windows 已在本机实际验证；macOS / Linux 的流程已配置，成功构建和播放仍需对应系统验证。

## License

FramePick source: [MIT](LICENSE). Qt/PySide and FFmpeg retain their own licenses; see [third-party notices](THIRD_PARTY_NOTICES.md). See [CONTRIBUTING](CONTRIBUTING.md) for maintenance rules.
