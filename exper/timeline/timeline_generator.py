import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
from collections import defaultdict
import matplotlib.colors as mcolors

target_x_request_id = "951139ad-b319-92d4-b646-deadba7ce8b8"
data_file = "/Users/alicesong/Desktop/research/meshtrek/res/trace/trace_absolute/trace_output_productpage-v1-65d7d4fdd8-qhx9t.log"

def adjust_color(base_color, pid):
    idx = pid_to_idx[pid]
    print(idx)
    rgb = mcolors.to_rgb(base_color)
    h, s, v = mcolors.rgb_to_hsv(rgb)

    hue_offset = (idx / max_idx) * 0.3 - 0.15
    new_h = (h + hue_offset) % 1.0

    return mcolors.hsv_to_rgb((new_h, s, v))

process_timelines = defaultdict(list)

with open(data_file) as f:
    for line in f:
        if target_x_request_id in line:
            parts = line.strip().split(", ")
            data = {p.split(": ")[0]: p.split(": ")[1] for p in parts}

            conn_id = int(data["Connection ID"])
            pid = int(data["Process ID"])
            start = int(data["Time Start"])
            decode = int(data["Time Decode Header"])
            upstream = int(data["Time Upstream Recorded"])
            end = int(data["Time End"])

            process_timelines[pid].append({
                "conn_id": conn_id,
                "start": start,
                "decode": decode,
                "upstream": upstream,
                "end": end
            })

max_pid = max(pid for pid in process_timelines.keys())
base_colors = ["#4caf50", "#2196f3", "#ff9800"]

fig = plt.figure(figsize=(10, 6))
gs = gridspec.GridSpec(2, 1, height_ratios=[3, 1])
ax = plt.subplot(gs[0])

all_events = []
for pid, events in sorted(process_timelines.items()):
    for evt in events:
        all_events.append({
            "pid": pid,
            "conn_id": evt["conn_id"],
            "start": evt["start"],
            "decode": evt["decode"],
            "upstream": evt["upstream"],
            "end": evt["end"]
        })

pid_list = sorted(set(evt['pid'] for evt in all_events))
pid_to_idx = {pid: i for i, pid in enumerate(pid_list)}
max_idx = len(pid_list) - 1 if pid_list else 1

print(pid_to_idx)

for i, evt in enumerate(all_events):
    s, d, u, e = evt["start"], evt["decode"], evt["upstream"], evt["end"]
    pid = evt['pid']

    y = i
    c1 = adjust_color(base_colors[0], pid)
    c2 = adjust_color(base_colors[1], pid)
    c3 = adjust_color(base_colors[2], pid)

    ax.barh(y, (d-s)/1e6, left=s/1e6, color=c1, height=0.3)
    ax.barh(y, (u-d)/1e6, left=d/1e6, color=c2, height=0.3)
    ax.barh(y, (e-u)/1e6, left=u/1e6, color=c3, height=0.3)

ax.set_yticks(range(len(all_events)))
ax.set_yticklabels([f"Conn {evt['conn_id']}" for evt in all_events])
ax.set_xlabel("Time (ms)")
ax.set_title(f"Timeline for X-Request-ID {target_x_request_id}")

ax_table = plt.subplot(gs[1])
ax_table.axis("off")

table_header = ["ConnID", "PID", "Start→Decode", "Decode→Upstream", "Upstream→End"]
table_data = []

for pid, events in sorted(process_timelines.items()):
    for evt in events:
        s, d, u, e = evt["start"], evt["decode"], evt["upstream"], evt["end"]
        t1 = (d - s)/1e6
        t2 = (u - d)/1e6
        t3 = (e - u)/1e6
        table_data.append([
            str(evt['conn_id']),
            str(pid),
            f"{t1:.1f}ms",
            f"{t2:.1f}ms",
            f"{t3:.1f}ms"
        ])

the_table = ax_table.table(cellText=table_data,
                           colLabels=table_header,
                           loc='center',
                           cellLoc='center')

the_table.auto_set_font_size(False)
the_table.set_fontsize(9)
the_table.scale(1, 1.5)

plt.tight_layout()
plt.show()