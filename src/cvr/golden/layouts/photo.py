"""The placeholder photo the two-column Layout embeds: a grey head-and-shoulders
silhouette drawn pixel by pixel and packed as a PNG with the standard library.

Generated, never committed as a source file, and byte-identical on every
call: the deflate stream is written by hand as stored blocks rather than by
``zlib.compress``, whose output can differ between zlib builds and would
change the document SHA from one platform to the next.
"""

import struct
import zlib

__all__ = ["placeholder_photo"]

WIDTH, HEIGHT = 120, 150
_BACKGROUND, _FIGURE = 0xD9, 0x8C  # greyscale levels
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_GREYSCALE_8BIT = (8, 0)  # bit depth, colour type
_STORED_BLOCK_MAX = 0xFFFF
# Silhouette geometry, in pixels: a circle for the head over a half-ellipse
# (its centre on the bottom edge) for the shoulders.
_HEAD_CENTRE_Y, _HEAD_RADIUS = 52, 28
_SHOULDER_TOP_Y, _SHOULDER_RADIUS = 96, 54


def placeholder_photo() -> bytes:
    """A ``WIDTH`` x ``HEIGHT`` greyscale PNG of a head-and-shoulders outline."""
    rows = b"".join(b"\x00" + bytes(_row(y)) for y in range(HEIGHT))
    return _PNG_SIGNATURE + b"".join(
        (
            _chunk(
                b"IHDR",
                struct.pack(">IIBBBBB", WIDTH, HEIGHT, *_GREYSCALE_8BIT, 0, 0, 0),
            ),
            _chunk(b"IDAT", _zlib_stored(rows)),
            _chunk(b"IEND", b""),
        )
    )


def _row(y: int) -> list[int]:
    return [_FIGURE if _in_silhouette(x, y) else _BACKGROUND for x in range(WIDTH)]


def _in_silhouette(x: int, y: int) -> bool:
    dx = x - WIDTH / 2
    head = (dx / _HEAD_RADIUS) ** 2 + ((y - _HEAD_CENTRE_Y) / _HEAD_RADIUS) ** 2 <= 1
    shoulders = (
        y >= _SHOULDER_TOP_Y
        and (dx / _SHOULDER_RADIUS) ** 2 + ((y - HEIGHT) / _SHOULDER_RADIUS) ** 2 <= 1
    )
    return head or shoulders


def _chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data))
    )


def _zlib_stored(data: bytes) -> bytes:
    """A zlib stream of uncompressed deflate blocks: fixed bytes for fixed input."""
    blocks = [
        data[start : start + _STORED_BLOCK_MAX]
        for start in range(0, len(data), _STORED_BLOCK_MAX)
    ] or [b""]
    body = b"".join(
        bytes([index == len(blocks) - 1])
        + struct.pack("<HH", len(block), len(block) ^ 0xFFFF)
        + block
        for index, block in enumerate(blocks)
    )
    return b"\x78\x01" + body + struct.pack(">I", zlib.adler32(data))
