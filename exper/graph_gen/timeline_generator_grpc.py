# only for grpc

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
from collections import defaultdict
import matplotlib.colors as mcolors

import argparse
import os
import re

base_colors = ["#4caf50", "#2196f3", "#ff9800"]

def get_events_with_x_request_id(target_x_request_id, data_dir):
    process_timelines = defaultdict(list)
    # traverse all files in the data_dir
    for root, dirs, files in os.walk(data_dir):
        for i, file in enumerate(files):
            if file.endswith(".log"):
                service_name_re = re.match(r"trace_output_([^-]+)-", file)
                service_name = service_name_re.group(1) if service_name_re else "unknown"
                data_file = os.path.join(root, file)
                with open(data_file) as f:
                    for lines in f:
                        if target_x_request_id in lines:
                            parts = lines.strip().split(", ")
                            data = {p.split(": ")[0]: p.split(": ")[1] for p in parts}

                            stream_id = int(data["Stream ID"])
                            pid = i
                            start = int(data["Time Start"])
                            request_filter_end = int(data["Time Request Filter End"])
                            upstream = int(data["Time Upstream Recorded"])
                            end = int(data["Time End"])

                            process_timelines[pid].append({
                                "service_name" : service_name, 
                                "stream_id": stream_id,
                                "start": start,
                                "filters_end": request_filter_end,
                                "upstream": upstream,
                                "end": end
                            })
    
    # sort events by start time
    for pid, events in process_timelines.items():
        events.sort(key=lambda x: x["start"])
    
    all_events = []
    for pid, events in process_timelines.items():
        for evt in events:
            all_events.append({
                "pid": pid,
                "service_name": evt["service_name"],
                "stream_id": evt["stream_id"],
                "start": evt["start"],
                "filters_end": evt["filters_end"],
                "upstream": evt["upstream"],
                "end": evt["end"]
            })

    all_events.sort(key=lambda x: x["start"])
    all_events.reverse()

    return all_events, process_timelines

def generate_timeline_graph(all_events, process_timelines, target_x_request_id):
    fig = plt.figure(figsize=(10, 6))
    gs = gridspec.GridSpec(2, 1, height_ratios=[3, 1])
    ax = plt.subplot(gs[0])

    t_start = all_events[-1]["start"] if all_events else 0
    for i, evt in enumerate(all_events):
        t = [evt["start"], evt["filters_end"], evt["upstream"], evt["end"]]
        pid = evt['pid']

        y = i

        t_rel = [ti - t_start for ti in t]

        for j in range(len(t) - 1):
            color = base_colors[j]
            ax.barh(y, (t_rel[j+1] - t_rel[j])/1e6, left=t_rel[j]/1e6, color=color, height=0.3)

    ax.set_yticks(range(len(all_events)))
    ax.set_yticklabels([f"{evt['service_name']}" for evt in all_events])
    ax.set_xlabel("Time (ms)")
    ax.set_title(f"Timeline for Uber ID {target_x_request_id}")

    ax_table = plt.subplot(gs[1])
    ax_table.axis("off")

    table_header = ["Service", "Request Filters", "Process Time", "Response Filters"]
    table_data = []

    legend_labels = table_header[1:]
    legend_colors = base_colors[:len(legend_labels)] 
    legend_patches = [mpatches.Patch(color=color, label=label) for color, label in zip(legend_colors, legend_labels)]
    ax.legend(handles=legend_patches, loc="upper right")

    for pid, events in process_timelines.items():
        for evt in events:
            t = [evt["start"], evt["filters_end"], evt["upstream"], evt["end"]]
            time_intervals = [(t[i+1] - t[i]) / 1e6 for i in range(len(t) - 1)]
            table_data.append([
                str(evt['service_name']),
                f"{time_intervals[0]:.2f} ms",
                f"{time_intervals[1]:.2f} ms",
                f"{time_intervals[2]:.2f} ms",
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate timeline for Request under service mesh.")
    # parser.add_argument("-x", type=str, help="X-Request-ID to filter traces", required=True, dest="x_request_id")
    parser.add_argument("-d", type=str, help="Path to the trace data file", required=True, dest="data_dir")
    args = parser.parse_args()

    # target_x_request_id = args.x_request_id
    # in grpc, this must be the unique identifier for the request as the x-request-id will not be forwarded automatically
    target_x_request_id = "457ba0b2-9b6f-9aae-a654-1108e98e93d5"
    data_dir = args.data_dir
    
    all_events, time_lines = get_events_with_x_request_id(target_x_request_id, data_dir)

    max_pid = max(pid for pid in time_lines.keys())
    pid_list = sorted(set(evt['pid'] for evt in all_events))
    pid_to_idx = {pid: i for i, pid in enumerate(pid_list)}
    max_idx = len(pid_list) - 1 if pid_list else 1

    generate_timeline_graph(all_events, time_lines, target_x_request_id)