#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile

try:
    from PIL import Image, ImageDraw, ImageFilter
except ModuleNotFoundError as exc:  # pragma: no cover - local tooling guard
    raise SystemExit("Pillow is required to generate icons. Install it with: pip install Pillow") from exc


ROOT_DIR = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT_DIR / "assets" / "icons"
BASE_SIZE = 1024
PNG_SIZES = (16, 24, 32, 48, 64, 128, 256, 512, 1024)
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return mask


def linear_gradient(size: int) -> Image.Image:
    image = Image.new("RGBA", (size, size))
    pixels = image.load()
    stops = (
        (0.0, (20, 50, 77)),
        (0.52, (15, 118, 110)),
        (1.0, (245, 158, 11)),
    )
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1))
            left, right = stops[0], stops[-1]
            for index in range(len(stops) - 1):
                if stops[index][0] <= t <= stops[index + 1][0]:
                    left, right = stops[index], stops[index + 1]
                    break
            span = right[0] - left[0] or 1.0
            local = (t - left[0]) / span
            color = tuple(int(left[1][i] + (right[1][i] - left[1][i]) * local) for i in range(3))
            pixels[x, y] = (*color, 255)
    return image


def draw_icon() -> Image.Image:
    size = BASE_SIZE
    scale = size / 1024
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    background = linear_gradient(size)
    image.alpha_composite(background)
    image.putalpha(rounded_mask(size, int(228 * scale)))

    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow, "RGBA")
    shadow_draw.rounded_rectangle((262, 307, 846, 769), radius=84, fill=(6, 24, 39, 98))
    shadow = shadow.filter(ImageFilter.GaussianBlur(22))
    image.alpha_composite(shadow)

    draw = ImageDraw.Draw(image, "RGBA")
    draw.rounded_rectangle((198, 287, 826, 747), radius=80, fill=(226, 252, 248, 255))
    draw.rounded_rectangle((216, 305, 808, 729), radius=64, outline=(255, 255, 255, 92), width=10)

    draw.line((385, 337, 331, 270), fill=(226, 232, 240, 255), width=30)
    draw.line((639, 337, 693, 270), fill=(226, 232, 240, 255), width=30)
    draw.rounded_rectangle((316, 325, 708, 688), radius=88, fill=(15, 118, 110, 255))
    draw.rectangle((316, 476, 708, 688), fill=(15, 118, 110, 255))
    draw.rounded_rectangle((316, 536, 708, 688), radius=56, fill=(15, 118, 110, 255))

    draw.ellipse((421, 429, 475, 483), fill=(236, 254, 255, 255))
    draw.ellipse((549, 429, 603, 483), fill=(236, 254, 255, 255))
    draw.line((387, 571, 470, 571, 501, 519, 555, 635, 594, 571, 639, 571), fill=(245, 158, 11, 255), width=34, joint="curve")
    draw.line((296, 737, 728, 737), fill=(236, 254, 255, 210), width=30)
    return image


def resize_icon(base: Image.Image, size: int) -> Image.Image:
    return base.resize((size, size), Image.Resampling.LANCZOS)


def write_pngs(base: Image.Image) -> None:
    for size in PNG_SIZES:
        resize_icon(base, size).save(ICON_DIR / f"app_icon_{size}.png")
    resize_icon(base, 1024).save(ICON_DIR / "app_icon.png")


def write_ico(base: Image.Image) -> None:
    base.save(ICON_DIR / "app_icon.ico", sizes=[(size, size) for size in ICO_SIZES])


def write_icns(base: Image.Image) -> None:
    try:
        base.save(ICON_DIR / "app_icon.icns")
        return
    except OSError:
        pass

    iconutil = shutil.which("iconutil")
    if not iconutil:
        return
    with tempfile.TemporaryDirectory() as tmp_dir:
        iconset = Path(tmp_dir) / "app_icon.iconset"
        iconset.mkdir(parents=True, exist_ok=True)
        for point_size in (16, 32, 128, 256, 512):
            resize_icon(base, point_size).save(iconset / f"icon_{point_size}x{point_size}.png")
            resize_icon(base, point_size * 2).save(iconset / f"icon_{point_size}x{point_size}@2x.png")
        completed = subprocess.run(
            [iconutil, "--convert", "icns", "--output", str(ICON_DIR / "app_icon.icns"), str(iconset)],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            message = (completed.stderr or completed.stdout or "iconutil failed").strip()
            print(f"Skipping app_icon.icns: {message}")


def main() -> int:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    base = draw_icon()
    write_pngs(base)
    write_ico(base)
    write_icns(base)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
