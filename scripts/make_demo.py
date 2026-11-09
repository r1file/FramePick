"""Create a small non-private sample for package smoke tests and UI previews."""

from __future__ import annotations

import argparse
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from framepick.media import Tools, hidden_process_options

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, default=Path("artifacts/demo/Evening Lake.mp4"))
args = parser.parse_args()
args.output.parent.mkdir(parents=True, exist_ok=True)
image = Image.new("RGB", (960, 540))
draw = ImageDraw.Draw(image)
for y in range(540):
    mix = y / 540
    color = tuple(
        round(a * (1 - mix) + b * mix) for a, b in zip((18, 35, 67), (232, 171, 120), strict=True)
    )
    draw.line((0, y, 960, y), fill=color)
draw.ellipse((690, 86, 774, 170), fill=(255, 215, 153))
draw.polygon(
    [
        (0, 320),
        (160, 195),
        (270, 280),
        (420, 135),
        (625, 310),
        (775, 220),
        (960, 330),
        (960, 540),
        (0, 540),
    ],
    fill=(39, 67, 86),
)
draw.polygon(
    [(0, 390), (145, 310), (305, 385), (545, 250), (795, 385), (960, 328), (960, 540), (0, 540)],
    fill=(23, 45, 63),
)
draw.rectangle((0, 415, 960, 540), fill=(29, 57, 74))
for y in range(425, 540, 8):
    length = int(24 + 90 * math.sin(y / 60) ** 2)
    draw.line((730 - length, y, 730 + length, y), fill=(137, 123, 99), width=2)
png = args.output.with_suffix(".png")
image.save(png)
subprocess.run(
    [
        str(Tools.discover().ffmpeg),
        "-v",
        "error",
        "-y",
        "-loop",
        "1",
        "-i",
        str(png),
        "-vf",
        "zoompan=z='min(zoom+0.00025,1.15)':d=750:s=960x540:fps=25",
        "-t",
        "30",
        "-c:v",
        "mpeg4",
        "-q:v",
        "3",
        "-pix_fmt",
        "yuv420p",
        str(args.output),
    ],
    check=True,
    timeout=90,
    **hidden_process_options(),
)
print(args.output)
