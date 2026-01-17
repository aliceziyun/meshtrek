#!/usr/bin/python3

from bcc import BPF
import ctypes
import subprocess

import argparse
import json
import queue, threading

from stream_uprobe import StreamUprobe
from conn_uprobe import ConnUprobe

from http1_uprobe import Http1Uprobe

log_queue = queue.Queue()

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

def http2_conn_callback(cpu, data, size):
    class ConnInfo(ctypes.Structure):
        _fields_ = [
            ("connection_id", ctypes.c_uint),
            ("position", ctypes.c_uint),
            ("stream_id", ctypes.c_ulonglong),
            ("write_ready_start_time", ctypes.c_ulonglong),
            ("read_ready_start_time", ctypes.c_ulonglong),
            ("parse_start_time", ctypes.c_ulonglong),
            ("parse_end_time", ctypes.c_ulonglong),
        ]
    conn_info = ctypes.cast(data, ctypes.POINTER(ConnInfo)).contents
    log_data = {
        "Connection ID": conn_info.connection_id,
        "Stream IDs": conn_info.stream_id,
        "Write Ready Start Time": conn_info.write_ready_start_time,
        "Read Ready Start Time": conn_info.read_ready_start_time,
        "Parse Start Time": conn_info.parse_start_time,
        "Parse End Time": conn_info.parse_end_time,
    }
    log_queue.put(json.dumps(log_data))

def http2_stream_callback(cpu, data, size):
    class StreamInfo(ctypes.Structure):
        _fields_ = [
            ("key", ctypes.c_ulonglong),
            ("request_id", ctypes.c_char * 32),
            ("upstream_conn_id", ctypes.c_uint),
            ("stream_id", ctypes.c_ulonglong),
            ("header_parse_start_time", ctypes.c_ulonglong),
            ("header_parse_end_time", ctypes.c_ulonglong),
            ("data_parse_start_time", ctypes.c_ulonglong),
            ("data_parse_end_time", ctypes.c_ulonglong),
            ("trailer_parse_start_time", ctypes.c_ulonglong),
            ("trailer_parse_end_time", ctypes.c_ulonglong),
            ("stream_end_time", ctypes.c_ulonglong),
        ]
    stream_info = ctypes.cast(data, ctypes.POINTER(StreamInfo)).contents
    request_id_str = stream_info.request_id.split(b'\x00', 1)[0].decode(errors="replace")
    log_data = {
        "Key": stream_info.key,
        "Request ID": request_id_str,
        "Upstream Connection ID": stream_info.upstream_conn_id,
        "Stream ID": stream_info.stream_id,
        "Header Parse Start Time": stream_info.header_parse_start_time,
        "Header Parse End Time": stream_info.header_parse_end_time,
        "Data Parse Start Time": stream_info.data_parse_start_time,
        "Data Parse End Time": stream_info.data_parse_end_time,
        "Trailer Parse Start Time": stream_info.trailer_parse_start_time,
        "Trailer Parse End Time": stream_info.trailer_parse_end_time,
        "Stream End Time": stream_info.stream_end_time,
    }
    log_queue.put(json.dumps(log_data))

def http1_conn_callback(cpu, data, size):
    class ConnInfo(ctypes.Structure):
        _fields_ = [
            ("connection_id", ctypes.c_uint),
            ("stream_id", ctypes.c_ulonglong),
            ("write_ready_start_time", ctypes.c_ulonglong),
            ("read_ready_start_time", ctypes.c_ulonglong),
            ("parse_start_time", ctypes.c_ulonglong),
            ("parse_end_time", ctypes.c_ulonglong),
        ]
    conn_info = ctypes.cast(data, ctypes.POINTER(ConnInfo)).contents
    log_data = {
        "Connection ID": conn_info.connection_id,
        "Stream IDs": conn_info.stream_id,
        "Write Ready Start Time": conn_info.write_ready_start_time,
        "Read Ready Start Time": conn_info.read_ready_start_time,
        "Parse Start Time": conn_info.parse_start_time,
        "Parse End Time": conn_info.parse_end_time,
    }
    log_queue.put(json.dumps(log_data))

