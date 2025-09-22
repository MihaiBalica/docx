#!/usr/bin/env python3
"""
List files in a directory tree and save their relative paths.

Features:
- Walks a directory recursively
- Writes relative paths into an output file (UTF-8)
- Optional filtering (prefix/suffix/substring)
- Output filename automatically prefixed with timestamp
"""

import os
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


def list_files_recursive(
    directory: Path,
    output_file: Path,
    root_prefix: Optional[Path] = None,
    startswith: Optional[str] = None,
    contains: Optional[str] = None,
) -> int:
    """
    Recursively walk through `directory` and write matching relative paths to `output_file`.

    Args:
        directory: Root directory to scan
        output_file: Output file to write results
        root_prefix: If given, strip this prefix from paths
        startswith: Only include files whose relative path starts with this string
        contains: Only include files whose relative path contains this substring

    Returns:
        int: number of files written
    """
    count = 0
    with output_file.open("w", encoding="utf-8") as f:
        for root, _, files in os.walk(directory):
            for file in files:
                full_path = Path(root) / file
                if root_prefix:
                    relative_path = full_path.relative_to(root_prefix)
                else:
                    relative_path = full_path.relative_to(directory)

                rel_str = str(relative_path).replace("\\", "/")

                if startswith and not rel_str.startswith(startswith):
                    continue
                if contains and contains not in rel_str:
                    continue

                f.write(rel_str + "\n")
                count += 1

    logging.info("Wrote %d file paths to %s", count, output_file)
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recursively list files under a directory and save relative paths."
    )
    parser.add_argument("--directory", "-d", type=Path,
                        default=Path(r"Y:\AP_TWINS\VAULT"),
                        help="Directory to scan (default: Y:\\AP_TWINS\\VAULT)")
    parser.add_argument("--output", "-o", type=Path,
                        default=Path("file_list.txt"),
                        help="Base name of output file (timestamp is prefixed)")
    parser.add_argument("--startswith", help="Filter: include only files whose relative path starts with this string")
    parser.add_argument("--contains", help="Filter: include only files whose relative path contains this string")

    args = parser.parse_args()

    if not args.directory.is_dir():
        logging.error("Provided directory %s does not exist", args.directory)
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = Path(f"{timestamp}_{args.output.name}")

    logging.info("Scanning directory: %s", args.directory)
    logging.info("Output file: %s", output_file)

    list_files_recursive(
        directory=args.directory,
        output_file=output_file,
        root_prefix=args.directory,
        startswith=args.startswith,
        contains=args.contains
    )


if __name__ == "__main__":
    main()