import os
import json
import math
from typing import List, Dict, Any


def _list_meta_files(meta_dir: str) -> List[str]:
    """List formatted span meta json files in a directory."""
    try:
        names = os.listdir(meta_dir)
    except FileNotFoundError:
        return []
    files = [
        os.path.join(meta_dir, n)
        for n in names
        if n.startswith("formatted_spans_meta_") and n.endswith(".json")
    ]
    return sorted(files)


def _load_filtered_request_times(file_path: str, length: int) -> List[float]:
    """Load request_time values from a single meta file filtered by total_sub_requests==length."""
    with open(file_path, "r") as f:
        data = json.load(f)
    times: List[float] = []
    for _req_id, meta in data.items():
        try:
            total_len = int(meta.get("total_sub_requests", 0))
            if total_len == 3 or total_len == 6:
                rt = float(meta.get("request_time", 0))
                times.append(rt)
        except Exception:
            # Skip malformed entries
            continue
    return times


def _percentile_nearest_rank(sorted_vals: List[float], p: float) -> float:
    """Nearest-rank percentile (p in [0,1]). Returns 0.0 if list empty."""
    if not sorted_vals:
        return 0.0
    if p <= 0:
        return sorted_vals[0]
    if p >= 1:
        return sorted_vals[-1]
    rank = max(1, math.ceil(p * len(sorted_vals)))
    return sorted_vals[rank - 1]


def compute_request_time_percentiles(meta_dir: str, length: int) -> Dict[str, Any]:
    """
    Read all formatted_spans_meta_*.json files under meta_dir, collect request_time where
    total_sub_requests == length, and compute p50 and p99.

    Returns dict with keys: count, p50, p99, times (sorted list).
    """
    meta_files = _list_meta_files(meta_dir)
    all_times: List[float] = []
    for fp in meta_files:
        all_times.extend(_load_filtered_request_times(fp, length))
    all_times.sort()

    # p50: use median for more stable central tendency
    if all_times:
        mid = len(all_times) // 2
        if len(all_times) % 2 == 1:
            p50 = all_times[mid]
        else:
            p50 = (all_times[mid - 1] + all_times[mid]) / 2.0
    else:
        p50 = 0.0

    p99 = _percentile_nearest_rank(all_times, 0.99)

    return {
        "count": len(all_times),
        "p50": p50,
        "p99": p99,
        "times": all_times,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Compute p50/p99 request_time from formatted span meta files."
    )
    parser.add_argument(
        "-d", "--dir", dest="meta_dir", required=True, help="Directory containing formatted_spans_meta_*.json files",
    )
    parser.add_argument(
        "-l", "--len", dest="length", type=int, required=True, help="Required total_sub_requests length to filter",
    )

    args = parser.parse_args()
    res = compute_request_time_percentiles(meta_dir=args.meta_dir, length=args.length)
    print(f"count={res['count']} p50={res['p50']:.6f} p99={res['p99']:.6f}")
