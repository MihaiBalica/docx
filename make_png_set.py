#!/usr/bin/env python3
"""
Generate N PNG files totalling a target size, FAST, with controllable uniqueness.

Uniqueness modes:
  - metadata : same pixels, inject per-file tEXt chunk (different bytes only)
  - pixels   : per-file unique RGB row, repeated for image (visually different) [default]
  - strong   : K unique rows per image (tiled), more varied visuals

Speed notes:
  - zlib level 0 + filter 0 keeps size linear and independent of content → identical size per file
  - No per-pixel Python loops; we build rows as bytes and repeat

Examples:
  python make_png_set_fast_unique.py --outdir out --num-files 1000 --total-size 1 --unit GB
  python make_png_set_fast_unique.py --outdir out --num-files 2000 --total-size 2 --unit GiB --png-width 512 --mode pixels --jobs 4
  python make_png_set_fast_unique.py --outdir out --num-files 500 --total-size 0.5 --unit GB --mode strong --rows-unique 8
"""

import argparse, os, struct, zlib, secrets
from concurrent.futures import ThreadPoolExecutor

PNG_SIG = b"\x89PNG\r\n\x1a\n"

def _crc32(data: bytes) -> int:
    import binascii
    return binascii.crc32(data) & 0xFFFFFFFF

def _chunk(typ: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + typ + data + struct.pack(">I", _crc32(typ + data))

def _ihdr(width: int, height: int) -> bytes:
    return _chunk(b'IHDR', struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))  # 8-bit RGB

def _iend() -> bytes:
    return _chunk(b'IEND', b"")

def build_png_from_rows(width: int, rows_rgb: bytes, height: int) -> bytes:
    """
    rows_rgb: concatenation of PNG scanlines WITHOUT filter byte (3*width per line) for a base period.
    We repeat that period to reach the requested height. Filter 0, zlib level 0.
    """
    row_len = 3 * width
    assert len(rows_rgb) % row_len == 0
    period = len(rows_rgb) // row_len
    # Build raw with filter byte 0 for each row
    raw = bytearray((row_len + 1) * height)
    # Fill by period to avoid Python loops per pixel
    pos = 0
    for r in range(height):
        raw[pos] = 0
        pos += 1
        off = (r % period) * row_len
        raw[pos:pos+row_len] = rows_rgb[off:off+row_len]
        pos += row_len
    idat = zlib.compress(bytes(raw), level=0)
    return b"".join([PNG_SIG, _ihdr(width, height), _chunk(b'IDAT', idat), _iend()])

def fixed_len_text_chunk(tag: str, content_bytes: bytes, fixed_len: int) -> bytes:
    if len(content_bytes) < fixed_len:
        content_bytes = content_bytes + b" " * (fixed_len - len(content_bytes))
    elif len(content_bytes) > fixed_len:
        content_bytes = content_bytes[:fixed_len]
    data = tag.encode("latin-1") + b"\x00" + content_bytes
    return _chunk(b"tEXt", data)

def insert_chunk_before_iend(png_bytes: bytes, chunk: bytes) -> bytes:
    # Replace final IEND with chunk + IEND
    return png_bytes[:-12] + chunk + png_bytes[-12:]

