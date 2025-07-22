import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
from collections import defaultdict
import matplotlib.colors as mcolors

import argparse
import os

def adjust_color(base_color, pid):
    idx = pid_to_idx[pid]
    print(idx)
    rgb = mcolors.to_rgb(base_color)
    h, s, v = mcolors.rgb_to_hsv(rgb)

    hue_offset = (idx / max_idx) * 0.3 - 0.15
    new_h = (h + hue_offset) % 1.0

    return mcolors.hsv_to_rgb((new_h, s, v))

def get_events_with_x_request_id(target_x_request_id, data_dir):
    process_timelines = defaultdict(list)
    # traverse all files in the data_dir
    for root, dirs, files in os.walk(data_dir):
        for file in files:
            if file.endswith(".log"):
                data_file = os.path.join(root, file)
                with open(data_file) as f:
                    for lines in f:
                        if target_x_request_id in lines:
                            parts = lines.strip().split(", ")
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
    
    # sort events by start time
    for pid, events in process_timelines.items():
        events.sort(key=lambda x: x["start"])
    
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

    return all_events, process_timelines

def generate_timeline_graph(all_events, process_timelines, target_x_request_id):
    fig = plt.figure(figsize=(10, 6))
    gs = gridspec.GridSpec(2, 1, height_ratios=[3, 1])
    ax = plt.subplot(gs[0])

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

    for pid, events in process_timelines.items():
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

base_colors = ["#4caf50", "#2196f3", "#ff9800"]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate timeline for Request under service mesh.")
    parser.add_argument("-x", type=str, help="X-Request-ID to filter traces", required=True, dest="x_request_id")
    parser.add_argument("-d", type=str, help="Path to the trace data file", required=True, dest="data_dir")
    args = parser.parse_args()

    target_x_request_id = args.x_request_id
    data_dir = args.data_dir
    
    all_events, time_lines = get_events_with_x_request_id(target_x_request_id, data_dir)

    max_pid = max(pid for pid in time_lines.keys())
    pid_list = sorted(set(evt['pid'] for evt in all_events))
    pid_to_idx = {pid: i for i, pid in enumerate(pid_list)}
    max_idx = len(pid_list) - 1 if pid_list else 1

    generate_timeline_graph(all_events, time_lines, target_x_request_id)