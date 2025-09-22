#!/usr/bin/env python3
"""
Delete a specific file from all subfolders under a root directory.

Features:
- Walks recursively with os.walk
- Deletes matching files
- Logs actions
- Confirmation prompt before deletion
"""

import os
import argparse
import logging
from pathlib import Path


# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


def delete_file_from_subfolders(root_folder: Path, target_filename: str, confirm: bool = True) -> int:
    """
    Delete all occurrences of target_filename inside root_folder recursively.

    Args:
        root_folder: Base folder to scan
        target_filename: File name to delete
        confirm: Whether to ask for confirmation before deletion

    Returns:
        int: Number of deleted files
    """
    deleted_count = 0
    candidates = []

    for foldername, _, filenames in os.walk(root_folder):
        for filename in filenames:
            if filename == target_filename:
                file_path = Path(foldername) / filename
                candidates.append(file_path)

    if not candidates:
        logging.info("No files named %s found under %s", target_filename, root_folder)
        return 0

    logging.info("Found %d files named %s under %s", len(candidates), target_filename, root_folder)

    if confirm:
        answer = input(f"Do you really want to delete {len(candidates)} file(s) named '{target_filename}'? [y/N]: ")
        if answer.lower() not in ("y", "yes"):
            logging.info("Deletion cancelled.")
            return 0

    for file_path in candidates:
        try:
            file_path.unlink()
            logging.info("Deleted %s", file_path)
            deleted_count += 1
        except Exception as e:
            logging.error("Failed to delete %s: %s", file_path, e)

    logging.info("Done. Deleted %d file(s) named '%s'", deleted_count, target_filename)
    return deleted_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete a specific file from all subfolders under a root directory")
    parser.add_argument("--root", "-r", type=Path, required=True, help="Root directory to scan")
    parser.add_argument("--filename", "-f", required=True, help="Target file name to delete (e.g., text_only_docx_2GB.docx)")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation (force delete)")

    args = parser.parse_args()

    if not args.root.is_dir():
        logging.error("Provided root directory does not exist: %s", args.root)
        return

    delete_file_from_subfolders(args.root, args.filename, confirm=not args.yes)


if __name__ == "__main__":
    main()