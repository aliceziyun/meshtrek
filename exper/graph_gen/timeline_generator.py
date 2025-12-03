import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
from collections import defaultdict
import matplotlib.colors as mcolors

import argparse
import os
import re

base_colors = ["#4caf50", "#2196f3","#ccc8c8", "#d8e91e", "#ff9800","#d8e91e", "#f44336", "#00bcd4"]

def get_events_with_x_request_id(target_x_request_id, data_dir):
    process_timelines = defaultdict(list)
    # traverse all files in the data_dir
    for root, dirs, files in os.walk(data_dir):
        for i, file in enumerate(files):
            if file.endswith(".log"):
                data_file = os.path.join(root, file)
                service_name_re = re.match(r"trace_output_([^-]+)-", file)
                service_name = service_name_re.group(1) if service_name_re else "unknown"
                with open(data_file) as f:
                    for lines in f:
                        if target_x_request_id in lines:
                            parts = lines.strip().split(", ")
                            data = {}
                            for p in parts:
                                key, val = p.split(": ", 1)
                                key = key.strip('"{}')
                                val = val.strip('"{}')
                                data[key] = val

                            print(data)

                            pid = i
                            http_start = int(data["Time HTTP Start"])
                            request_filter_start = int(data["Time Request Filter Start"])
                            filter_end = int(data["Time Process Start"])
                            write_start = int(data["Write Start Time"])
                            process_start = int(data["Write End Time"])
                            read_start = int(data["Read Start Time"])
                            read_end = int(data["Read End Time"])
                            upstream_http_start = int(data["Response Parse Start"])
                            response_filter_start = int(data["Time Response Filter Start"])
                            end = int(data["Time End"])

                            process_timelines[pid].append({
                                "service_name" : service_name, 
                                "http_start": http_start,
                                "request_filter_start": request_filter_start,
                                "filter_end": filter_end,
                                "write_start": write_start,
                                "process_start": process_start,
                                "read_start": read_start,
                                "read_end": read_end,
                                "upstream_http_start": upstream_http_start,
                                "response_filter_start": response_filter_start,
                                "end": end
                            })
    
    # sort events by start time
    for pid, events in process_timelines.items():
        events.sort(key=lambda x: x["http_start"])
    
    all_events = []
    for pid, events in process_timelines.items():
        for evt in events:
            all_events.append({
                "pid": pid,
                "service_name": evt["service_name"],
                "http_start": evt["http_start"],
                "request_filter_start": evt["request_filter_start"],
                "filter_end": evt["filter_end"],
                "write_start": evt["write_start"],
                "process_start": evt["process_start"],
                "read_start": evt["read_start"],
                "read_end": evt["read_end"],
                "upstream_http_start": evt["upstream_http_start"],
                "response_filter_start": evt["response_filter_start"],
                "end": evt["end"]
            })

    all_events.sort(key=lambda x: x["http_start"])
    all_events.reverse()

    return all_events, process_timelines

def generate_timeline_graph(all_events, process_timelines, target_x_request_id):
    fig = plt.figure(figsize=(12, 20))
    gs = gridspec.GridSpec(2, 1, height_ratios=[3, 1])
    ax = plt.subplot(gs[0])

    t_start = all_events[-1]["http_start"] if all_events else 0
    for i, evt in enumerate(all_events):
        t = [
            evt["http_start"], 
            evt["request_filter_start"], 
            evt["filter_end"],
            evt["write_start"],
            evt["process_start"], 
            evt["read_start"],
            evt["upstream_http_start"], 
            evt["response_filter_start"], 
            evt["end"]
        ]
        pid = evt['pid']

        y = i

        t_rel = [ti - t_start for ti in t]

        for j in range(len(t) - 1):
            color = base_colors[j]
            elapsed = t_rel[j+1] - t_rel[j]
            if elapsed < 0:
                print(f"[!] Negative elapsed time detected in {j}.")
                exit(1)
            ax.barh(y, elapsed/1e6, left=t_rel[j]/1e6, color=color, height=0.3)

    ax.set_yticks(range(len(all_events)))
    ax.set_yticklabels([f"{evt['service_name']}" for evt in all_events])
    ax.set_xlabel("Time (ms)")
    ax.set_title(f"Timeline for X-Request-ID {target_x_request_id}")

    ax_table = plt.subplot(gs[1])
    ax_table.axis("off")

    # table_header = ["Service", "DownStream Http Parsing", "Request Filters", "Process Time", "Upstream Http Parsing", "Response Filters", "Overhead Ratio"]
    table_header = ["Service", "DownStream Http Parsing", "Request Filters", "Socket Waiting", "Write", "Process Time", "Read", "Upstream Http Parsing", "Response Filters"]
    table_data = []

    legend_labels = table_header[1:]
    legend_colors = base_colors[:len(legend_labels)] 
    legend_patches = [mpatches.Patch(color=color, label=label) for color, label in zip(legend_colors, legend_labels)]
    ax.legend(handles=legend_patches, loc="upper right")

    for pid, events in process_timelines.items():
        for evt in events:
            t = [
                evt["http_start"], 
                evt["request_filter_start"],  
                evt["filter_end"],
                evt["write_start"], 
                evt["process_start"], 
                evt["read_start"], 
                evt["upstream_http_start"], 
                evt["response_filter_start"], 
                evt["end"]
            ]
            time_intervals = [(t[i+1] - t[i]) / 1e6 for i in range(len(t) - 1)]
            # other_time = time_intervals[0] + time_intervals[1] + time_intervals[3] + time_intervals[4] + time_intervals[5]
            # overhead_ratio =  other_time / time_intervals[2] if time_intervals[2] > 0 else 0
            table_data.append([
                str(evt['service_name']),
                f"{time_intervals[0]:.2f} ms",
                f"{time_intervals[1]:.2f} ms",
                f"{time_intervals[2]:.2f} ms",
                f"{time_intervals[3]:.2f} ms",
                f"{time_intervals[4]:.2f} ms",
                f"{time_intervals[5]:.2f} ms",
                f"{time_intervals[6]:.2f} ms",
                f"{time_intervals[7]:.2f} ms",
                f"{time_intervals[8]:.2f} ms",
                # f"{overhead_ratio:.2%}"
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
    target_x_request_id = "4ba79e3ece66ba8a"
    data_dir = args.data_dir
    
    all_events, time_lines = get_events_with_x_request_id(target_x_request_id, data_dir)

    max_pid = max(pid for pid in time_lines.keys())
    pid_list = sorted(set(evt['pid'] for evt in all_events))
    pid_to_idx = {pid: i for i, pid in enumerate(pid_list)}
    max_idx = len(pid_list) - 1 if pid_list else 1

    generate_timeline_graph(all_events, time_lines, target_x_request_id) 