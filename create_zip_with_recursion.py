#!/usr/bin/env python3
"""
Create nested ZIP archives up to N levels deep.

At the deepest level, a text file is created.
Each folder level above it is zipped, producing nested archives.

Example (N=3):
    base/
      level1/
        level2/
          level3/
            file.txt
    => creates level3.zip, level2.zip, level1.zip
"""

import os
import zipfile
import argparse
from pathlib import Path

def make_text_file(path: Path, content: str = "Sample text content") -> None:
    """Create a text file with given content."""
    path.write_text(content, encoding="utf-8")

def zip_directory(directory: Path) -> Path:
    """Create a ZIP archive for the given directory and return the ZIP file path."""
    zip_path = directory.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(directory):
            for file in files:
                full_path = Path(root) / file
                arcname = full_path.relative_to(directory)
                zf.write(full_path, arcname)
    return zip_path

def build_nested_archives(base_dir: Path, depth: int) -> None:
    """
    Create nested directories N levels deep, a text file at the bottom,
    then zip each level going upwards.
    """
    if depth < 1:
        raise ValueError("Depth must be at least 1")

    # Step 1: Build nested folder structure
    current = base_dir
    for i in range(1, depth + 1):
        current = current / f"level{i}"
        current.mkdir(parents=True, exist_ok=True)

    # Step 2: Create a text file at the deepest level
    text_file = current / "file.txt"
    make_text_file(text_file, f"This is a text file at depth {depth}\nPath: {text_file}")

    # Step 3: Go upward, zipping each level
    for i in range(depth, 0, -1):
        folder = base_dir.joinpath(*[f"level{j}" for j in range(1, i + 1)])
        zip_path = zip_directory(folder)
        print(f"Created ZIP: {zip_path}")

def main():
    parser = argparse.ArgumentParser(description="Create N-level nested ZIP archives.")
    parser.add_argument("--base-dir", "-b", type=Path, required=True, help="Base directory to create structure in")
    parser.add_argument("--depth", "-n", type=int, required=True, help="Number of nested levels")
    args = parser.parse_args()

    build_nested_archives(args.base_dir, args.depth)
    print("✅ Done creating nested archives.")

if __name__ == "__main__":
    main()