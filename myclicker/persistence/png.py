"""Minimal PNG codec for domain Images (8-bit RGB/RGBA, non-interlaced). Standard library only."""
from __future__ import annotations

import struct
import zlib

from myclicker.domain.model import Image

_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def encode(image: Image) -> bytes:
    """BGRA Image -> RGB PNG bytes."""
    raw = bytearray()
    stride = image.width * 4
    for row in range(image.height):
        line = image.bgra[row * stride:(row + 1) * stride]
        rgb = bytearray(image.width * 3)
        rgb[0::3], rgb[1::3], rgb[2::3] = line[2::4], line[1::4], line[0::4]
        raw += b"\0" + rgb
    header = struct.pack(">IIBBBBB", image.width, image.height, 8, 2, 0, 0, 0)
    return _SIGNATURE + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + _chunk(b"IEND", b"")


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def decode(data: bytes) -> Image:
    """PNG bytes (8-bit RGB or RGBA) -> BGRA Image."""
    if not data.startswith(_SIGNATURE):
        raise ValueError("not a PNG file")
    pos, idat = len(_SIGNATURE), b""
    width = height = channels = 0
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            width, height, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", body)
            if depth != 8 or color not in (2, 6) or interlace:
                raise ValueError("only 8-bit non-interlaced RGB/RGBA PNG is supported")
            channels = 3 if color == 2 else 4
        elif kind == b"IDAT":
            idat += body
        pos += 12 + length
    raw = zlib.decompress(idat)
    stride = width * channels
    prev = bytearray(stride)
    out = bytearray()
    for row in range(height):
        start = row * (stride + 1)
        kind = raw[start]
        line = bytearray(raw[start + 1:start + 1 + stride])
        for i in range(stride):
            left = line[i - channels] if i >= channels else 0
            up = prev[i]
            up_left = prev[i - channels] if i >= channels else 0
            if kind == 1:
                line[i] = (line[i] + left) & 0xFF
            elif kind == 2:
                line[i] = (line[i] + up) & 0xFF
            elif kind == 3:
                line[i] = (line[i] + (left + up) // 2) & 0xFF
            elif kind == 4:
                line[i] = (line[i] + _paeth(left, up, up_left)) & 0xFF
        for x in range(width):
            p = x * channels
            out += bytes((line[p + 2], line[p + 1], line[p], line[p + 3] if channels == 4 else 255))
        prev = line
    return Image(width, height, bytes(out))
