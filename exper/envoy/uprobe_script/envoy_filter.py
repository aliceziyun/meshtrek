#!/usr/bin/python3

# this is for grpc, to get the time of filters

from bcc import BPF
import ctypes

program = r"""
#include <uapi/linux/ptrace.h>
struct connection_info_t {
    char uber_id[17];
    u64 stream_id;
    u64 time_start;
    u64 time_request_filter_end;
    u64 time_end;
    u64 time_upstream_recorded;
};

BPF_HASH(stream_id_map, u64, struct connection_info_t);
BPF_PERF_OUTPUT(trace_events);

int request_start(struct pt_regs *ctx) {
    u64 stream_id = (u64)(ctx->r8);
    
    u64 ts = bpf_ktime_get_tai_ns();

    struct connection_info_t new_info = {};
    new_info.stream_id = stream_id;
    new_info.time_start = ts;

    const char* str = (const char *)PT_REGS_PARM2(ctx);
    u64 size = 17; // we know its 16 bytes
    bpf_probe_read_str(new_info.uber_id, size, str);

    stream_id_map.update(&stream_id, &new_info);
    
    return 0;
}

int request_end(struct pt_regs *ctx) {
    u64 stream_id = PT_REGS_PARM3(ctx);
    u64 ts = bpf_ktime_get_tai_ns();

    struct connection_info_t *info = stream_id_map.lookup(&stream_id);
    if (info) {
        info->time_end = ts;
        
        // commit this info to the trace_events
        trace_events.perf_submit(ctx, info, sizeof(*info));
        // remove the connection info from the map
        stream_id_map.delete(&stream_id);
    } else {
        bpf_trace_printk("Stream ID not found in map: %d\\n", stream_id);
    }
    
    return 0;
}

int request_filter_end(struct pt_regs *ctx) {
    u64 stream_id = PT_REGS_PARM3(ctx);
    u64 ts = bpf_ktime_get_tai_ns();
    
    struct connection_info_t *info = stream_id_map.lookup(&stream_id);
    if (info) {
        info->time_request_filter_end = ts;

        return 0;
    } else {
        bpf_trace_printk("Stream ID not found in map: %d\\n", stream_id);
        return 0;
    }
}

int upstream(struct pt_regs *ctx) {
    u64 stream_id = PT_REGS_PARM4(ctx);

    struct connection_info_t *info = stream_id_map.lookup(&stream_id);
    if(info) {
        info->time_upstream_recorded = bpf_ktime_get_tai_ns();
    }else{
        bpf_trace_printk("Stream ID not found in map: %d\\n", stream_id);
    }

    return 0;
}
"""

# --------------- add hook function --------------------
hook_filter_end_symbol = "_ZN5Envoy4Http21ConnectionManagerImpl12ActiveStream19hookpointFiltersEndEim"
hook_start_symbol = "_ZN5Envoy4Http21ConnectionManagerImpl12ActiveStream21hookpointFiltersStartENSt3__117basic_string_viewIcNS3_11char_traitsIcEEEEim"
hook_end_symbol = "_ZN5Envoy4Http21ConnectionManagerImpl12ActiveStream30hookpointOnCodecEncodeCompleteEim"
hook_upstream_symbol = "_ZN5Envoy6Router15UpstreamRequest17hookpointUpstreamEiim"

b = BPF(text=program)
binary_path = "/usr/local/bin/envoy"

import subprocess
def find_envoy_pid():
    cmd = "ps aux | grep '/usr/local/bin/envoy' | grep -v grep"
    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, text=True)

    for line in result.stdout.strip().split('\n'):
        if not line:
            continue
        parts = line.split()
        pid = int(parts[1])
        return pid
    
    raise RuntimeError("Envoy process not found")

target_pid = find_envoy_pid()
b.attach_uprobe(name=binary_path, sym=hook_filter_end_symbol, fn_name="request_filter_end", pid=target_pid)
b.attach_uprobe(name=binary_path, sym=hook_start_symbol, fn_name="request_start", pid=target_pid)
b.attach_uprobe(name=binary_path, sym=hook_end_symbol, fn_name="request_end", pid=target_pid)
b.attach_uprobe(name=binary_path, sym=hook_upstream_symbol, fn_name="upstream", pid=target_pid)

# -------------- extra data structure --------------
output_file = "/tmp/trace_output.log"
import queue, threading

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

# Start the log worker thread
threading.Thread(target=log_worker, daemon=True).start()

def callback(cpu, data, size):
    class ConnInfo(ctypes.Structure):
        _fields_ = [
            ("uber_id", ctypes.c_char * 17),
            ("stream_id", ctypes.c_ulonglong),
            ("time_start", ctypes.c_ulonglong),
            ("time_request_filter_end", ctypes.c_ulonglong),
            ("time_end", ctypes.c_ulonglong),
            ("time_upstream_recorded", ctypes.c_ulonglong),
        ]
    event = ctypes.cast(data, ctypes.POINTER(ConnInfo)).contents
    uber_id_str = event.uber_id.split(b'\x00', 1)[0].decode(errors="replace")
    log_queue.put(f"Stream ID: {event.stream_id}, X-Request-ID: {uber_id_str}, Time Start: {event.time_start}, Time Request Filter End: {event.time_request_filter_end}, "
                  f"Time End: {event.time_end}, Time Upstream Recorded: {event.time_upstream_recorded} \n")

# ----------- register callbacks ------------------
b["trace_events"].open_perf_buffer(callback, page_cnt=256)

print("Tracing... Ctrl+C to stop.")
try:
    while True:
        b.perf_buffer_poll(timeout=10)
except KeyboardInterrupt:
    pass