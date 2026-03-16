"""
Generate a simple app icon (PNG and ICO) using only standard library.
Run this once to create the icon files.

Usage: python assets/generate_icon.py
"""
import struct
import zlib
import os


def create_png(width, height, pixels):
    """Create a minimal PNG file from RGBA pixel data."""
    def chunk(chunk_type, data):
        c = chunk_type + data
        crc = struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack('>I', len(data)) + c + crc

    # PNG signature
    sig = b'\x89PNG\r\n\x1a\n'

    # IHDR
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    ihdr = chunk(b'IHDR', ihdr_data)

    # IDAT - raw pixel data with filter byte
    raw = b''
    for y in range(height):
        raw += b'\x00'  # filter: none
        for x in range(width):
            raw += bytes(pixels[y][x])

    compressed = zlib.compress(raw)
    idat = chunk(b'IDAT', compressed)

    # IEND
    iend = chunk(b'IEND', b'')

    return sig + ihdr + idat + iend


def draw_icon():
    """Draw a simple document icon with 'CFR' text concept."""
    size = 64
    pixels = [[(30, 30, 46, 255)] * size for _ in range(size)]

    # Draw a document shape (white rectangle with folded corner)
    for y in range(8, 56):
        for x in range(14, 50):
            if y < 16 and x > 40:
                # Folded corner area
                if x - 40 + 8 > y:
                    continue
                pixels[y][x] = (180, 190, 220, 255)
            else:
                pixels[y][x] = (240, 240, 250, 255)

    # Draw blue header bar
    for y in range(16, 24):
        for x in range(14, 50):
            pixels[y][x] = (137, 180, 250, 255)  # Blue accent

    # Draw text lines (dark gray)
    for line_y in [28, 33, 38, 43]:
        for x in range(18, 46):
            if line_y == 28:
                end = 40
            elif line_y == 33:
                end = 44
            elif line_y == 38:
                end = 36
            else:
                end = 42
            if x < end:
                pixels[line_y][x] = (100, 100, 120, 255)

    # Draw a small green checkmark in bottom right
    check_points = [(48, 52), (49, 53), (50, 54), (51, 53), (52, 52), (53, 51), (54, 50)]
    for cx, cy in check_points:
        if 0 <= cx < size and 0 <= cy < size:
            pixels[cy][cx] = (80, 220, 120, 255)
            if cy + 1 < size:
                pixels[cy + 1][cx] = (80, 220, 120, 255)

    return pixels


def create_ico(png_data):
    """Create a minimal ICO file from PNG data."""
    # ICO header: reserved=0, type=1(icon), count=1
    header = struct.pack('<HHH', 0, 1, 1)
    # Directory entry: width, height, colors, reserved, planes, bpp, size, offset
    entry = struct.pack('<BBBBHHII', 64, 64, 0, 0, 1, 32, len(png_data), 22)
    return header + entry + png_data


def main():
    pixels = draw_icon()
    png_data = create_png(64, 64, pixels)

    script_dir = os.path.dirname(os.path.abspath(__file__))

    png_path = os.path.join(script_dir, "icon.png")
    with open(png_path, "wb") as f:
        f.write(png_data)
    print(f"Created {png_path}")

    ico_path = os.path.join(script_dir, "icon.ico")
    ico_data = create_ico(png_data)
    with open(ico_path, "wb") as f:
        f.write(ico_data)
    print(f"Created {ico_path}")


if __name__ == "__main__":
    main()
