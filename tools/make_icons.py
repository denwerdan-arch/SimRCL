"""Draws the icons of the SimRCL Python tags (lines and shapes only, no icon fonts).

Usage: python make_icons.py <icons folder>
"""
import math
import os
import sys

from PIL import Image, ImageDraw

SIZE, SUPER = 64, 8  # drawn 8x larger, then downsampled for anti-aliasing
GREY, LIGHT, ORANGE = (200, 200, 200, 255), (200, 200, 200, 70), (255, 163, 0, 255)


def _canvas():
    image = Image.new("RGBA", (SIZE * SUPER,) * 2, (0, 0, 0, 0))
    return image, ImageDraw.Draw(image)


def _save(image, path):
    image.resize((SIZE, SIZE), Image.LANCZOS).save(path)


def _arrow(draw, start, end, width, head):
    draw.line((start, end), fill=ORANGE, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    for tip, direction in ((end, angle), (start, angle + math.pi)):
        wings = [(tip[0] - head * math.cos(direction + side), tip[1] - head * math.sin(direction + side)) for side in (0.5, -0.5)]
        draw.polygon([tip] + wings, fill=ORANGE)


def uv_scale(path):
    """A tiled UV square with a diagonal two-headed scale arrow."""
    image, draw = _canvas()
    big, margin, cells = SIZE * SUPER, 6 * SUPER, 3
    step = (big - 2 * margin) / cells
    for row in range(cells):
        for col in range(cells):
            if (row + col) % 2 == 0:
                x, y = margin + col * step, margin + row * step
                draw.rectangle((x, y, x + step, y + step), fill=LIGHT)
    draw.rectangle((margin, margin, big - margin, big - margin), outline=GREY, width=3 * SUPER)
    inset = 15 * SUPER
    _arrow(draw, (inset, big - inset), (big - inset, inset), 5 * SUPER, 13 * SUPER)
    _save(image, path)


def round_corners(path):
    """A box outline whose top right corner is a thick orange fillet."""
    image, draw = _canvas()
    big, margin, radius, width = SIZE * SUPER, 8 * SUPER, 24 * SUPER, 4 * SUPER
    left, top, right, bottom = margin, margin, big - margin, big - margin
    draw.rectangle((left, top, right, bottom), fill=LIGHT)
    draw.line((left, top, right - radius, top), fill=GREY, width=width)
    draw.line((right, top + radius, right, bottom), fill=GREY, width=width)
    draw.line((left, top, left, bottom), fill=GREY, width=width)
    draw.line((left, bottom, right, bottom), fill=GREY, width=width)
    # hide the square corner behind the fillet before drawing it
    draw.rectangle((right - radius, top - width, right + width, top + radius), fill=(0, 0, 0, 0))
    draw.pieslice((right - 2 * radius, top, right, top + 2 * radius), 270, 360, fill=LIGHT)
    draw.arc((right - 2 * radius, top, right, top + 2 * radius), 270, 360, fill=ORANGE, width=2 * width)
    _save(image, path)


if __name__ == "__main__":
    folder = sys.argv[1]
    uv_scale(os.path.join(folder, "simrs_uv_scale.png"))
    round_corners(os.path.join(folder, "simrs_round_corners.png"))
