#!/usr/bin/env python3
import argparse, os, random, struct, zlib, zipfile, time

PNG_SIG = b"\x89PNG\r\n\x1a\n"

def _crc32(data: bytes) -> int:
    import binascii
    return binascii.crc32(data) & 0xFFFFFFFF

def _chunk(typ: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + typ + data + struct.pack(">I", _crc32(typ + data))

def build_png_bytes(width_px: int, height_px: int, seed: int) -> bytes:
    rng = random.Random(seed)
    ihdr = struct.pack(">IIBBBBB", width_px, height_px, 8, 2, 0, 0, 0)  # 8-bit RGB
    row_len = 1 + 3 * width_px
    raw = bytearray(row_len * height_px)
    p = 0
    for _ in range(height_px):
        raw[p] = 0  # filter type 0
        p += 1
        for _ in range(width_px * 3):
            raw[p] = rng.randrange(0, 256)
            p += 1
    idat = zlib.compress(bytes(raw), level=0)  # predictable
    return b"".join([PNG_SIG, _chunk(b'IHDR', ihdr), _chunk(b'IDAT', idat), _chunk(b'IEND', b"")])

def choose_png_height_for_size(per_image_target: int, width_px: int) -> tuple[int, bytes]:
    base_overhead = 100
    row_bytes = 1 + 3 * width_px
    height_px = max(1, (per_image_target - base_overhead) // row_bytes)
    seed = 1234
    png = build_png_bytes(width_px, height_px, seed)
    attempts = 0
    while len(png) < per_image_target and attempts < 100000:
        height_px += 1
        seed += 1
        png = build_png_bytes(width_px, height_px, seed)
        attempts += 1
    return height_px, png

def emu_from_cm(cm: float) -> int:
    return int((cm / 2.54) * 914400)

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml"  ContentType="application/xml"/>
  <Default Extension="png"  ContentType="image/png"/>
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

def build_doc_rels(num_images: int) -> str:
    parts = ["""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
"""]
    for i in range(1, num_images + 1):
        parts.append(f"""  <Relationship Id="rIdImg{i}"
                Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
                Target="media/image{i:05d}.png"/>
""")
    parts.append("</Relationships>\n")
    return "".join(parts)

def build_document_xml(num_images: int, cx_emu: int, cy_emu: int) -> str:
    head = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
            xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
            xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"
            xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">
  <w:body>
    <w:p><w:r><w:t>Generated document displaying {num_images} image(s).</w:t></w:r></w:p>
"""
    body = []
    for i in range(1, num_images + 1):
        body.append(f"""    <w:p>
      <w:r>
        <w:drawing>
          <wp:inline distT="0" distB="0" distL="0" distR="0">
            <wp:extent cx="{cx_emu}" cy="{cy_emu}"/>
            <wp:docPr id="{i}" name="Picture {i}"/>
            <a:graphic>
              <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
                <pic:pic>
                  <pic:nvPicPr>
                    <pic:cNvPr id="{i}" name="image{i:05d}.png"/>
                    <pic:cNvPicPr/>
                  </pic:nvPicPr>
                  <pic:blipFill>
                    <a:blip r:embed="rIdImg{i}"/>
                    <a:stretch><a:fillRect/></a:stretch>
                  </pic:blipFill>
                  <pic:spPr>
                    <a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx_emu}" cy="{cy_emu}"/></a:xfrm>
                    <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
                  </pic:spPr>
                </pic:pic>
              </a:graphicData>
            </a:graphic>
          </wp:inline>
        </w:drawing>
      </w:r>
    </w:p>
""")
    tail = """    <w:sectPr>
      <w:pgSz w:w="11907" w:h="16840"/>
      <w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="708" w:footer="708" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>
"""
    return head + "".join(body) + tail

def make_docx_all_visible(docx_path: str,
                  num_images: int,
                  target_total_bytes: int,
                  png_width_px: int = 512,
                  page_width_cm: float = 21.0,
                  left_margin_cm: float = 2.0,
                  right_margin_cm: float = 2.0) -> dict:
    if num_images < 1:
        raise ValueError("num_images must be >= 1")
    if png_width_px < 1:
        raise ValueError("png_width_px must be >= 1")

    # Compute display width (content width) in EMU
    content_width_cm = max(0.5, page_width_cm - left_margin_cm - right_margin_cm)
    cx_emu = emu_from_cm(content_width_cm)

    # --- First pass: assume square display to estimate media budget conservatively ---
    placeholder_cy = cx_emu
    rels_xml = build_doc_rels(num_images)
    placeholder_doc_xml = build_document_xml(num_images, cx_emu, placeholder_cy)

    base_fixed = (len(CONTENT_TYPES.encode("utf-8")) +
                  len(RELS_ROOT.encode("utf-8")) +
                  len(rels_xml.encode("utf-8")) +
                  len(placeholder_doc_xml.encode("utf-8")))

    SAFETY_ZIP_OVERHEAD = 800_000  # a bit higher to avoid edge cases
    bytes_for_media = max(1, target_total_bytes - base_fixed - SAFETY_ZIP_OVERHEAD)
    per_image_target = max(1, bytes_for_media // num_images)

    # Choose PNG height to meet per-image target
    png_height_px, sample_png = choose_png_height_for_size(per_image_target, png_width_px)
    per_png_bytes = len(sample_png)

    # Now rebuild the document XML with the correct cy honoring aspect ratio
    cy_emu = max(1, int(cx_emu * (png_height_px / float(png_width_px))))
    document_xml = build_document_xml(num_images, cx_emu, cy_emu)

    # Write DOCX
    root, ext = os.path.splitext(docx_path)
    if ext.lower() != ".docx":
        docx_path = root + ".docx"

    with zipfile.ZipFile(docx_path, "w", allowZip64=True) as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES)
        zf.writestr("_rels/.rels", RELS_ROOT)
        zf.writestr("word/_rels/document.xml.rels", rels_xml)
        zf.writestr("word/document.xml", document_xml)

        seed = 10000
        for i in range(1, num_images + 1):
            if i == 1:
                png_bytes = sample_png
            else:
                png_bytes = build_png_bytes(png_width_px, png_height_px, seed)
            seed += 1
            if len(png_bytes) != per_png_bytes:
                png_bytes = sample_png
            name = f"word/media/image{i:05d}.png"
            zinfo = zipfile.ZipInfo(name)
            zinfo.compress_type = zipfile.ZIP_STORED
            zf.writestr(zinfo, png_bytes)

    final_size = os.path.getsize(docx_path)
    return {
        "docx_path": docx_path,
        "num_images": num_images,
        "png_px": (png_width_px, png_height_px),
        "display_emu": (cx_emu, cy_emu),
        "per_png_bytes": per_png_bytes,
        "final_bytes": final_size,
    }

# ----- Simple validator for the result -----
def validate_docx(path: str) -> None:
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(path, "r") as z:
        names = set(z.namelist())
        for req in ("[Content_Types].xml","_rels/.rels","word/document.xml","word/_rels/document.xml.rels"):
            if req not in names:
                print("❌ Missing part:", req); return
        # check relationships count and targets
        drels = z.read("word/_rels/document.xml.rels").decode("utf-8","replace")
        rel_ids = [line.split('Id="')[1].split('"',1)[0] for line in drels.splitlines() if 'Relationship Id=' in line]
        # naive scan of r:embed in document.xml
        doc_xml = z.read("word/document.xml").decode("utf-8","replace")
        embeds = []
        i = 0
        while True:
            j = doc_xml.find('r:embed="', i)
            if j == -1: break
            k = doc_xml.find('"', j+9)
            embeds.append(doc_xml[j+9:k])
            i = k+1
        if len(embeds) != len(rel_ids):
            print(f"⚠️ Mismatch embeds vs rels: {len(embeds)} vs {len(rel_ids)}")
        # try parsing XMLs
        try: ET.fromstring(z.read("[Content_Types].xml"))
        except Exception as e: print("❌ content types parse error:", e); return
        try: ET.fromstring(z.read("_rels/.rels"))
        except Exception as e: print("❌ root rels parse error:", e); return
        try: ET.fromstring(z.read("word/_rels/document.xml.rels"))
        except Exception as e: print("❌ doc rels parse error:", e); return
        try: ET.fromstring(z.read("word/document.xml"))
        except Exception as e: print("❌ document.xml parse error:", e); return
    print("✅ Basic structure & XML parse OK.")

def to_bytes(value: float, unit: str) -> int:
    return int(value * (1024**3)) if unit.lower() == "gib" else int(value * 1_000_000_000)
# ---------------- CLI ----------------
def main():
    start_time = time.time()

    ap = argparse.ArgumentParser(description="Make a .docx (stdlib only) with ALL PNGs displayed at A4 width.")
    ap.add_argument("--docx-path", required=True, help="Output .docx path")
    ap.add_argument("--num-images", type=int, required=True, help="Number of PNGs to embed & display")
    ap.add_argument("--target-size", type=float, required=True, help="Target total size")
    ap.add_argument("--unit", choices=["GB", "GiB"], default="GB", help="Units for target size")
    ap.add_argument("--png-width-px", type=int, default=512, help="PNG pixel width (>=512 recommended)")
    ap.add_argument("--page-width-cm", type=float, default=21.0, help="A4 width in cm")
    ap.add_argument("--margin-left-cm", type=float, default=2.0)
    ap.add_argument("--margin-right-cm", type=float, default=2.0)
    args = ap.parse_args()

    target_bytes = to_bytes(args.target_size, args.unit)
    info = make_docx_all_visible(
        args.docx_path,
        args.num_images,
        target_bytes,
        png_width_px=args.png_width_px,
        page_width_cm=args.page_width_cm,
        left_margin_cm=args.margin_left_cm,
        right_margin_cm=args.margin_right_cm,
    )

    fb = info["final_bytes"]
    def from_bytes(n, unit):  # local helper for pretty print
        return n / (1024**3) if unit.lower() == "gib" else n / 1_000_000_000

    duration = time.time() - start_time
    print(f"Created: {info['docx_path']}")
    print(f"Images displayed: {info['num_images']}")
    print(f"PNG geometry (px): {info['png_px'][0]}x{info['png_px'][1]}")
    print(f"Display size (EMU): {info['display_emu'][0]} x {info['display_emu'][1]}")
    print(f"Per PNG bytes: {info['per_png_bytes']:,}")
    print(f"Actual size: {fb:,} bytes  (≈ {from_bytes(fb,'GB'):.6f} GB | {from_bytes(fb,'GiB'):.6f} GiB)")
    print(f"Duration: {duration:.2f} seconds ({duration/60:.2f} min, {duration/3600:.2f} hr)")

    # Optional quick validation
    validate_docx(info['docx_path'])


if __name__ == "__main__":
    main()