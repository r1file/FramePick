"""Generate code-native application icons. Pillow is a dev-only dependency."""

from pathlib import Path

from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1]
directory = root / "assets"
directory.mkdir(exist_ok=True)
image = Image.new("RGBA", (512, 512), (17, 24, 33, 255))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((34, 34, 478, 478), radius=100, fill="#1b2d37")
draw.rounded_rectangle((92, 116, 420, 395), radius=34, outline="#5adbbd", width=22)
draw.rectangle((229, 116, 283, 395), fill="#1b2d37")
draw.line((235, 107, 235, 405), fill="#a1f4df", width=13)
draw.polygon(((276, 204), (276, 313), (353, 258)), fill="#5adbbd")
image.save(directory / "framepick.png")
image.save(
    directory / "framepick.ico",
    sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
)
image.save(directory / "framepick.icns")
