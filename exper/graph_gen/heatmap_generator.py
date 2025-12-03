import os
import argparse
import matplotlib.pyplot as plt
# import seaborn as sns
import numpy as np
from collections import defaultdict
# from scipy.stats import gaussian_kde

result_file = "heatmap_results.txt"
target_entry_size = [11]

def get_entry(line):
    parts = line.strip().split(", ")
    data = {p.split(": ")[0]: p.split(": ")[1] for p in parts}
    data = {k.strip('"{}'): v.strip('"{}') for k, v in data.items()}
    # print(data)

    x_request_id = data['X-Request-ID']

    if len(x_request_id) == 0:
        return None, None

    start = int(data['Time HTTP Start'])
    # http_parsed = int(data["Time HTTP Parsed"])
    # filter_end = int(data["Time Request Filter End"])
    # upstream_time_start = int(data["Time Upstream Recorded"])
    # upstream_http_parsed = int(data["Upstream Time HTTP Parsed"])
    # upstream = int(data["Upstream Time Recorded"])
    end = int(data['Time End'])

    # entry = {
    #     "x_request_id": x_request_id,
    #     "start": start,
    #     "http_parsed": http_parsed,
    #     "filters_end": filter_end,
    #     "upstream_start": upstream_time_start,
    #     "upstream_http_parsed": upstream_http_parsed,
    #     "upstream": upstream,
    #     "end": end
    # }

    entry = {
        "x_request_id": x_request_id,
        "start": start,
        # "process_start": filter_end,
        # "process_end": upstream_time_start,
        "end": end
    }

    return x_request_id, entry

def find_all_entries_with_x_request_id(target_x_request_id, directory, entry_lines, entry_file):
    if entry_lines is None:
        entry_file = os.path.join(directory, entry_file)
        with open(entry_file, 'r') as ef:
            entry_lines = ef.readlines()

    request_entries = []
    for line in entry_lines[:]:
        if target_x_request_id in line:
            _, entry = get_entry(line)
            request_entries.append(entry)
    
    # then find in other files in the directory
    for root, dirs, files in os.walk(directory):
        for i, file in enumerate(files):
            # do not read the entry file again
            if entry_file and file == os.path.basename(entry_file):
                continue
            if file.endswith(".log"):
                data_file = os.path.join(root, file)
                with open(data_file) as f:
                    lines = f.readlines()
                    for line in lines:
                        if target_x_request_id in line:
                            _, entry = get_entry(line)
                            request_entries.append(entry)

    request_entries.sort(key=lambda x: x["start"])

    return request_entries

def merge_requests(request_entries):
    if len(request_entries) == 0 or len(request_entries) == 1:
        return request_entries
    
    current_request = request_entries[0]
    merged_requests = []
    for entry in request_entries[1:]:
        # compare the process start time to find nested requests
        # WARNING: now the program will not handle the parallel requests, all serial
        merged = False
        # if entry["process_start"] >= current_request["process_start"] and entry["process_end"] <= current_request["process_end"]:
        #     # whether it can be merged
        #     if (entry["start"] > current_request["start"] and entry["start"] < current_request["process_start"]):
        #         current_request["process_start"] = entry["process_start"]
        #         merged = True
        #     if entry["end"] > current_request["process_end"] and entry["end"] < current_request["end"]:
        #         current_request["process_end"] = entry["process_end"]
        #         merged = True
        
        if merged == False:
            current_request = entry
            merged_requests.append(current_request)

    merged_requests.append(current_request)
    return merged_requests     

def generator_dot_file(directory, entry_file):
    # read entry file
    entry_file = os.path.join(directory, entry_file)
    with open(entry_file, 'r') as ef:
        entry_lines = ef.readlines()

    # discard the first 10% lines and last 10% lines
    discard_num = int(len(entry_lines) * 0.1)
    entry_lines = entry_lines[discard_num: -discard_num]

    # already processed x_request_id
    processed_x_request_ids = set()

    while entry_lines:
        request_entries = []

        line = entry_lines.pop(0)  # Use current first line
        x_request_id, entry = get_entry(line)
        if x_request_id is None:
            continue
        if x_request_id in processed_x_request_ids:
            continue

        processed_x_request_ids.add(x_request_id)

        request_entries.append(entry)
        target_x_request_id = x_request_id[0:16]

        # find all entries with the same x_request_id
        request_entries.extend(find_all_entries_with_x_request_id(target_x_request_id, directory, entry_lines, entry_file))
        if len(request_entries) not in target_entry_size:       # discard requests which may not be complete
            continue

        # merge nested requests
        merged_requests = merge_requests(request_entries)

        # calculate the [total_time, overhead]
        total_time = merged_requests[0]["end"] - merged_requests[0]["start"]
        overhead = 0
        # for req in merged_requests:
        #     overhead += (req["process_start"] - req["start"])
        #     overhead += (req["end"] - req["process_end"])
        
        result_file_path = os.path.join(os.getcwd(), result_file)
        with open(result_file_path, 'a') as rf:
            # print(f"Writing result for X-Request-ID: {target_x_request_id}, Total Time: {total_time}, Overhead: {overhead}")
            rf.write(f"{target_x_request_id}, {total_time}, {overhead}\n")

def generate_heatmap_graph():
    result_file_path = os.path.join(os.getcwd(), result_file)
    if not os.path.exists(result_file_path):
        print(f"Result file {result_file_path} does not exist.")
        return
    
    with open(result_file_path, 'r') as rf:
        lines = rf.readlines()
        _, total_times, overheads = zip(*(line.strip().split(", ") for line in lines))
        total_times = list(map(int, total_times))
        overheads = list(map(int, overheads))

        # divide by 1e6 to convert to milliseconds
        total_times = np.array([t / 1e6 for t in total_times])
        overheads = np.array([o / 1e6 for o in overheads])

        # sample 30% of the data if too large
        if len(total_times) > 5000:
            sample_indices = np.random.choice(len(total_times), size=int(len(total_times) * 0.3), replace=False)
            total_times = total_times[sample_indices]
            overheads = overheads[sample_indices]

        xy = np.vstack([total_times, overheads])
        z = gaussian_kde(xy)(xy)

        idx = z.argsort()
        x, y, z = total_times[idx], overheads[idx], z[idx]

        plt.figure(figsize=(10, 5))
        plt.title("Request Time vs Service Mesh Overhead Distribution")
        plt.xlabel("Total Request Time (ms)")
        plt.ylabel("Overhead Time (ms)")
        plt.scatter(x, y, c=z, s=20, cmap='Spectral')
        plt.colorbar(label='Density')

        plt.show()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Heatmap Generator")
    parser.add_argument("-d", type=str, dest="dir", required=True, help="Directory containing log files")
    parser.add_argument("-e", type=str, dest="entry_file", help="Entry log file name (default: entry.log)")
    args = parser.parse_args()

    generator_dot_file(args.dir, args.entry_file)
    # generate_heatmap_graph()