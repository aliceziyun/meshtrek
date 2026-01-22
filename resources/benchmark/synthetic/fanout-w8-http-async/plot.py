import re
import matplotlib.pyplot as plt

# Branch factors and istio modes
branches = [1, 2, 4, 8]
istio_modes = ["false", "true"]

# Adjust filename rule if needed
def file_name(branch, istio_mode):
    return f"results/branch{branch}-yamls-istio-{istio_mode}.log"

def parse_p50_latency(path):
    """Parse p50 latency (in ms) from a wrk output file."""
    with open(path, "r") as f:
        for line in f:
            if line.strip().startswith("50.000%"):
                parts = line.split()
                if len(parts) >= 2:
                    return float(parts[1].replace("ms", ""))
    raise ValueError(f"Could not find p50 line in {path}")

# Collect data
p50_data = {mode: [] for mode in istio_modes}

for b in branches:
    for mode in istio_modes:
        fname = file_name(b, mode)
        p50 = parse_p50_latency(fname)
        p50_data[mode].append(p50)
        print(f"Branch {b}, istio={mode}: p50 = {p50} ms")

# Plot
x = range(len(branches))
width = 0.35

fig, ax = plt.subplots(figsize=(8, 4))

bar_false = [i - width/2 for i in x]
bar_true  = [i + width/2 for i in x]

# Draw bars
ax.bar(bar_false, p50_data["false"], width, label="w/o Istio")
ax.bar(bar_true,  p50_data["true"],  width, label="w/ Istio")

# --- Add annotations ---
y_max = max(p50_data["false"] + p50_data["true"])
offset = y_max * 0.01  # small vertical offset

for i in range(len(branches)):
    base = p50_data["false"][i]
    istio = p50_data["true"][i]

    # Label for w/o istio bar → raw latency
    ax.text(
        bar_false[i],
        base + offset,
        f"{base:.2f} ms",
        ha="center",
        va="bottom",
        fontsize=8,
    )

    # Label for w/ istio bar → absolute overhead
    overhead = istio - base
    ax.text(
        bar_true[i],
        istio + offset,
        f"+{overhead:.2f} ms",
        ha="center",
        va="bottom",
        fontsize=8,
    )

ax.set_xticks(list(x))
ax.set_xticklabels([f"branch {b}" for b in branches])
ax.set_ylabel("p50 latency (ms)")
ax.legend()

plt.tight_layout()
plt.savefig("fanout-branch-p50-latency.png", dpi=300)
