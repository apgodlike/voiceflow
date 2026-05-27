"""Generate assets/icon.ico — a simple mic glyph on a rounded blue tile.

Run from the repo root:  python tools/make_icon.py
Kept in-repo so the icon is reproducible rather than an opaque binary.
"""
from pathlib import Path

from PIL import Image, ImageDraw

_BG = (37, 99, 235)      # blue tile
_FG = (255, 255, 255)    # white mic
_SIZE = 256


def _draw(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = size // 6
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=_BG)

    # mic capsule
    cx = size / 2
    cap_w, cap_h = size * 0.30, size * 0.42
    top = size * 0.16
    d.rounded_rectangle(
        [cx - cap_w / 2, top, cx + cap_w / 2, top + cap_h],
        radius=cap_w / 2, fill=_FG,
    )
    # stand arc + post + base
    lw = max(2, size // 32)
    d.arc([cx - cap_w * 0.85, top + cap_h * 0.25, cx + cap_w * 0.85, top + cap_h * 1.15],
          start=20, end=160, fill=_FG, width=lw)
    post_top = top + cap_h * 1.05
    d.line([cx, post_top, cx, post_top + size * 0.12], fill=_FG, width=lw)
    base_y = post_top + size * 0.12
    d.line([cx - size * 0.10, base_y, cx + size * 0.10, base_y], fill=_FG, width=lw)
    return img


def main() -> None:
    out = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"
    out.parent.mkdir(parents=True, exist_ok=True)
    base = _draw(_SIZE)
    base.save(out, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
