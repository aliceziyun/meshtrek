"""Span reader/writer utility.

Reads all JSON files in a directory and writes entries in chunks of N (default 500).

Two input groups are processed separately:
- formatted_spans_*.json       -> aggregated into spans chunks
- formatted_spans_meta_*.json  -> aggregated into meta chunks

Output files are written as JSON objects with up to N entries each.
"""

from __future__ import annotations

import os
import json
import math
from typing import Dict, List, Tuple


def _list_files(dir_path: str, prefix: str) -> List[str]:
    """List JSON files under dir_path that start with prefix and end with .json.

    Returns files sorted by name for deterministic processing.
    """
    try:
        names = os.listdir(dir_path)
    except FileNotFoundError:
        return []
    files = [
        os.path.join(dir_path, n)
        for n in names
        if n.startswith(prefix) and n.endswith(".json")
    ]
    return sorted(files)


def _read_all_entries(file_paths: List[str]) -> Dict[str, dict]:
    """Read JSON objects from file paths and merge all entries into a dict.

    Later files override earlier entries on key collision.
    """
    merged: Dict[str, dict] = {}
    for fp in file_paths:
        with open(fp, "r") as f:
            try:
                data = json.load(f)
                if isinstance(data, dict):
                    merged.update(data)
                else:
                    # If file is an array of entries with id fields, convert to dict (best effort)
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                rid = item.get("request_id") or item.get("id")
                                if rid is not None:
                                    merged[str(rid)] = item
                    # else ignore malformed
            except json.JSONDecodeError:
                # Skip malformed files
                continue
    return merged


def _chunk_and_write(entries: List[Tuple[str, dict]], out_dir: str, base_name: str, chunk_size: int = 500) -> List[str]:
    """Write entries into chunked JSON object files.

    entries: list of (key, value) pairs, already ordered.
    Returns list of written file paths.
    """
    if not entries:
        return []
    os.makedirs(out_dir, exist_ok=True)

    total = len(entries)
    num_parts = math.ceil(total / chunk_size)
    written: List[str] = []
    for part_idx in range(num_parts):
        start = part_idx * chunk_size
        end = min(start + chunk_size, total)
        part_entries = entries[start:end]
        obj: Dict[str, dict] = {k: v for k, v in part_entries}
        # Name files by cumulative count, e.g., formatted_spans_500.json, formatted_spans_1000.json
        cumulative = end
        out_name = f"{base_name}_{cumulative}.json"
        out_path = os.path.join(out_dir, out_name)
        with open(out_path, "w") as f:
            json.dump(obj, f, separators=(",", ":"))
        written.append(out_path)
    return written


def process_directory(input_dir: str, output_dir: str | None = None, chunk_size: int = 500) -> Dict[str, List[str]]:
    """Process a directory and write chunked outputs for spans and meta files.

    Returns dict with keys 'spans_files' and 'meta_files' containing written paths.
    """
    output_dir = output_dir or input_dir

    # Gather files separately
    span_files = _list_files(input_dir, prefix="formatted_spans_")
    meta_files = _list_files(input_dir, prefix="formatted_spans_meta_")

    # Avoid double counting meta if prefix overlaps: remove meta files from spans
    meta_set = set(meta_files)
    span_files = [fp for fp in span_files if fp not in meta_set]

    # Read and merge entries
    span_entries = _read_all_entries(span_files)
    meta_entries = _read_all_entries(meta_files)

    # Order deterministically by key
    span_items = sorted(span_entries.items(), key=lambda kv: kv[0])
    meta_items = sorted(meta_entries.items(), key=lambda kv: kv[0])

    # Write
    spans_written = _chunk_and_write(
        span_items, out_dir=output_dir, base_name="formatted_spans", chunk_size=chunk_size
    )
    meta_written = _chunk_and_write(
        meta_items, out_dir=output_dir, base_name="formatted_spans_meta", chunk_size=chunk_size
    )

    return {"spans_files": spans_written, "meta_files": meta_written}


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="span_reader_writer",
        description="Read span JSONs and write chunked outputs (500 entries per file by default).",
    )
    parser.add_argument(
        "-d", "--dir", dest="input_dir", required=True, help="Input directory containing JSON files",
    )
    parser.add_argument(
        "-o", "--out", dest="output_dir", required=False, default=None, help="Output directory (default: same as input)",
    )
    parser.add_argument(
        "-n", "--chunk", dest="chunk_size", type=int, required=False, default=500, help="Chunk size per output file",
    )

    args = parser.parse_args(argv)
    res = process_directory(input_dir=args.input_dir, output_dir=args.output_dir, chunk_size=args.chunk_size)
    print(f"[spans] written {len(res['spans_files'])} files")
    print(f"[meta ] written {len(res['meta_files'])} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
