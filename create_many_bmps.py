#!/usr/bin/env python3
import os
import random
import struct
import argparse
import time

# ---------------- BMP GENERATOR (24-bit uncompressed) ---------------- #

def make_bmp(width: int, height: int, seed: int) -> bytes:
    """Return bytes of a valid 24-bit BMP image with random RGB pixels."""
    random.seed(seed)

    # Each row padded to 4 bytes
    row_bytes = (width * 3 + 3) & ~3
    pixel_data_size = row_bytes * height
    file_size = 54 + pixel_data_size

    # BITMAPFILEHEADER (14 bytes)
    bfType = b'BM'
    bfSize = struct.pack("<I", file_size)
    bfReserved = b"\x00\x00\x00\x00"
    bfOffBits = struct.pack("<I", 54)

    # BITMAPINFOHEADER (40 bytes)
    biSize = struct.pack("<I", 40)
    biWidth = struct.pack("<i", width)
    biHeight = struct.pack("<i", height)
    biPlanes = struct.pack("<H", 1)
    biBitCount = struct.pack("<H", 24)
    biCompression = struct.pack("<I", 0)
    biSizeImage = struct.pack("<I", pixel_data_size)
    biXPelsPerMeter = struct.pack("<i", 2835)
    biYPelsPerMeter = struct.pack("<i", 2835)
    biClrUsed = struct.pack("<I", 0)
    biClrImportant = struct.pack("<I", 0)

    header = (
        bfType + bfSize + bfReserved + bfOffBits +
        biSize + biWidth + biHeight + biPlanes + biBitCount +
        biCompression + biSizeImage + biXPelsPerMeter +
        biYPelsPerMeter + biClrUsed + biClrImportant
    )

    # Pixel data (BGR per pixel, rows bottom→top)
    row = bytearray(row_bytes)
    pixels = bytearray(pixel_data_size)
    for y in range(height):
        for x in range(width):
            base = x * 3
            row[base:base+3] = bytes([random.randrange(256), random.randrange(256), random.randrange(256)])
        # pad row
        row[width*3:row_bytes] = b'\x00' * (row_bytes - width*3)
        start = y * row_bytes
        pixels[start:start + row_bytes] = row

    return header + pixels

# ---------------- UTILITIES ---------------- #

def to_bytes(size_value: float, unit: str) -> int:
    unit = unit.lower()
    if unit == "gib":
        return int(size_value * (1024 ** 3))
    if unit == "gb":
        return int(size_value * 1_000_000_000)
    if unit == "mb":
        return int(size_value * 1_000_000)
    if unit == "mib":
        return int(size_value * (1024 ** 2))
    return int(size_value)

# ---------------- MAIN ---------------- #

def main():
    ap = argparse.ArgumentParser(description="Generate random BMP images (stdlib only).")
    ap.add_argument("--out-dir", required=True, help="Output directory for BMPs.")
    ap.add_argument("--count", type=int, required=True, help="Number of BMPs to generate.")
    ap.add_argument("--target-size", type=float, required=True, help="Target total size (e.g. 4.0)")
    ap.add_argument("--unit", choices=["B", "MB", "MiB", "GB", "GiB"], default="MB", help="Unit for target size.")
    ap.add_argument("--unique-lines", type=int, default=10, help="How many scanlines per image to randomize uniquely.")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    total_target = to_bytes(args.target_size, args.unit)
    per_image_target = total_target // args.count

    # approximate square dimension based on size
    # 3 bytes per pixel + header overhead ≈ 54 bytes
    pixels_needed = max(1, (per_image_target - 54) // 3)
    side = int(pixels_needed ** 0.5)

    print(f"[INFO] Generating {args.count} BMPs in {args.out_dir}")
    print(f"[INFO] Each ~{per_image_target/1_000_000:.2f} MB, dimension ~{side}x{side}px")

    start_time = time.time()
    for i in range(args.count):
        bmp_path = os.path.join(args.out_dir, f"random_{i+1:05d}.bmp")
        bmp_bytes = make_bmp(side, side, seed=i + args.unique_lines)
        with open(bmp_path, "wb") as f:
            f.write(bmp_bytes)
        if (i + 1) % max(1, args.count // 10) == 0:
            print(f"  → {i+1}/{args.count} done")

    elapsed = time.time() - start_time
    print(f"[DONE] Created {args.count} BMPs in {elapsed:.1f}s (total ~{args.target_size} {args.unit})")

if __name__ == "__main__":
    main()