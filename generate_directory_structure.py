#!/usr/bin/env python3
"""
Generate a folder structure under a base path.

Structure:
  <base_path>/<parent_name>/<child_name>/<subfolder>

Naming scheme:
  Parent: <base_number><suffix>
  Child : <base_number>-<index>_NL_<date><suffix>
  Subfolder: constant name (default: "EXTRACTIONS")

Example:
  python GenerateFoldersWithDiffSenas.py --base-path "Y:\\AP_TWINS\\VAULT" --start 81000 --count 10
"""

import os
import logging
import argparse
from datetime import datetime
from pathlib import Path

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


def generate_parent_name(base_number: int, suffix: str) -> str:
    """Return parent folder name from base number + suffix."""
    return f"{base_number}{suffix}"


def generate_child_name(base_number: int, index: int, date_str: str, suffix: str) -> str:
    """Return child folder name using base number, index, date string, and suffix."""
    return f"{base_number}-{index}_0_NL_{date_str}{suffix}"


def create_folder_structure(
    base_path: Path,
    start_number: int,
    total_folders: int,
    date_str: str,
    suffix: str = "",
    subfolder: str = "EXTRACTIONS"
) -> None:
    """
    Create folder structure with parent/child/subfolder levels.

    Args:
        base_path: Root path where structure will be created
        start_number: Starting base number for naming
        total_folders: Number of sets to create
        date_str: Date string for naming
        suffix: Optional suffix for folder names
        subfolder: Subfolder name inside each child folder
    """
    for i in range(1, total_folders + 1):
        base_number = start_number + i

        # Parent
        parent_name = generate_parent_name(base_number, suffix)
        parent_path = base_path / parent_name
        parent_path.mkdir(parents=True, exist_ok=True)

        # Child
        child_name = generate_child_name(base_number, i, date_str, suffix)
        child_path = parent_path / child_name
        child_path.mkdir(parents=True, exist_ok=True)

        # Subfolder
        subfolder_path = child_path / subfolder
        subfolder_path.mkdir(parents=True, exist_ok=True)

        logging.info("Created %s", subfolder_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate folder structures with parent/child/subfolder naming"
    )
    parser.add_argument("--base-path", type=Path, required=True,
                        help="Root path where folders will be created")
    parser.add_argument("--start", type=int, required=True,
                        help="Starting number for naming")
    parser.add_argument("--count", type=int, required=True,
                        help="How many sets of folders to create")
    parser.add_argument("--suffix", type=str, default="",
                        help="Optional suffix for folder names (default: '')")
    parser.add_argument("--subfolder", type=str, default="EXTRACTIONS",
                        help="Subfolder name inside each child (default: EXTRACTIONS)")
    parser.add_argument("--date", type=str,
                        default=datetime.today().strftime("%Y%m%d"),
                        help="Date string for naming (default: today YYYYMMDD)")

    args = parser.parse_args()

    logging.info("Generating %d folder sets under %s", args.count, args.base_path)
    create_folder_structure(
        base_path=args.base_path,
        start_number=args.start,
        total_folders=args.count,
        date_str=args.date,
        suffix=args.suffix,
        subfolder=args.subfolder,
    )
    logging.info("Done.")


if __name__ == "__main__":
    main()