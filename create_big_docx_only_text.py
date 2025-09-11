#!/usr/bin/env python3
"""
Create a huge text-only DOCX near a target size, with random-looking text.
Pure standard library. Fast: streams large randomized chunks.

Examples:
  python make_text_only_docx_random.py --out text_3p99gb.docx --target-size 3.99 --unit GB
  python make_text_only_docx_random.py --out text_3_9_gib.docx --target-size 3.9 --unit GiB --chunk-mb 4
"""

import argparse
import os
import random
import string
import zipfile

# ----------------- Minimal OOXML parts -----------------
CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml"  ContentType="application/xml"/>
  <Override PartName="/word/document.xml"
            ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
""".strip()

RELS_ROOT = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
                Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
                Target="word/document.xml"/>
</Relationships>
""".strip()

DOC_HEAD = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    <w:p><w:r><w:t>Text-only generated document (randomized).</w:t></w:r></w:p>
""".encode("utf-8")

DOC_TAIL = """    <w:sectPr>
      <w:pgSz w:w="11907" w:h="16840"/>
      <w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"
               w:header="708" w:footer="708" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>
""".encode("utf-8")

PARA_PREFIX = b'    <w:p><w:r><w:t xml:space="preserve">'
PARA_SUFFIX = b'</w:t></w:r></w:p>\n'
PARA_OVERHEAD = len(PARA_PREFIX) + len(PARA_SUFFIX)

ALPHA = string.ascii_lowercase  # safe for XML (no escaping)
SPACES = [" ", "  ", "   ", " ", "\t", " ", "    "]  # varied whitespace; xml:space="preserve" keeps them

# ----------------- Helpers -----------------
def to_bytes(value: float, unit: str) -> int:
    u = unit.lower()
    if u == "gib": return int(value * (1024 ** 3))
    if u == "mb":  return int(value * 1_000_000)
    return int(value * 1_000_000_000)  # decimal GB

def make_word(rng: random.Random, min_len=3, max_len=12) -> str:
    n = rng.randint(min_len, max_len)
    return "".join(rng.choice(ALPHA) for _ in range(n))

def make_random_text(rng: random.Random, target_len: int) -> bytes:
    """
    Build ~target_len chars of random words & spaces (ASCII only).
    We slightly overshoot and then trim to exact byte length.
    """
    parts = []
    total = 0
    # Build in chunks to reduce Python overhead
    while total < target_len:
        # One sentence-ish burst
        burst = []
        words = rng.randint(8, 18)
        for _ in range(words):
            burst.append(make_word(rng))
            burst.append(rng.choice(SPACES))
        burst.append("\n")  # occasional newline inside the text node
        s = "".join(burst)
        parts.append(s)
        total += len(s)
    text = "".join(parts)
    if len(text) > target_len:
        text = text[:target_len]
    return text.encode("ascii", "strict")

def build_paragraph_chunk(rng: random.Random, target_bytes: int, para_text_bytes: int) -> bytes:
    """
    Build a chunk consisting of many <w:p> paragraphs whose total size ~= target_bytes.
    Each paragraph contains xml:space='preserve' text of length 'para_text_bytes'.
    """
    if para_text_bytes < 32:
        para_text_bytes = 32
    chunk = bytearray()
    # Write full paragraphs until close to target
    while len(chunk) + PARA_OVERHEAD + para_text_bytes <= target_bytes:
        chunk += PARA_PREFIX
        chunk += make_random_text(rng, para_text_bytes)
        chunk += PARA_SUFFIX
    # Fit one last paragraph if we still have some room left
    remaining = target_bytes - len(chunk)
    if remaining > PARA_OVERHEAD + 8:  # leave some minimum room for text
        n_text = remaining - PARA_OVERHEAD
        chunk += PARA_PREFIX
        chunk += make_random_text(rng, n_text)
        chunk += PARA_SUFFIX
    return bytes(chunk)

def write_document_xml_stream(zf: zipfile.ZipFile,
                              entry_name: str,
                              total_target_bytes: int,
                              other_parts_bytes: int,
                              chunk_bytes: int,
                              para_text_bytes: int,
                              seed: int) -> None:
    """
    Stream word/document.xml so overall .docx ends up near total_target_bytes.
    """
    rng = random.Random(seed)

    # Budget for document.xml (we store entries as ZIP_STORED, so sizes add)
    budget_docxml = max(0, total_target_bytes - other_parts_bytes)

    zi = zipfile.ZipInfo(entry_name)
    zi.compress_type = zipfile.ZIP_STORED
    with zf.open(zi, mode="w", force_zip64=True) as w:
        # head
        w.write(DOC_HEAD)
        written = len(DOC_HEAD)

        # how much space left inside document.xml (including tail)
        remaining = max(0, budget_docxml - written - len(DOC_TAIL))

        # prebuild a randomized chunk ~chunk_bytes
        # to keep randomness across loops, rebuild every so often
        while remaining > 0:
            target_chunk = min(chunk_bytes, remaining)
            # Keep a tiny slack so metadata doesn't risk overflow
            if target_chunk <= PARA_OVERHEAD + 16:
                break
            chunk = build_paragraph_chunk(rng, target_chunk, para_text_bytes)
            w.write(chunk)
            written += len(chunk)
            remaining -= len(chunk)

        # tail
        w.write(DOC_TAIL)
        written += len(DOC_TAIL)
    # done (ZIP central directory written on close by caller)

# ----------------- Main builder -----------------
def make_text_only_docx_random(out_path: str,
                               target_bytes: int,
                               margin_bytes: int,
                               chunk_bytes: int,
                               para_text_bytes: int,
                               seed: int) -> int:
    # normalize extension
    root, ext = os.path.splitext(out_path)
    if ext.lower() != ".docx":
        out_path = root + ".docx"

    # aim just below target
    effective_target = max(1, target_bytes - max(0, margin_bytes))

    # sizes of fixed parts
    other_parts_bytes = (len(CONTENT_TYPES.encode("utf-8")) +
                         len(RELS_ROOT.encode("utf-8")))

    with zipfile.ZipFile(out_path, "w", allowZip64=True) as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES, compress_type=zipfile.ZIP_STORED)
        zf.writestr("_rels/.rels", RELS_ROOT, compress_type=zipfile.ZIP_STORED)
        write_document_xml_stream(
            zf,
            "word/document.xml",
            total_target_bytes=effective_target,
            other_parts_bytes=other_parts_bytes,
            chunk_bytes=chunk_bytes,
            para_text_bytes=para_text_bytes,
            seed=seed,
        )

    return os.path.getsize(out_path)

def main():
    ap = argparse.ArgumentParser(description="Create a text-only DOCX near a target size with random-looking text.")
    ap.add_argument("--out", required=True, help="Output .docx path")
    ap.add_argument("--target-size", type=float, required=True, help="Target size value (e.g., 3.99)")
    ap.add_argument("--unit", choices=["GB","GiB","MB"], default="GB", help="Size unit")
    ap.add_argument("--margin-bytes", type=int, default=2_000_000, help="Safety margin to stay below target (bytes)")
    ap.add_argument("--chunk-mb", type=float, default=4.0, help="Chunk size to stream per write (MB)")
    ap.add_argument("--para-bytes", type=int, default=4096, help="Approx text bytes per paragraph (before XML)")
    ap.add_argument("--seed", type=int, default=0, help="Random seed (0 -> derive from OS)")
    args = ap.parse_args()

    # derive bytes
    target_bytes = to_bytes(args.target_size, args.unit)
    chunk_bytes = max(256*1024, int(args.chunk_mb * 1_000_000))  # min 256KB chunk
    para_text_bytes = max(64, args.para_bytes)

    # seed
    seed = args.seed if args.seed != 0 else int.from_bytes(os.urandom(8), "big")

    final_size = make_text_only_docx_random(
        args.out, target_bytes, args.margin_bytes, chunk_bytes, para_text_bytes, seed
    )

    def fmt(b): return f"{b:,} bytes  (~ {b/1_000_000_000:.6f} GB | ~ {b/(1024**3):.6f} GiB)"
    print("Created:", os.path.abspath(args.out))
    print("Final size:", fmt(final_size))
    print("Tune speed/shape: --chunk-mb (bigger = fewer writes), --para-bytes (bigger = fewer paragraphs).")

if __name__ == "__main__":
    main()