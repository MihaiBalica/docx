#!/usr/bin/env python3
"""
Generate a set of PNG files with predictable size.

- Pure Python standard library (no Pillow, etc.).
- Each PNG is a valid 8-bit RGB image with random pixel data.
- You choose the number of files and the total size; script divides evenly.

Usage:
  python make_png_set.py --outdir out_pngs --num-files 1000 --total-size 1 --unit GB
"""

import argparse, os, random, struct, zlib

PNG_SIG = b"\x89PNG\r\n\x1a\n"

def _crc32(data: bytes) -> int:
    import binascii
    return binascii.crc32(data) & 0xFFFFFFFF

def _chunk(typ: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + typ + data + struct.pack(">I", _crc32(typ + data))

def build_png_bytes(width: int, height: int, seed: int) -> bytes:
    """
    Minimal 8-bit RGB PNG (color type 2), zlib level=0, with random data.
    """
    rng = random.Random(seed)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row_len = 1 + 3 * width
    raw = bytearray(row_len * height)
    p = 0
    for _ in range(height):
        raw[p] = 0
        p += 1
        for _ in range(width * 3):
            raw[p] = rng.randrange(0, 256)
            p += 1
    idat = zlib.compress(bytes(raw), level=0)
    return b"".join([PNG_SIG, _chunk(b'IHDR', ihdr), _chunk(b'IDAT', idat), _chunk(b'IEND', b"")])

def choose_png_for_target_size(target_bytes: int, width: int = 256) -> tuple[int, bytes]:
    """
    Pick a height such that PNG >= target_bytes.
    """
    base_overhead = 100
    row_bytes = 1 + 3 * width
    height = max(1, (target_bytes - base_overhead) // row_bytes)
    seed = 1234
    png = build_png_bytes(width, height, seed)
    while len(png) < target_bytes:
        height += 1
        seed += 1
        png = build_png_bytes(width, height, seed)
    return height, png

def to_bytes(value: float, unit: str) -> int:
    if unit.lower() == "gib":
        return int(value * (1024 ** 3))
    return int(value * 1_000_000_000)

def main():
    ap = argparse.ArgumentParser(description="Generate N PNGs totalling a given size.")
    ap.add_argument("--outdir", required=True, help="Output directory")
    ap.add_argument("--num-files", type=int, required=True, help="Number of PNG files to generate")
    ap.add_argument("--total-size", type=float, required=True, help="Total size target")
    ap.add_argument("--unit", choices=["GB", "GiB", "MB"], default="GB", help="Units for total size")
    ap.add_argument("--png-width", type=int, default=256, help="Width in pixels (controls aspect)")
    args = ap.parse_args()

    total_bytes = to_bytes(args.total_size, args.unit) if args.unit in ("GB", "GiB") else int(args.total_size * 1_000_000)
    per_file_target = max(1, total_bytes // args.num_files)

    os.makedirs(args.outdir, exist_ok=True)

    # Find geometry for per-file size
    height, sample_png = choose_png_for_target_size(per_file_target, args.png_width)
    per_png_size = len(sample_png)

    print(f"Target total: {args.total_size} {args.unit} (~{total_bytes:,} bytes)")
    print(f"Files: {args.num_files}, each ~{per_png_size:,} bytes ({args.png_width}x{height}px)")

    seed = 1000
    written = 0
    for i in range(1, args.num_files + 1):
        png = build_png_bytes(args.png_width, height, seed)
        seed += 1
        if len(png) != per_png_size:
            png = sample_png  # fallback for consistency
        fn = os.path.join(args.outdir, f"img_{i:05d}.png")
        with open(fn, "wb") as f:
            f.write(png)
        written += len(png)
        if i % 100 == 0 or i == args.num_files:
            print(f"  wrote {i}/{args.num_files} ... total {written:,} bytes")

    print(f"Done. Wrote {args.num_files} PNGs, total {written:,} bytes")

if __name__ == "__main__":
    main()