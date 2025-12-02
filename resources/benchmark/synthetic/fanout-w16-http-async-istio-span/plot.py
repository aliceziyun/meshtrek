import re
import matplotlib.pyplot as plt
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Branch factors and istio modes
branches = [16,8,4,2,1]
istio_modes = ["false", "true"]

# Adjust filename rule if needed
def file_name(branch, istio_mode):
    return f"results-done/branch{branch}-yamls-istio-{istio_mode}.log"

def throughput_file_name(branch, istio_mode):
    # As you described: same as .log but with ".throughput" suffix
    return file_name(branch, istio_mode) + ".throughput"

def parse_p50_latency(path):
    """Parse p50 latency (in ms) from a wrk output file."""
    with open(path, "r") as f:
        for line in f:
            # Match lines like: "50%  138.07ms" or "50.000% ..."
            stripped = line.strip()
            if stripped.startswith("50.000%") or stripped.startswith("50%"):
                parts = stripped.split()
                # Usually: ["50.000%", "138.07ms"] or ["50%", "138.07ms"]
                if len(parts) >= 2:
                    return float(parts[1].replace("ms", ""))
    raise ValueError(f"Could not find p50 line in {path}")

def parse_throughput(path):
    """Parse throughput (Requests/sec) from a wrk throughput output file."""
    with open(path, "r") as f:
        for line in f:
            stripped = line.strip()
            # Line looks like: "Requests/sec:    897.53"
            if stripped.startswith("Requests/sec:"):
                parts = stripped.split()
                # e.g. ["Requests/sec:", "897.53"]
                for p in parts:
                    # Find the first token that can be parsed as float
                    try:
                        return float(p)
                    except ValueError:
                        continue
    raise ValueError(f"Could not find Requests/sec line in {path}")

# Collect data
p50_data = {mode: [] for mode in istio_modes}
throughput_data = {mode: [] for mode in istio_modes}

for b in branches:
    for mode in istio_modes:
        # Latency
        fname = file_name(b, mode)
        p50 = parse_p50_latency(fname)
        p50_data[mode].append(p50)

        # Throughput
        tname = throughput_file_name(b, mode)
        thr = parse_throughput(tname)
        throughput_data[mode].append(thr)

        print(f"Branch {b}, istio={mode}: p50 = {p50:.2f} ms, throughput = {thr:.2f} req/s")

# Plot
x = range(len(branches))
width = 0.35

fig, (ax_lat, ax_thr) = plt.subplots(1, 2, figsize=(10, 4))

bar_false = [i - width/2 for i in x]
bar_true  = [i + width/2 for i in x]

# -------------------- Latency subplot --------------------
ax_lat.bar(bar_false, p50_data["false"], width, label="w/o Istio")
ax_lat.bar(bar_true,  p50_data["true"],  width, label="w/ Istio")

# Annotations for latency
y_max_lat = max(p50_data["false"] + p50_data["true"])
offset_lat = y_max_lat * 0.01  # small vertical offset

for i in range(len(branches)):
    base = p50_data["false"][i]
    istio = p50_data["true"][i]

    # Label for w/o istio bar → raw latency
    ax_lat.text(
        bar_false[i],
        base + offset_lat,
        f"{base:.2f} ms",
        ha="center",
        va="bottom",
        fontsize=8,
    )

    # Label for w/ istio bar → absolute overhead (latency increase)
    overhead = istio - base
    ax_lat.text(
        bar_true[i],
        istio + offset_lat,
        f"+{overhead:.2f} ms",
        ha="center",
        va="bottom",
        fontsize=8,
    )

ax_lat.set_xticks(list(x))
ax_lat.set_xticklabels([f"branch {b}" for b in branches])
ax_lat.set_ylabel("p50 latency (ms)")
ax_lat.set_title("p50 Latency")
ax_lat.legend()

# -------------------- Throughput subplot --------------------
ax_thr.bar(bar_false, throughput_data["false"], width, label="w/o Istio")
ax_thr.bar(bar_true,  throughput_data["true"],  width, label="w/ Istio")

# Annotations for throughput (you can comment this block out if too busy)
y_max_thr = max(throughput_data["false"] + throughput_data["true"])
offset_thr = y_max_thr * 0.01

for i in range(len(branches)):
    base = throughput_data["false"][i]
    istio = throughput_data["true"][i]

    # Raw throughput on w/o Istio bar
    ax_thr.text(
        bar_false[i],
        base + offset_thr,
        f"{base:.1f}",
        ha="center",
        va="bottom",
        fontsize=8,
    )

    # Delta throughput on w/ Istio bar
    delta_thr = istio - base
    ax_thr.text(
        bar_true[i],
        istio + offset_thr,
        f"{delta_thr:+.1f}",
        ha="center",
        va="bottom",
        fontsize=8,
    )

ax_thr.set_xticks(list(x))
ax_thr.set_xticklabels([f"branch {b}" for b in branches])
ax_thr.set_ylabel("Throughput (Requests/sec)")
ax_thr.set_title("Throughput")
ax_thr.legend()

plt.tight_layout()
plt.savefig("fanout-branch-latency-throughput.png", dpi=300)