def pick_geometry_for_target(per_file_target: int, width: int, rows_in_period: int) -> tuple[int, bytes]:
    """
    Choose a height so that a PNG built from 'rows_in_period' unique rows meets per_file_target.
    We start with a reasonable estimate and grow.
    """
    row_len = 3 * width
    # Make a random period (rows_in_period rows)
    period = b"".join(secrets.token_bytes(row_len) for _ in range(rows_in_period))
    # Estimate: each row contributes (row_len + 1) raw bytes, plus small zlib overhead
    base_overhead = 150
    row_stride = row_len + 1
    height = max(rows_in_period, (per_file_target - base_overhead) // row_stride)
    png = build_png_from_rows(width, period, height)
    # grow until >= target
    while len(png) < per_file_target:
        height += 1
        png = build_png_from_rows(width, period, height)
    return height, period, png

def to_bytes(total: float, unit: str) -> int:
    u = unit.lower()
    if u == "gib": return int(total * (1024 ** 3))
    if u == "mb":  return int(total * 1_000_000)
    return int(total * 1_000_000_000)  # GB decimal

def main():
    ap = argparse.ArgumentParser(description="Fast PNG set generator with controllable uniqueness (stdlib only).")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--num-files", type=int, required=True)
    ap.add_argument("--total-size", type=float, required=True)
    ap.add_argument("--unit", choices=["GB","GiB","MB"], default="GB")
    ap.add_argument("--png-width", type=int, default=512, help="PNG pixel width (>= 32 recommended)")
    ap.add_argument("--mode", choices=["metadata","pixels","strong"], default="pixels",
                    help="Uniqueness mode: metadata (bytes differ), pixels (row differs), strong (several rows differ)")
    ap.add_argument("--rows-unique", type=int, default=8, help="For mode=strong, number of unique rows per image")
    ap.add_argument("--jobs", type=int, default=1, help="Parallel writers (I/O bound)")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    if args.num_files < 1: raise SystemExit("num-files must be >= 1")
    if args.png_width < 32: raise SystemExit("png-width too small (>=32)")

    total_bytes = to_bytes(args.total_size, args.unit)
    per_file_target = max(1, total_bytes // args.num_files)

    # Build a template based on the chosen uniqueness mode
    if args.mode == "metadata":
        # One pixel pattern for all files, same height for all
        height, period, base_png = pick_geometry_for_target(per_file_target, args.png_width, rows_in_period=1)
        # Inject a fixed-length tEXt placeholder we will rewrite per file
        placeholder = fixed_len_text_chunk("Comment", b"X"*48, 48)
        base_png = insert_chunk_before_iend(base_png, placeholder)
        tex_len = len(placeholder)
        def payload(i: int) -> bytes:
            token = f"FILE_{i:07d}_UNIQ_XXXXXXXXXXXXXXXXXXXX".encode("latin-1")
            token = token[:48] if len(token) >= 48 else token + b" "*(48-len(token))
            texc = fixed_len_text_chunk("Comment", token, 48)
            return base_png[:-12 - tex_len] + texc + base_png[-12:]
    elif args.mode == "pixels":
        # Each file gets its own unique row, same height/size
        height, period, sample_png = pick_geometry_for_target(per_file_target, args.png_width, rows_in_period=1)
        per_size = len(sample_png)
        def payload(i: int) -> bytes:
            row = secrets.token_bytes(3 * args.png_width)
            png = build_png_from_rows(args.png_width, row, height)
            # keep exact size by regenerating if needed (rare)
            if len(png) != per_size:
                return sample_png
            return png
    else:  # strong
        rows_in_period = max(2, args.rows_unique)
        height, period, sample_png = pick_geometry_for_target(per_file_target, args.png_width, rows_in_period)
        per_size = len(sample_png)
        def payload(i: int) -> bytes:
            # build a fresh period with 'rows_in_period' unique rows
            row_len = 3 * args.png_width
            p = b"".join(secrets.token_bytes(row_len) for _ in range(rows_in_period))
            png = build_png_from_rows(args.png_width, p, height)
            if len(png) != per_size:
                return sample_png
            return png

    # Prepare paths
    paths = [os.path.join(args.outdir, f"img_{i:05d}.png") for i in range(1, args.num_files + 1)]

    def write_one(i_path):
        i, path = i_path
        data = payload(i)
        with open(path, "wb", buffering=1024*1024) as f:
            f.write(data)
        return len(data)

    # Write files (optionally parallel)
    if args.jobs > 1:
        with ThreadPoolExecutor(max_workers=args.jobs) as ex:
            sizes = list(ex.map(write_one, enumerate(paths, start=1)))
    else:
        sizes = []
        for i, p in enumerate(paths, start=1):
            sizes.append(write_one((i, p)))

    total_written = sum(sizes)
    print(f"Files: {args.num_files} | per-file ~{sizes[0]:,} bytes | total ~{total_written:,} bytes "
          f"(~ {total_written/1_000_000_000:.6f} GB)")

if __name__ == "__main__":
    main()