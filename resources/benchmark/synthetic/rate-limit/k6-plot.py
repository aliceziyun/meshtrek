#!/usr/bin/env python3
import json
import argparse
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt


def parse_time(ts: str) -> float:
    """
    Parse RFC3339 timestamp with timezone offset, e.g.
    2026-01-04T07:25:34.521823486-07:00
    Returns POSIX seconds (float).
    """
    # Python's fromisoformat can't parse nanosecond precision; trim to microseconds if needed.
    # Split fractional seconds and timezone part safely.
    # Example: "2026-01-04T07:25:34.521823486-07:00"
    if "T" not in ts:
        raise ValueError(f"Bad timestamp: {ts}")

    # If there's a fractional part longer than 6 digits, trim to 6 for fromisoformat.
    # Keep timezone offset.
    if "." in ts:
        main, rest = ts.split(".", 1)
        # rest contains: fractional + timezone, e.g. "521823486-07:00"
        # find start of timezone sign (+/-) after fraction
        tz_pos = None
        for i, ch in enumerate(rest):
            if ch in "+-":
                tz_pos = i
                break
        if tz_pos is None:
            frac = rest
            tz = ""
        else:
            frac = rest[:tz_pos]
            tz = rest[tz_pos:]
        frac = (frac[:6]).ljust(6, "0")  # microseconds
        ts2 = f"{main}.{frac}{tz}"
    else:
        ts2 = ts

    dt = datetime.fromisoformat(ts2)
    return dt.timestamp()


def is_success_status(status: str, mode: str) -> bool:
    """
    mode:
      - "2xx": treat 200-299 as success
      - "expected": use tags.expected_response=="true"
      - "all": everything counts as success (not recommended)
    """
    if mode == "all":
        return True
    if mode == "expected":
        # handled elsewhere via tag
        return True
    # default "2xx"
    try:
        code = int(status)
        return 200 <= code <= 299
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="k6 NDJSON output from: k6 run --out json=out.json ...")
    ap.add_argument("--bucket", type=float, default=1.0, help="time bucket size in seconds (default: 1)")
    ap.add_argument("--success", choices=["2xx", "expected", "all"], default="2xx",
                    help="how to count success for goodput: 2xx (default), expected, all")
    ap.add_argument("--burst-start", type=float, default=None, help="burst start time (sec, relative to first point)")
    ap.add_argument("--burst-end", type=float, default=None, help="burst end time (sec, relative to first point)")
    ap.add_argument("--auto-burst", action="store_true",
                    help="auto-detect burst window using goodput threshold; ignored if burst-start/end provided")
    ap.add_argument("--out", default="k6_burst.png", help="output PNG filename")
    ap.add_argument("--title", default=None, help="optional figure title")
    args = ap.parse_args()

    bucket = args.bucket

    # Per-bucket accumulators
    durs = {}          # b -> list[ms]
    total_reqs = {}    # b -> int
    failed_reqs = {}   # b -> int  (according to success rule)

    t0 = None
    last_rel = 0.0

    with open(args.path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Your format: top-level metric/type/data
            if obj.get("type") != "Point":
                continue

            metric = obj.get("metric")
            data = obj.get("data", {})
            t = data.get("time")
            val = data.get("value")
            tags = data.get("tags", {}) or {}

            if metric is None or t is None or val is None:
                continue

            ts = parse_time(t)
            if t0 is None:
                t0 = ts
            rel = ts - t0
            if rel > last_rel:
                last_rel = rel

            b = int(rel // bucket)

            if metric == "http_req_duration":
                # k6 duration values are in milliseconds
                durs.setdefault(b, []).append(float(val))

                # Also count success/fail from status tags if present.
                status = str(tags.get("status", ""))
                expected = str(tags.get("expected_response", "")).lower()  # "true"/"false"

                total_reqs[b] = total_reqs.get(b, 0) + 1

                if args.success == "expected":
                    # expected_response=="true" counts as success
                    if expected != "true":
                        failed_reqs[b] = failed_reqs.get(b, 0) + 1
                elif args.success == "2xx":
                    if not is_success_status(status, "2xx"):
                        failed_reqs[b] = failed_reqs.get(b, 0) + 1
                else:
                    # all success => no failures
                    pass

            elif metric == "http_reqs":
                # Many setups also emit http_reqs points; you *could* use these for counting too.
                # But using http_req_duration is robust and already tied to status tags.
                pass

    if t0 is None:
        raise SystemExit("No Point records found. Confirm you used: k6 run --out json=out.json ...")

    # Build time axis
    max_b = int(last_rel // bucket)
    ts = np.arange(0, max_b + 1) * bucket

    p50 = np.full(len(ts), np.nan)
    p99 = np.full(len(ts), np.nan)
    goodput = np.zeros(len(ts), dtype=float)

    for i, tsec in enumerate(ts):
        b = int(tsec // bucket)
        arr = durs.get(b, [])
        if arr:
            # numpy quantile on list -> percentiles per bucket
            p50[i] = float(np.quantile(arr, 0.50))
            p99[i] = float(np.quantile(arr, 0.99))

        tot = total_reqs.get(b, 0)
        fail = failed_reqs.get(b, 0)
        succ = max(0, tot - fail)
        goodput[i] = succ / bucket

    # Burst shading selection
    burst_start = args.burst_start
    burst_end = args.burst_end
    if burst_start is None or burst_end is None:
        if args.auto_burst:
            finite = goodput[np.isfinite(goodput)]
            if finite.size >= 10:
                baseline = np.median(finite[: max(1, int(0.2 * finite.size))])
                thresh = baseline * 1.3
                mask = goodput > thresh
                if np.any(mask):
                    idx = np.where(mask)[0]
                    burst_start = ts[idx[0]]
                    burst_end = ts[idx[-1]] + bucket

    # Plot (like your example)
    fig, (ax_lat, ax_tp) = plt.subplots(
        2, 1, figsize=(7.2, 5.2), sharex=True,
        gridspec_kw={"height_ratios": [1, 1]}
    )

    if burst_start is not None and burst_end is not None:
        ax_lat.axvspan(burst_start, burst_end, alpha=0.15)
        ax_tp.axvspan(burst_start, burst_end, alpha=0.15)

    ax_lat.plot(ts, p50, label="p50")
    ax_lat.plot(ts, p99, label="p99")
    ax_lat.set_yscale("log")
    ax_lat.set_ylabel("Latencies (ms)")
    ax_lat.grid(True, which="both", linestyle="--", alpha=0.4)
    ax_lat.legend(loc="best", fontsize=9)

    ax_tp.fill_between(ts, goodput, step="pre", alpha=0.25)
    ax_tp.plot(ts, goodput, label="goodput")
    ax_tp.set_ylabel("Throughput (RPS)")
    ax_tp.set_xlabel("Time (second)")
    ax_tp.grid(True, linestyle="--", alpha=0.4)
    ax_tp.legend(loc="best", fontsize=9)

    if args.title:
        fig.suptitle(args.title)

    plt.tight_layout()
    plt.savefig(args.out, dpi=300)
    print(f"Saved: {args.out}")
    if burst_start is not None and burst_end is not None:
        print(f"Burst shading: [{burst_start:.1f}, {burst_end:.1f}] sec")
    else:
        print("Burst shading: none (use --burst-start/--burst-end or --auto-burst)")
    print(f"Goodput success mode: {args.success}")


if __name__ == "__main__":
    main()

