#!/usr/bin/python3

from bcc import BPF
import ctypes
import subprocess

program = r"""
#include <uapi/linux/ptrace.h>
struct request_info_t {
    char uber_id[17];
    u32 tmp_stream_id;
    u64 stream_id;

    u64 time_start;
    u64 time_request_filter_start;
    u64 time_process_start;
    u64 time_response_filter_start;
    u64 time_end;

    u64 upstream_time_http_parse_start;
    u64 upstream_time_end;
}

BPF_HASH(stream_id_map, u32, struct request_info_t);
BPF_HASH(request_id_map, u64, struct request_info_t);
BPF_PERF_OUTPUT(trace_events);

// ConnectionImpl::Http2Visitor::OnBeginHeadersForStream <tmp_stream_id>
int request_and_http_parse_start(struct pt_regs *ctx) {
    u32 tmp_stream_id = PT_REGS_PARM2(ctx);
    u64 ts = bpf_ktime_get_tai_ns();
    struct request_info_t info = {};
    info.tmp_stream_id = tmp_stream_id;
    info.time_start = ts;

    stream_id_map.update(&tmp_stream_id, &info);
    return 0;
}

// ConnectionImpl::Http2Visitor::OnEndHeadersForStream <tmp_stream_id>
int request_filter_start(struct pt_regs *ctx) {
    u32 tmp_stream_id = PT_REGS_PARM2(ctx);
    u64 ts = bpf_ktime_get_tai_ns();
    struct request_info_t *info = stream_id_map.lookup(&tmp_stream_id);
    if(info) {
        info->time_request_filter_start = ts;
    } else{
        // bpf_trace_printk("request_filter_start: not found tmp_stream_id %d\n", tmp_stream_id);
    }

    return 0;
}

// ConnectionManagerImpl::ActiveStream::decodeHeaders <connection_id, stream_id, tmp_stream_id>
// this function is to support for associating tmp_stream_id with stream_id
// TODO: I want to combine this function with process_start() and delete this function
int associate_stream_id(struct pt_regs *ctx) {
    u64 stream_id = PT_REGS_PARM3(ctx);
    u32 tmp_stream_id = PT_REGS_PARM4(ctx);
    struct request_info_t *info = stream_id_map.lookup(&tmp_stream_id);
    if(info) {
        info->stream_id = stream_id;
        request_id_map.update(&stream_id, info);
        stream_id_map.delete(&tmp_stream_id);
    } else{
        // bpf_trace_printk("associate_stream_id: not found tmp_stream_id %d\n", tmp_stream_id);
    }
    return 0;
}

// ConnectionManagerImpl::ActiveStream::decodeHeaders <x_request_id, connection_id, stream_id>
int process_start(struct pt_regs *ctx) {
    u64 stream_id = (u64)ctx->r8;
    struct request_info_t *info = request_id_map.lookup(&stream_id);
    if(info) {
        const char* str = (const char *)PT_REGS_PARM2(ctx);
        u64 size = 16;
        bpf_probe_read_str(info->uber_id, sizeof(info->uber_id), str);
        info->uber_id[size] = '\0';
        info->time_process_start = bpf_ktime_get_tai_ns();
    } else{
        // bpf_trace_printk("process_start: not found stream_id %d\n", stream_id);
    }
    return 0;
}

// UpstreamRequest::decodeHeaders <upstream_connection_id, connection_id, stream_id>
// TODO: I want to change this hookpoint to <upstream_id, stream_id>
int response_filter_start(struct pt_regs *ctx) {
    u64 upstream_stream_id = (u64) PT_REGS_PARM2(ctx);
    u64 stream_id = (64) PT_REGS_PARM3(ctx);
    struct request_info_t *upstream_info = request_id_map.lookup(&upstream_stream_id);
    if(upstream_info) {
        struct request_info_t *info = request_id_map.lookup(&stream_id);
        if(info) {
            info->time_response_filter_start = bpf_ktime_get_tai_ns();

            info->upstream_time_http_parse_start = upstream_info->time_start;
            info->upstream_time_end = upstream_info->time_request_filter_start;

            request_id_map.delete(&upstream_stream_id);
        }
    } else{
        // bpf_trace_printk("response_filter_start: not found upstream_stream_id %d\n", upstream_stream_id);
    }
    return 0;
}

// ConnectionManagerImpl::ActiveStream::onCodecEncodeComplete <connection_id, stream_id>
int request_end(struct pt_regs *ctx) {
    u64 stream_id = (u64) PT_REGS_PARM3(ctx);
    struct request_info_t *info = request_id_map.lookup(&stream_id);
    if(info) {
        info->time_end = bpf_ktime_get_tai_ns();
        trace_events.perf_submit(ctx, info, sizeof(*info));
        request_id_map.delete(&stream_id);
    } else{
        // bpf_trace_printk("request_end: not found stream_id %d\n", stream_id);
    }
    return 0;
}
"""

import argparse
import json
import queue, threading

hook_symbol_list = [

]

hook_function_list = ["request_and_http_parse_start",
                      "request_filter_start",
                      "associate_stream_id",
                      "process_start",
                      "response_filter_start",
                      "request_end"]

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
    b = BPF(text=program)

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
    for i, symbol in enumerate(hook_symbol_list):
        b.attach_uprobe(sym=symbol, fn_name=hook_function_list[i], name=binary_path, pid=target_pid)

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
    start_trace(parser.t)