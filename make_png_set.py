#!/usr/bin/env python3
"""
Generate N PNG files with a target total size, FAST (stdlib only).

Speed tricks:
- Build one PNG of the target per-file size and write it N times.
- Per row: b'\x00' + os.urandom(3*width) once, then repeat for height.
- zlib level=0 (stored blocks): size ~ linear, minimal CPU.
- Optional --unique: append a fixed-length tEXt chunk with a per-file token.
- Optional --jobs: parallelize file writes.

Examples:
  python make_png_set_fast.py --outdir out --num-files 1000 --total-size 1 --unit GB
  python make_png_set_fast.py --outdir out --num-files 500 --total-size 2 --unit GiB --png-width 512 --unique --jobs 4
"""

import argparse, os, struct, zlib, os as _os
from concurrent.futures import ThreadPoolExecutor

PNG_SIG = b"\x89PNG\r\n\x1a\n"

def _crc32(data: bytes) -> int:
    import binascii
    return binascii.crc32(data) & 0xFFFFFFFF

def _chunk(typ: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + typ + data + struct.pack(">I", _crc32(typ + data))

def build_png_bytes_fast(width: int, height: int, row_data: bytes) -> bytes:
    """
    Build a valid 8-bit RGB PNG quickly:
      - IHDR once
      - raw = (b'\x00' + row_data) * height
      - IDAT = zlib.compress(raw, level=0)
    """
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit RGB
    row = b"\x00" + row_data  # filter 0 + RGB row
    raw = row * height
    idat = zlib.compress(raw, level=0)
    return b"".join([PNG_SIG, _chunk(b"IHDR", ihdr), _chunk(b"IDAT", idat), _chunk(b"IEND", b"")])

def fixed_len_text_chunk(tag: str, content: str, total_len: int) -> bytes:
    """
    Make a tEXt chunk 'tag\\0content' ensuring *content* has a fixed total length.
    If content is shorter, pad with spaces; if longer, truncate.
    """
    key = tag.encode("latin-1")
    c = content.encode("latin-1")
    if len(c) < total_len:
        c = c + b" " * (total_len - len(c))
    elif len(c) > total_len:
        c = c[:total_len]
    data = key + b"\x00" + c
    return _chunk(b"tEXt", data)

def pick_height_for_target(per_file_target: int, width: int, row_data_len: int) -> tuple[int, bytes]:
    """
    Choose height so that PNG >= per_file_target. We build with a single random row.
    Size progression is linear in height at level=0, so this converges in a few steps.
    """
    import secrets
    row_data = secrets.token_bytes(row_data_len)  # random RGB row
    # Estimate: each row contributes (1 + row_data_len) bytes into raw before zlib headers
    # We'll start near target.
    base_overhead = 100  # cushion
    row_stride = 1 + row_data_len
    height = max(1, (per_file_target - base_overhead) // row_stride)
    png = build_png_bytes_fast(width, height, row_data)
    # grow until >= target
    while len(png) < per_file_target:
        height += 1
        png = build_png_bytes_fast(width, height, row_data)
    return height, png, row_data

def to_bytes(total: float, unit: str) -> int:
    u = unit.lower()
    if u == "gib": return int(total * (1024 ** 3))
    if u == "mb":  return int(total * 1_000_000)
    return int(total * 1_000_000_000)  # GB (decimal)

def write_file(path: str, data: bytes) -> None:
    with open(path, "wb", buffering=1024*1024) as f:
        f.write(data)

def main():
    ap = argparse.ArgumentParser(description="Fast PNG set generator (stdlib only).")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--num-files", type=int, required=True)
    ap.add_argument("--total-size", type=float, required=True)
    ap.add_argument("--unit", choices=["GB","GiB","MB"], default="GB")
    ap.add_argument("--png-width", type=int, default=512, help="PNG pixel width (>= 32 recommended)")
    ap.add_argument("--unique", action="store_true",
                    help="Make files differ via a fixed-length tEXt chunk (same size across files).")
    ap.add_argument("--jobs", type=int, default=1, help="Parallel writers (I/O bound).")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    total_bytes = to_bytes(args.total_size, args.unit)
    if args.num_files < 1:
        raise SystemExit("num-files must be >= 1")
    if args.png_width < 32:
        raise SystemExit("png-width too small (use >= 32)")

    per_file_target = max(1, total_bytes // args.num_files)

    # Build one PNG near per-file target (width fixed; choose height)
    row_len = 3 * args.png_width
    height, base_png, row_data = pick_height_for_target(per_file_target, args.png_width, row_len)
    per_file_size = len(base_png)

    # If we need to *increase* by a small, fixed delta (to get closer to target), we can append a fixed tEXt chunk
    # (PNG allows ancillary chunks anywhere before IEND; we’ll put it before IEND).
    # For speed, we only do this when --unique is set (and keep size the same for all files).
    texc = b""
    if args.unique:
        # 48-byte token yields constant extra size; same for all, content differs per file but stays same length.
        # We'll later rewrite the last 48 bytes of the tEXt content per file.
        texc = fixed_len_text_chunk("Comment", "X"*48, 48)
        # splice tEXt before IEND
        # base_png = PNG_SIG + IHDR + IDAT + IEND
        # insert texc before final 12 bytes of IEND
        if not base_png.endswith(_chunk(b"IEND", b"")):
            # rebuild to ensure standard ending
            pass
        # replace ending with tEXt + IEND
        base_png = base_png[:-12] + texc + base_png[-12:]
        per_file_size = len(base_png)

    # Now we have the final per-file data template
    print(f"Target total: {total_bytes:,} bytes  | files: {args.num_files}")
    print(f"Per-file target: {per_file_target:,} bytes  | actual per-file: {per_file_size:,} bytes")
    approx_total = per_file_size * args.num_files
    print(f"Approx total written: {approx_total:,} bytes (~ {(approx_total/1_000_000_000):.6f} GB)")

    # Prepare all outputs (if unique, patch the tEXt payload per file with a fixed-length token)
    def build_payload(i: int) -> bytes:
        if not args.unique:
            return base_png
        # Find the tEXt chunk we injected: it’s right before the final IEND
        # …base_png = (prefix) + tEXt(len=... "Comment\0" + 48 bytes) + IEND(12 bytes)
        # Patch the last 48 bytes of the tEXt data area with a constant-length token.
        # tEXt base structure: [len][b'tEXt'][data][crc]
        # We’ll re-create the tEXt chunk with a per-file content to keep CRC correct.
        token = f"IMG_{i:08d}_TOKEN_XXXXXXXXXXXXXXXXXXXX".encode("latin-1")  # 32+ bytes
        token = token[:48] if len(token) >= 48 else token + b" "*(48-len(token))
        new_texc = fixed_len_text_chunk("Comment", token.decode("latin-1"), 48)
        return base_png[:-12 - len(texc)] + new_texc + base_png[-12:]

    # File names
    paths = [os.path.join(args.outdir, f"img_{i:05d}.png") for i in range(1, args.num_files+1)]

    if args.jobs > 1:
        with ThreadPoolExecutor(max_workers=args.jobs) as ex:
            for i, p in enumerate(paths, start=1):
                ex.submit(write_file, p, build_payload(i))
    else:
        for i, p in enumerate(paths, start=1):
            write_file(p, build_payload(i))

    # Final report
    try:
        total_written = sum(_os.path.getsize(p) for p in paths)
    except Exception:
        total_written = approx_total
    print(f"Done. Total written: {total_written:,} bytes (~ {(total_written/1_000_000_000):.6f} GB)")
    print("Tip: If you need to be closer to the requested total, tweak --total-size slightly (±0.5%).")

if __name__ == "__main__":
    main()