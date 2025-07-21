# analyze results

import re
import numpy as np
import argparse
import os
import matplotlib.pyplot as plt

def analyze_raw_http_parse(file_path):
    '''
    analyze results look like '[parse-end] connection_id: 15, elapsed_time: 24694'
    '''

    # extract pod name from file path
    # for example trace_output_details-v1-6768f6584f-w9xx5.log, I need to extract details-v1-6768f6584f-w9xx5
    podname = file_path.split('trace_output')[-1].split('.')[0]

    output_file = "output.log"
    elapsed_times = []
    values = ...
    if not os.path.exists(file_path):
        raise FileNotFoundError(f'File not found: {file_path}')
    with open(file_path, 'r') as f:
        for line in f:
            match = re.search(r'Elapsed Time:\s*(\d+)', line)
            if match:
                if int(match.group(1)) < 6300000:
                    elapsed_times.append(int(match.group(1)))
        
        values = np.array(elapsed_times)
    
    avg = np.mean(values)
    p50 = np.percentile(values, 50)
    p99 = np.percentile(values, 99)
    with open(output_file, 'a') as f:
        f.write(f'Pod: {podname}\n')
        f.write(f'Avg: {avg}, P50: {p50}, P99: {p99}\n')
        f.write(f'Max: {np.max(values)}, Min: {np.min(values)}\n\n')

    sorted_vals = np.sort(values)
    yvals = np.arange(len(sorted_vals)) / float(len(sorted_vals))

    plt.plot(sorted_vals, yvals, label='CDF')
    plt.axvline(p50, color='orange', linestyle='--', label='P50')
    plt.axvline(p99, color='red', linestyle='--', label='P99')
    plt.title('CDF of Elapsed Time')
    plt.xlabel('Elapsed Time')
    plt.ylabel('Cumulative Probability')
    plt.legend()
    plt.grid(True)

    # Save the plot to a file
    plot_file = f'cdf_plot_{podname}.png'
    plt.savefig(plot_file)
    plt.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Analyze raw HTTP parse results.')
    parser.add_argument('-f', '--file_path', type=str)
    parser.add_argument('-d', '--dir_name', type=str)
    parser.add_argument('-t', '--type', type=str, required=True, choices=['raw_http'])
    args = parser.parse_args()

    if not args.file_path and not args.dir_name:
        raise ValueError('Either file_path or dir_name must be provided.')
    if args.file_path and args.dir_name:
        raise ValueError('Only one of file_path or dir_name should be provided.')
    
    if args.type == 'raw_http' and args.file_path:
        analyze_raw_http_parse(args.file_path)
    elif args.type == 'raw_http' and args.dir_name:
        for file in os.listdir(args.dir_name):
            if file.endswith('.log'):
                file_path = os.path.join(args.dir_name, file)
                analyze_raw_http_parse(file_path)
    else:
        raise ValueError(f'Unknown type: {args.type}')