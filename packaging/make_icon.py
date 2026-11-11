"""Generate the SoundPod Windows icon (ICO) from the app's green play mark."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "packaging" / "soundpod.ico"

SCALE = 4
BASE = 256


def render() -> Image.Image:
    size = BASE * SCALE
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    margin = 10 * SCALE
    radius = 52 * SCALE
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=radius,
        fill=(31, 157, 85, 255),
        outline=(126, 240, 168, 255),
        width=6 * SCALE,
    )

    # Play triangle.
    cx, cy = size * 0.52, size * 0.50
    half = size * 0.20
    points = [
        (cx - half * 0.85, cy - half * 1.15),
        (cx - half * 0.85, cy + half * 1.15),
        (cx + half * 1.15, cy),
    ]
    draw.polygon(points, fill=(234, 255, 241, 255))

    # Small sound-wave bars for the "pod" feel.
    bar_color = (234, 255, 241, 255)
    base_x = size * 0.30
    for index, height in enumerate((0.10, 0.17, 0.23, 0.15)):
        x = base_x + index * size * 0.035
        y0 = size * 0.50 - size * height / 2
        y1 = size * 0.50 + size * height / 2
        draw.rounded_rectangle(
            [x, y0, x + size * 0.018, y1],
            radius=size * 0.009,
            fill=bar_color,
        )
    return image


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    image = render()
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    image.save(OUT, format="ICO", sizes=sizes)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