def http1_stream_callback(cpu, data, size):
    class StreamInfo(ctypes.Structure):
        _fields_ = [
            ("request_id", ctypes.c_char * 32),
            ("upstream_conn_id", ctypes.c_uint),
            ("stream_id", ctypes.c_ulonglong),
            ("header_filter_start_time", ctypes.c_ulonglong),
            ("header_filter_end_time", ctypes.c_ulonglong),
            ("data_filter_start_time", ctypes.c_ulonglong),
            ("data_filter_end_time", ctypes.c_ulonglong),
            ("trailer_filter_start_time", ctypes.c_ulonglong),
            ("trailer_filter_end_time", ctypes.c_ulonglong),
            ("stream_end_time", ctypes.c_ulonglong),
        ]
    stream_info = ctypes.cast(data, ctypes.POINTER(StreamInfo)).contents
    request_id_str = stream_info.request_id.split(b'\x00', 1)[0].decode(errors="replace")
    log_data = {
        "Request ID": request_id_str,
        "Upstream Connection ID": stream_info.upstream_conn_id,
        "Stream ID": stream_info.stream_id,
        "Header Filter Start Time": stream_info.header_filter_start_time,
        "Header Filter End Time": stream_info.header_filter_end_time,
        "Data Filter Start Time": stream_info.data_filter_start_time,
        "Data Filter End Time": stream_info.data_filter_end_time,
        "Trailer Filter Start Time": stream_info.trailer_filter_start_time,
        "Trailer Filter End Time": stream_info.trailer_filter_end_time,
        "Stream End Time": stream_info.stream_end_time,
    }
    log_queue.put(json.dumps(log_data))


def start_trace(type, protocol):
    binary_path = ...

    # attach uprobes
    if type == "cilium":
        binary_path = "/usr/bin/cilium-envoy"
    elif type == "istio":
        binary_path = "/usr/local/bin/envoy"
    else:
        print("Unknown type")
        return

    def register_uprobe(b, uprobe):
        target_pid = find_envoy_pid(type)
        for i, symbol in enumerate(uprobe.hook_symbol_list):
            b.attach_uprobe(sym=symbol, fn_name=uprobe.hook_function_list[i], name=binary_path, pid=target_pid)

    # start working thread to collect logs
    output_file = "/tmp/trace_output.log"
    def log_worker():
        with open(output_file, "a") as f:
            while True:
                try:
                    line = log_queue.get(timeout=1)
                    f.write(line)
                    f.write("\n")
                    f.flush()
                except queue.Empty:
                    continue
    threading.Thread(target=log_worker, daemon=True).start()

    if protocol == "http1":
        trace_uprobe = Http1Uprobe()
        b = BPF(text=trace_uprobe.program)
        register_uprobe(b, trace_uprobe)
        b["conn_events"].open_perf_buffer(http1_conn_callback, page_cnt=256)
        b["stream_events"].open_perf_buffer(http1_stream_callback, page_cnt=256)

        print("Tracing HTTP1... Ctrl+C to stop.")
        try:
            while True:
                b.perf_buffer_poll(timeout=2)
        except KeyboardInterrupt:
            pass
    
    if protocol == "http2":
        stream_uprobe = StreamUprobe()
        conn_uprobe = ConnUprobe()
        b_stream = BPF(text=stream_uprobe.program)
        b_conn = BPF(text=conn_uprobe.program)
        register_uprobe(b_stream, stream_uprobe)
        register_uprobe(b_conn, conn_uprobe)
        b_stream["stream_events"].open_perf_buffer(http2_stream_callback, page_cnt=256)
        b_conn["conn_events"].open_perf_buffer(http2_conn_callback, page_cnt=256)

        print("Tracing HTTP2... Ctrl+C to stop.")
        try:
            while True:
                b_stream.perf_buffer_poll(timeout=2)
                b_conn.perf_buffer_poll(timeout=2)
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Envoy HTTP/2 Tracing")
    parser.add_argument("-t", "--type", type=str, choices=["cilium", "istio"], required=True)
    parser.add_argument("-p", "--protocol", type=str, choices=["http1", "http2"], required=True)
    args = parser.parse_args()
    start_trace(args.type, args.protocol)