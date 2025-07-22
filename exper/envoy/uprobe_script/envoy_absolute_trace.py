#!/usr/bin/python3

# get the absolute time of the start/end of the request, so we can know whether the abnormal
# request will contribute to the total time of the request or not.

from bcc import BPF
import ctypes

program = r"""
#include <uapi/linux/ptrace.h>
struct connection_info_t {
    char x_request_id[40];
    u32 connection_id;
    u64 time_start;
    u64 time_end;
    u64 time_upstream_recorded;
    u64 time_decode_header;
    u64 process_id;
};

BPF_HASH(connection_id_map, u32, struct connection_info_t);
BPF_PERF_OUTPUT(trace_events);

int request_start(struct pt_regs *ctx) {
    u32 connection_id = PT_REGS_PARM2(ctx);
    u64 ts = bpf_ktime_get_ns();

    struct connection_info_t new_info = {};
    new_info.connection_id = connection_id;
    new_info.time_start = ts;
    new_info.time_end = 0;
    new_info.time_upstream_recorded = 0;
    new_info.time_decode_header = 0;
    new_info.process_id = bpf_get_current_pid_tgid() >> 32; // get the process ID

    connection_id_map.update(&connection_id, &new_info);
    
    return 0;
}

int request_end(struct pt_regs *ctx) {
    u32 connection_id = PT_REGS_PARM2(ctx);
    u64 ts = bpf_ktime_get_ns();

    struct connection_info_t *info = connection_id_map.lookup(&connection_id);
    if (info) {
        info->time_end = ts;
        
        // commit this info to the trace_events
        trace_events.perf_submit(ctx, info, sizeof(*info));
        // remove the connection info from the map
        connection_id_map.delete(&connection_id);
    } else {
        bpf_trace_printk("Connection ID not found in map: %d\\n", connection_id);
    }
    
    return 0;
}

int record_xid(struct pt_regs *ctx) {
    u32 connection_id = PT_REGS_PARM4(ctx);
    struct connection_info_t *info = connection_id_map.lookup(&connection_id);
    if (info) {
        const char* str = (const char *)PT_REGS_PARM2(ctx);

        u64 size = 36; // we know its 36 bytes
        bpf_probe_read_str(info->x_request_id, sizeof(info->x_request_id), str);
        info->x_request_id[size] = '\0';

        info->time_decode_header = bpf_ktime_get_ns();

        return 0;
    } else {
        bpf_trace_printk("Connection ID not found in map: %d\\n", PT_REGS_PARM2(ctx));
        return 0;
    }
}

int upstream(struct pt_regs *ctx) {
    u32 connection_id = PT_REGS_PARM3(ctx);

    struct connection_info_t *info = connection_id_map.lookup(&connection_id);
    if(info) {
        info->time_upstream_recorded = bpf_ktime_get_ns();
    }else{
        bpf_trace_printk("Connection ID not found in map: %d\\n", connection_id);
    }

    return 0;
    
}
"""

# --------------- add hook function --------------------
hook_decode_headers_symbol = "_ZN5Envoy6Router6Filter22hookpointDecodeHeadersENSt3__117basic_string_viewIcNS2_11char_traitsIcEEEEim"
hook_start_symbol = "_ZN5Envoy4Http21ConnectionManagerImpl15hookpointOnDataEi"
hook_end_symbol = "_ZN5Envoy4Http21ConnectionManagerImpl32hookpointDoDeferredStreamDestroyEi"
hook_upstream_symbol = "_ZN5Envoy6Router15UpstreamRequest17hookpointUpstreamEiim"

b = BPF(text=program)
binary_path = "/usr/local/bin/envoy"

target_pid = 13
b.attach_uprobe(name=binary_path, sym=hook_decode_headers_symbol, fn_name="record_xid", pid=target_pid)
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
            ("x_request_id", ctypes.c_char * 40),
            ("connection_id", ctypes.c_uint),
            ("time_start", ctypes.c_ulonglong),
            ("time_end", ctypes.c_ulonglong),
            ("time_upstream_recorded", ctypes.c_ulonglong),
            ("time_decode_header", ctypes.c_ulonglong),
            ("process_id", ctypes.c_uint)
        ]
    event = ctypes.cast(data, ctypes.POINTER(ConnInfo)).contents
    x_request_id_str = event.x_request_id.split(b'\x00', 1)[0].decode(errors="replace")
    log_queue.put(f"Connection ID: {event.connection_id}, X-Request-ID: {x_request_id_str}, Time Start: {event.time_start}, "
                  f"Time End: {event.time_end}, Time Upstream Recorded: {event.time_upstream_recorded}, "
                  f"Time Decode Header: {event.time_decode_header}, Process ID: {event.process_id}\n")

# ----------- register callbacks ------------------
b["trace_events"].open_perf_buffer(callback, page_cnt=256)

print("Tracing... Ctrl+C to stop.")
try:
    while True:
        b.perf_buffer_poll(timeout=10)
except KeyboardInterrupt:
    pass