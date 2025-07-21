#!/usr/bin/python3
from bcc import BPF
import ctypes

program = r"""
#include <uapi/linux/ptrace.h>
struct connection_info_t {
    char x_request_id[40];
    u32 connection_id;
    u64 elapsed_time;
};

BPF_HASH(connection_id_map, u32, struct connection_info_t);
BPF_PERF_OUTPUT(trace_events);

int request_start(struct pt_regs *ctx) {
    u32 connection_id = PT_REGS_PARM3(ctx);
    u64 ts = bpf_ktime_get_ns();

    struct connection_info_t *info = connection_id_map.lookup(&connection_id);
    if (info) {
        // If the connection already exists, update the elapsed time
        info->elapsed_time = ts - info->elapsed_time;
    } else {
        bpf_trace_printk("Connection ID not found in map: %d\\n", connection_id);
    }
    
    return 0;
}

int request_end(struct pt_regs *ctx) {
    u32 connection_id = PT_REGS_PARM2(ctx);
    u64 ts = bpf_ktime_get_ns();

    struct connection_info_t *info = connection_id_map.lookup(&connection_id);
    if (info) {
        info->elapsed_time = ts - info->elapsed_time;
        
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
    u64 size = 36; // we know its 36 bytes
    const char* str = (const char *)PT_REGS_PARM2(ctx);
    struct connection_info_t *info = connection_id_map.lookup(&connection_id);

    // create a new struct 
    struct connection_info_t new_info = {};
    new_info.connection_id = connection_id;
    new_info.elapsed_time = 0; // initialize elapsed_time to 0
    bpf_probe_read_str(new_info.x_request_id, sizeof(new_info.x_request_id), str);
    new_info.x_request_id[size] = '\0';

    // update the map with the new info
    connection_id_map.update(&connection_id, &new_info);

    return 0;
}
"""

# --------------- add hook function --------------------
hook_decode_headers_symbol = "_ZN5Envoy6Router6Filter22hookpointDecodeHeadersENSt3__117basic_string_viewIcNS2_11char_traitsIcEEEEim"
hook_start_symbol = "_ZN5Envoy6Router15UpstreamRequest17hookpointUpstreamEiim"     # upstream()
hook_end_symbol = "_ZN5Envoy4Http21ConnectionManagerImpl12ActiveStream30hookpointOnCodecEncodeCompleteEi"   # end

b = BPF(text=program)
binary_path = "/usr/local/bin/envoy"

b.attach_uprobe(name=binary_path, sym=hook_decode_headers_symbol, fn_name="record_xid")
b.attach_uprobe(name=binary_path, sym=hook_start_symbol, fn_name="request_start")
b.attach_uprobe(name=binary_path, sym=hook_end_symbol, fn_name="request_end")

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
            ("elapsed_time", ctypes.c_ulonglong),
        ]
    event = ctypes.cast(data, ctypes.POINTER(ConnInfo)).contents
    x_request_id_str = event.x_request_id.split(b'\x00', 1)[0].decode(errors="replace")
    log_queue.put(f"Connection ID: {event.connection_id}, X-Request-ID: {x_request_id_str}, Elapsed Time: {event.elapsed_time} ns\n")

# ----------- register callbacks ------------------
b["trace_events"].open_perf_buffer(callback, page_cnt=256)

print("Tracing... Ctrl+C to stop.")
try:
    while True:
        b.perf_buffer_poll(timeout=10)
except KeyboardInterrupt:
    pass