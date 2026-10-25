"""Gera assets/app.ico (ícone do aplicativo). Requer Pillow."""

import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))


def draw(size: int = 256) -> Image.Image:
    s = size / 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([8 * s, 8 * s, 248 * s, 248 * s], 44 * s,
                        fill=(29, 36, 51))
    d.line([70 * s, 36 * s, 70 * s, 84 * s], fill=(200, 205, 212),
           width=int(10 * s))
    d.rounded_rectangle([28 * s, 84 * s, 228 * s, 210 * s], 16 * s,
                        fill=(58, 61, 66), outline=(20, 20, 22),
                        width=int(4 * s))
    d.rectangle([44 * s, 100 * s, 156 * s, 150 * s], fill=(240, 160, 48))
    for i, h in enumerate((10, 18, 26, 34)):
        x = 56 * s + i * 22 * s
        d.rectangle([x, 142 * s - h * s, x + 14 * s, 142 * s],
                    fill=(40, 22, 0))
    d.ellipse([170 * s, 104 * s, 214 * s, 148 * s], fill=(22, 23, 26),
              outline=(110, 113, 118), width=int(4 * s))
    for i in range(4):
        x = 44 * s + i * 30 * s
        d.rectangle([x, 168 * s, x + 22 * s, 190 * s], fill=(200, 204, 210))
    d.ellipse([178 * s, 164 * s, 206 * s, 192 * s], fill=(22, 23, 26))
    return img


if __name__ == "__main__":
    out = os.path.join(ROOT, "assets", "app.ico")
    draw().save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                            (64, 64), (128, 128), (256, 256)])
    draw().save(os.path.join(ROOT, "assets", "app.png"))
    print("gerado", out)
