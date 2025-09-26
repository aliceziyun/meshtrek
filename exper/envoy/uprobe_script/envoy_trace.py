#!/usr/bin/python3

from bcc import BPF
import ctypes
import subprocess

import argparse
import json
import queue, threading

from http_uprobe import HttpUprobe

global log_queue

def find_envoy_pid(type):
    cmd = ...
    if type == "cilium":
        cmd = "ps aux | grep '/usr/bin/cilium-envoy -c /var/run/cilium/envoy/bootstrap-config.json --base-id 0' | grep -v grep"
    elif type == "istio":
        cmd = "ps aux | grep '/usr/local/bin/envoy' | grep -v grep"
    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, text=True)

    for line in result.stdout.strip().split('\n'):
        if not line:
            continue
        parts = line.split()
        pid = int(parts[1])
        return pid
    
    raise RuntimeError("Envoy process not found")

def callback(cpu, data, size):
    class ConnInfo(ctypes.Structure):
        _fields_ = [
            ("x_request_id", ctypes.c_char * 17),
            ("tmp_stream_id", ctypes.c_uint),
            ("upstream_id", ctypes.c_ulonglong),
            ("time_start", ctypes.c_ulonglong),
            ("time_request_filter_start", ctypes.c_ulonglong),
            ("time_process_start", ctypes.c_ulonglong),
            ("time_response_filter_start", ctypes.c_ulonglong),
            ("time_end", ctypes.c_ulonglong),
            ("response_parse_start", ctypes.c_ulonglong),
            ("response_parse_end", ctypes.c_ulonglong),
        ]
    event = ctypes.cast(data, ctypes.POINTER(ConnInfo)).contents
    x_request_id_str = event.x_request_id.split(b'\x00', 1)[0].decode(errors="replace")
    log_data = {
        "Connection ID": event.connection_id,
        "X-Request-ID": x_request_id_str,
        "Time Start": event.time_start,
        "Time Request Filter Start": event.time_request_filter_start,
        "Time Process Start": event.time_process_start,
        "Time Response Filter Start": event.time_response_filter_start,
        "Response Parse Start": event.response_parse_start,
        "Response Parse End": event.response_parse_end,
    }
    log_queue.put(json.dump(log_data))

def start_trace(type):
    binary_path = ...
    uprobe = ...

    uprobe = HttpUprobe()
    b = BPF(text=uprobe.program)

    # start working thread to collect logs
    output_file = "/tmp/trace_output.log"
    log_queue = queue.Queue()
    def log_worker():
        with open(output_file, "a") as f:
            while True:
                try:
                    line = log_queue.get(timeout=1)
                    f.write(line)
                    f.flush()
                except queue.Empty:
                    continue
    threading.Thread(target=log_worker, daemon=True).start()

    # attach uprobes
    if type == "cilium":
        binary_path = "/usr/bin/cilium-envoy"
    elif type == "istio":
        binary_path = "/usr/local/bin/envoy"
    else:
        print("Unknown type")
        return
    
    target_pid = find_envoy_pid(type)
    for i, symbol in enumerate(uprobe.hook_symbol_list):
        b.attach_uprobe(sym=symbol, fn_name=uprobe.hook_function_list[i], name=binary_path, pid=target_pid)

    # register call backs
    b["trace_events"].open_perf_buffer(callback, page_cnt=256)

    print("Tracing... Ctrl+C to stop.")
    try:
        while True:
            b.perf_buffer_poll(timeout=5)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Envoy HTTP/2 Tracing")
    parser.add_argument("-t", "--type", type=str, choices=["cilium", "istio"], required=True)
    start_trace(parser.t, parser.http)