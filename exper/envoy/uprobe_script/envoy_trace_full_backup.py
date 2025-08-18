#!/usr/bin/python3

# no read and write
# 1st stage: http parsing - from dispatch() to on HeaderComplete()
# 2nd stage: filters(request) from onHeaderComplete() to dispatch()
# 3rd stage: http parsing - from dispatch() to on HeaderComplete()
# 4th stage: filters(response) from Upstream::decodeHeaders() to doDeferredStreamDestroy()

from bcc import BPF
import ctypes
import subprocess

program = r"""
#include <uapi/linux/ptrace.h>
struct connection_info_t {
    char x_request_id[40];
    u32 connection_id;
    u32 upstream_id;
    u64 time_start;     // dispatch()
    u64 time_http_parsed;  // onHeaderComplete()
    u64 time_filters_end; // dispatch()
    u64 time_upstream_recorded;     // Upstream::decodeHeaders()
    u64 time_end;   // doDeferredStreamDestroy()

    u64 upstream_time_start;
    u64 upstream_time_http_parsed;
};

BPF_HASH(connection_id_map, u32, struct connection_info_t);
BPF_PERF_OUTPUT(trace_events);

int http_parse_start(struct pt_regs *ctx) {
    bpf_trace_printk("http_parse_start called\\n");
    u32 connection_id = PT_REGS_PARM2(ctx);
    u64 ts = bpf_ktime_get_tai_ns();

    struct connection_info_t info = {};
    info.connection_id = connection_id;
    info.time_start = ts;

    connection_id_map.update(&connection_id, &info);

    return 0;
}

int http_parsed(struct pt_regs *ctx) {
    u32 connection_id = PT_REGS_PARM2(ctx);
    u64 ts = bpf_ktime_get_tai_ns();
    
    struct connection_info_t *info = connection_id_map.lookup(&connection_id);
    if (info) {
        info->time_http_parsed = ts;
    }

    return 0;
}

int filters_end(struct pt_regs *ctx) {
    u32 connection_id = PT_REGS_PARM2(ctx);
    u64 ts = bpf_ktime_get_tai_ns();
    
    struct connection_info_t *info = connection_id_map.lookup(&connection_id);
    if (info) {
        info->time_filters_end = ts;
    }

    return 0;
}

int record_xid(struct pt_regs *ctx) {
    u32 connection_id = PT_REGS_PARM4(ctx);
    bpf_trace_printk("record_xid called with connection_id %d\\n", connection_id);
    struct connection_info_t *info = connection_id_map.lookup(&connection_id);
    if (info) {
        const char* str = (const char *)PT_REGS_PARM3(ctx);

        bpf_trace_printk("record_xid is str %s with length %d\\n", str, PT_REGS_PARM2(ctx));

        u64 size = 36; // we know its 36 bytes
        bpf_probe_read_str(info->x_request_id, sizeof(info->x_request_id), str);
        info->x_request_id[size] = '\0';

        return 0;
    } else {
        // bpf_trace_printk("Connection ID not found in map: %d\\n", PT_REGS_PARM4(ctx));
        return 0;
    }
}

int upstream(struct pt_regs *ctx) {
    u32 connection_id = PT_REGS_PARM3(ctx);
    u32 upstream_id = PT_REGS_PARM2(ctx);

    struct connection_info_t *upstream_info = connection_id_map.lookup(&upstream_id);
    if(upstream_info) {
        struct connection_info_t *info = connection_id_map.lookup(&connection_id);
        if(info) {
            info->time_upstream_recorded = bpf_ktime_get_tai_ns();
            info->upstream_id = upstream_id;

            info->upstream_time_start = upstream_info->time_start;
            info->upstream_time_http_parsed = upstream_info->time_http_parsed;
        }

        // remove upstream connection info from the map
        connection_id_map.delete(&upstream_id);
    }

    return 0;
}

int request_end(struct pt_regs *ctx) {
    u32 connection_id = PT_REGS_PARM2(ctx);
    u64 ts = bpf_ktime_get_tai_ns();

    struct connection_info_t *info = connection_id_map.lookup(&connection_id);
    if (info) {
        info->time_end = ts;
        trace_events.perf_submit(ctx, info, sizeof(*info));
        // remove the connection info from the map
        connection_id_map.delete(&connection_id);
    } else {
        // bpf_trace_printk("Connection ID not found in map: %d\\n", connection_id);
    }
    
    return 0;
}
"""

hook_symbol_list = [
    "_ZN5Envoy4Http21ConnectionManagerImpl12ActiveStream30hookpointOnCodecEncodeCompleteEim",
    "_ZN5Envoy4Http5Http114ConnectionImpl17hookpointDispatchEi",
    "_ZN5Envoy4Http5Http114ConnectionImpl20hookpointDispatchEndEi",
    "_ZN5Envoy6Router15UpstreamRequest17hookpointUpstreamEiim",
    "_ZN5Envoy6Router6Filter22hookpointDecodeHeadersESt17basic_string_viewIcSt11char_traitsIcEEim",
    "_ZN5Envoy4Http5Http114ConnectionImpl26hookpointOnHeadersCompleteEi",
]

hook_function_list = ["request_end", "http_parse_start", "filters_end", "upstream", "record_xid", "http_parsed"]

b = BPF(text=program)
# binary_path = "/usr/local/bin/envoy"
binary_path = "/usr/bin/cilium-envoy"

def find_envoy_pid():
    # cmd = "ps aux | grep '/usr/local/bin/envoy' | grep -v grep"
    cmd = "ps aux | grep '/usr/bin/cilium-envoy -c /var/run/cilium/envoy/bootstrap-config.json --base-id 0' | grep -v grep"
    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, text=True)

    for line in result.stdout.strip().split('\n'):
        if not line:
            continue
        parts = line.split()
        pid = int(parts[1])
        return pid
    
    raise RuntimeError("Envoy process not found")

target_pid = find_envoy_pid()
for i, symbol in enumerate(hook_symbol_list):
    b.attach_uprobe(sym=symbol, fn_name=hook_function_list[i], name=binary_path, pid=target_pid)

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
            ("x_request_id", ctypes.c_char * 40),
            ("connection_id", ctypes.c_uint),
            ("upstream_id", ctypes.c_uint),
            ("time_start", ctypes.c_ulonglong),
            ("time_http_parsed", ctypes.c_ulonglong),
            ("time_filters_end", ctypes.c_ulonglong),
            ("time_upstream_recorded", ctypes.c_ulonglong),
            ("time_end", ctypes.c_ulonglong),
            ("time_upstream_start", ctypes.c_ulonglong),
            ("time_upstream_http_parsed", ctypes.c_ulonglong),
        ]
    event = ctypes.cast(data, ctypes.POINTER(ConnInfo)).contents
    x_request_id_str = event.x_request_id.split(b'\x00', 1)[0].decode(errors="replace")
    log_queue.put(f"Connection ID: {event.connection_id}, X-Request-ID: {x_request_id_str}, Time Start: {event.time_start}, Time HTTP Parsed: {event.time_http_parsed}, Time Filters End: {event.time_filters_end}, Upstream Time Start: {event.time_upstream_start}, Upstream Time HTTP Parsed: {event.time_upstream_http_parsed}, Upstream Time Recorded: {event.time_upstream_recorded}, Time End: {event.time_end}\n")

# ----------- register callbacks ------------------
b["trace_events"].open_perf_buffer(callback, page_cnt=256)

print("Tracing... Ctrl+C to stop.")
try:
    while True:
        b.perf_buffer_poll(timeout=5)
except KeyboardInterrupt:
    pass