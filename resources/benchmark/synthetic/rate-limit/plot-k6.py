#!/usr/bin/env python3
import json
import argparse
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from mpl_toolkits.axes_grid1.inset_locator import inset_axes, mark_inset

NAMES=["istio", "istio+limit", "noistio"]

def parse_time(ts: str) -> float:
    """
    Parse RFC3339 timestamp with timezone offset; trim to microseconds for datetime.fromisoformat.
    Example: 2026-01-04T07:25:34.521823486-07:00
    Returns POSIX seconds (float).
    """
    if "." in ts:
        main, rest = ts.split(".", 1)
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
        frac = (frac[:6]).ljust(6, "0")
        ts = f"{main}.{frac}{tz}"
    dt = datetime.fromisoformat(ts)
    return dt.timestamp()


def is_success(tags: dict, success_mode: str) -> bool:
    """
    success_mode:
      - "2xx": status 200-299 considered success (default)
      - "expected": tags.expected_response == "true"
      - "all": treat all as success
    """
    if success_mode == "all":
        return True
    if success_mode == "expected":
        return str(tags.get("expected_response", "")).lower() == "true"
    try:
        code = int(tags.get("status", -1))
        return 200 <= code <= 299
    except Exception:
        return False


def read_k6_ndjson_success_only(path: str, bucket_s: float, success_mode: str):
    """
    Reads k6 --out json=... NDJSON file and returns per-bucket time series:
      ts (sec from start),
      p50_ms (success-only),
      p99_ms (success-only),
      goodput_rps (success-only),
      fail_rps (non-success per sec)
    """
    durs_ok = {}    # bucket -> list[ms] for successful requests only
    succ = {}       # bucket -> count successful
    total = {}      # bucket -> count total (duration points)

    t0 = None
    last_rel = 0.0

    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            if obj.get("type") != "Point":
                continue
            if obj.get("metric") != "http_req_duration":
                continue

            data = obj.get("data", {})
            t = data.get("time")
            v = data.get("value")
            tags = data.get("tags", {}) or {}
            if t is None or v is None:
                continue

            ts_abs = parse_time(t)
            if t0 is None:
                t0 = ts_abs
            rel = ts_abs - t0
            last_rel = max(last_rel, rel)
            b = int(rel // bucket_s)

            total[b] = total.get(b, 0) + 1
            ok = is_success(tags, success_mode)
            if ok:
                succ[b] = succ.get(b, 0) + 1
                durs_ok.setdefault(b, []).append(float(v))

    if t0 is None:
        raise RuntimeError(f"No http_req_duration points found in {path}")

    max_b = int(last_rel // bucket_s)
    ts = np.arange(0, max_b + 1) * bucket_s

    p50 = np.full(len(ts), np.nan)
    p99 = np.full(len(ts), np.nan)
    goodput = np.zeros(len(ts), dtype=float)
    fail_rps = np.zeros(len(ts), dtype=float)

    for i, tsec in enumerate(ts):
        b = int(tsec // bucket_s)
        arr = durs_ok.get(b, [])
        if arr:
            p50[i] = float(np.quantile(arr, 0.50))
            p99[i] = float(np.quantile(arr, 0.99))

        s = succ.get(b, 0)
        tot = total.get(b, 0)
        fail = max(0, tot - s)

        goodput[i] = s / bucket_s
        fail_rps[i] = fail / bucket_s

    return ts, p50, p99, goodput, fail_rps


def align_to_shortest(series_dict):
    """Truncate all series to shortest length so overlays line up."""
    min_len = min(len(v[0]) for v in series_dict.values())
    for k, (ts, p50, p99, gp, fr) in series_dict.items():
        series_dict[k] = (ts[:min_len], p50[:min_len], p99[:min_len], gp[:min_len], fr[:min_len])
    return series_dict


def finite_slice(arr):
    arr = np.asarray(arr)
    return arr[np.isfinite(arr)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="k6-results-automate", help="directory containing json files")
    ap.add_argument("--bucket", type=float, default=1.0, help="time bucket size in seconds (default 1)")
    ap.add_argument("--success", choices=["2xx", "expected", "all"], default="2xx",
                    help="success definition for goodput & latency (default 2xx)")
    ap.add_argument("--burst-start", type=float, default=None, help="burst start (sec, relative)")
    ap.add_argument("--burst-end", type=float, default=None, help="burst end (sec, relative)")
    ap.add_argument("--show-fail", action="store_true", help="also plot fail_rps in bottom panel")

    # Stable-stage zoom window (you wanted 5-10 by default)
    ap.add_argument("--stable-start", type=float, default=5.0,
                    help="stable stage start time in seconds (relative). default 5")
    ap.add_argument("--stable-end", type=float, default=10.0,
                    help="stable stage end time in seconds (relative). default 10")
    ap.add_argument("--zoom-metric", choices=["p50", "p99"], default="p50",
                    help="which latency metric to show in the inset (default p50)")

    ap.add_argument("--out", default="k6_compare_success_only_zoom.pdf", help="output PDF")
    ap.add_argument("--title", default=None, help="optional figure title")
    args = ap.parse_args()

    paths = {
        "istio": f"{args.dir}/default.json",
        "istio+limit":   f"{args.dir}/limit.json",
        "noistio": f"{args.dir}/noistio.json",
    }
    colors = {
        "istio": "tab:blue",
        "istio+limit": "tab:orange",
        "noistio": "tab:green",
    }

    series = {}
    for name, path in paths.items():
        series[name] = read_k6_ndjson_success_only(path, args.bucket, args.success)
    series = align_to_shortest(series)

    fig, (ax_lat, ax_gp) = plt.subplots(
        2, 1, figsize=(8.2, 5.6), sharex=True,
        gridspec_kw={"height_ratios": [1, 1]}
    )

    # Burst shading optional
    if args.burst_start is not None and args.burst_end is not None:
        ax_lat.axvspan(args.burst_start, args.burst_end, alpha=0.15)
        ax_gp.axvspan(args.burst_start, args.burst_end, alpha=0.15)

    # Top: latency p50/p99 (success-only)
    for name in NAMES:
        ts, p50, p99, gp, fr = series[name]
        c = colors[name]
        ax_lat.plot(ts, p50, color=c, linestyle="--", label=f"{name} p50")
        ax_lat.plot(ts, p99, color=c, linestyle="-",  label=f"{name} p99")

    ax_lat.set_yscale("log")
    ax_lat.set_ylabel("Latency (ms)")
    ax_lat.grid(True, which="both", linestyle="--", alpha=0.4)

    # Put legend upper-left (as in your screenshot)
    ax_lat.legend(loc="upper left", fontsize=8, ncol=2)

    # Bottom: goodput
    for name in NAMES:
        ts, p50, p99, gp, fr = series[name]
        c = colors[name]
        # ax_gp.fill_between(ts, gp, step="pre", alpha=0.18, color=c)
        # ax_gp.plot(ts, gp, color=c, linestyle="-", label=f"{name} goodput")
        ax_gp.plot(ts, gp, color=c, linestyle="-", linewidth=2, label=f"{name} goodput")
        if args.show_fail:
            ax_gp.plot(ts, fr, color=c, linestyle=":", label=f"{name} fail_rps")

    ax_gp.set_ylabel("RPS")
    ax_gp.set_xlabel("Time (second)")
    ax_gp.grid(True, linestyle="--", alpha=0.4)
    ax_gp.legend(loc="upper left", fontsize=8, ncol=1)

    # ---- Stable-stage zoom rectangle + inset (smaller, 5-10s default, placed under legend area) ----
    stable_start = args.stable_start
    stable_end = args.stable_end
    if stable_end <= stable_start:
        raise SystemExit("--stable-end must be > --stable-start")

    # Choose which metric to zoom
    use_p50 = (args.zoom_metric == "p50")

    # Determine y-range from all configs within stable window
    ys = []
    for name in NAMES:
        ts, p50, p99, gp, fr = series[name]
        y = p50 if use_p50 else p99
        mask = (ts >= stable_start) & (ts <= stable_end)
        ys.append(finite_slice(y[mask]))
    ys = np.concatenate([a for a in ys if a.size > 0]) if any(a.size > 0 for a in ys) else np.array([])

    if ys.size > 0:
        y_min = float(np.nanmin(ys))
        y_max = float(np.nanmax(ys))
        pad = 0.10 * (y_max - y_min) if y_max > y_min else 0.10 * max(y_max, 1.0)
        y0 = max(1e-6, y_min - pad)
        y1 = y_max + pad

        # Rectangle on main plot
        rect = Rectangle(
            (stable_start, y0),
            stable_end - stable_start,
            y1 - y0,
            fill=False,
            linewidth=1.4
        )
        ax_lat.add_patch(rect)

        # Smaller inset, manually positioned under legend zone (avoid blocking right side)
        # Tune bbox_to_anchor to move it: (x0, y0, width, height) in axes fraction coords
        axins = inset_axes(
            ax_lat,
            width="28%",
            height="20%",
            bbox_to_anchor=(0.13, -0.2, 0.35, 0.7),
            bbox_transform=ax_lat.transAxes,
            loc="upper left",
            borderpad=0.6,
        )

        for name in NAMES:
            ts, p50, p99, gp, fr = series[name]
            c = colors[name]
            y = p50 if use_p50 else p99
            mask = (ts >= stable_start) & (ts <= stable_end)
            axins.plot(ts[mask], y[mask], color=c, linestyle="-", label=name)

        axins.set_xlim(stable_start, stable_end)
        axins.set_ylim(y0, y1)
        axins.grid(True, linestyle="--", alpha=0.35)
        axins.set_title(f"Zoom: {args.zoom_metric}", fontsize=8)
        axins.tick_params(labelsize=7)

        # Optional: connectors. Comment out if you prefer cleaner camera-ready style.
        mark_inset(ax_lat, axins, loc1=2, loc2=4, fc="none", ec="0.35", lw=1.0)

    if args.title:
        fig.suptitle(args.title)

    plt.tight_layout()
    plt.savefig(args.out, dpi=300, bbox_inches="tight")
    print(f"Saved: {args.out}")
    print(f"Latency percentiles computed over SUCCESS-ONLY requests ({args.success}).")
    print(f"Stable zoom window: [{stable_start}, {stable_end}] sec; zoom metric={args.zoom_metric}")


if __name__ == "__main__":
    main()