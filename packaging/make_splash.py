"""Generate the SoundPod startup splash image."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "packaging" / "splash.png"
WIDTH, HEIGHT = 560, 300


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        Path(r"C:\Windows\Fonts") / name,
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(str(candidate), size)
        except OSError:
            continue
    return ImageFont.load_default()


def main() -> None:
    image = Image.new("RGBA", (WIDTH, HEIGHT), (15, 19, 25, 255))
    draw = ImageDraw.Draw(image)

    # Subtle green border.
    draw.rounded_rectangle(
        [1, 1, WIDTH - 2, HEIGHT - 2],
        radius=16,
        outline=(46, 204, 113, 210),
        width=2,
    )

    # Green play tile.
    tile = 128
    x0, y0 = 42, (HEIGHT - tile) // 2
    draw.rounded_rectangle(
        [x0, y0, x0 + tile, y0 + tile],
        radius=28,
        fill=(31, 157, 85, 255),
        outline=(126, 240, 168, 255),
        width=3,
    )
    cx, cy = x0 + tile * 0.52, y0 + tile * 0.50
    half = tile * 0.20
    draw.polygon(
        [
            (cx - half * 0.85, cy - half * 1.15),
            (cx - half * 0.85, cy + half * 1.15),
            (cx + half * 1.15, cy),
        ],
        fill=(234, 255, 241, 255),
    )

    title_font = font("segoeuib.ttf", 46)
    body_font = font("segoeui.ttf", 20)
    small_font = font("segoeui.ttf", 15)

    draw.text((202, 92), "SoundPod", font=title_font, fill=(241, 245, 249, 255))
    draw.text((204, 154), "Starting the soundboard…", font=body_font, fill=(170, 184, 200, 255))
    draw.text(
        (204, 196),
        "Loading audio engine, library and hotkeys",
        font=small_font,
        fill=(127, 140, 156, 255),
    )

    # Small progress bar.
    draw.rounded_rectangle([204, 236, 500, 244], radius=4, fill=(38, 49, 63, 255))
    draw.rounded_rectangle([204, 236, 380, 244], radius=4, fill=(46, 204, 113, 255))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUT)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
