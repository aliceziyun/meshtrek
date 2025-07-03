#!/usr/bin/python3
from bcc import BPF
import ctypes
import time

program = r"""
#include <uapi/linux/ptrace.h>
struct connid_time_t {
    u32 connection_id;
    u64 elapsed_time;
};

BPF_HASH(connection_id_map, u32, u64);  // <connection_id, time>
BPF_PERF_OUTPUT(parse_events);
BPF_PERF_OUTPUT(decode_events);
BPF_PERF_OUTPUT(upstream_events);

int parse_start(struct pt_regs *ctx) {
    // get the second parameter of the function
    u32 connection_id = PT_REGS_PARM2(ctx);
    u64 ts = bpf_ktime_get_ns();
    connection_id_map.update(&connection_id, &ts);
    return 0;
}

int parse_end(struct pt_regs *ctx) {
    u32 connection_id = PT_REGS_PARM2(ctx);
    u64 ts = bpf_ktime_get_ns();
    u64 *existing_ts = connection_id_map.lookup(&connection_id);
    if(existing_ts) {
        // send the elapsed time to userspace
        struct connid_time_t data = {};
        data.connection_id = connection_id;
        data.elapsed_time = ts - *existing_ts;
        connection_id_map.delete(&connection_id);
        parse_events.perf_submit(ctx, &data, sizeof(data));
        return 0;
    }else{
        // this should not happen, error
        bpf_trace_printk("Connection ID not found in map: %d\\n", connection_id);
        return 0;
    }
}

struct stream_info_t {
    char x_request_id[40];
    u32 connection_id;
    u64 stream_id;
};

int record_xid(struct pt_regs *ctx) {
    struct stream_info_t stream_info = {};
    const char* str = (const char *)PT_REGS_PARM2(ctx);

    // u64 size = (u64)PT_REGS_PARM3(ctx);
    // bpf_trace_printk("size = %llu\n", size);
    // if ((s64)size <= 0 || size > 40)
    //    return 0;

    u64 size = 36; // we know its 36 bytes

    bpf_probe_read_str(&stream_info.x_request_id, size + 1, str);
    stream_info.x_request_id[size + 1] = '\0';

    stream_info.connection_id = PT_REGS_PARM4(ctx);
    stream_info.stream_id = (u64)(ctx->r8);

    decode_events.perf_submit(ctx, &stream_info, sizeof(stream_info));
    return 0;
}

struct connection_map_t {
    u32 upstream_id;
    u32 downstream_id;
};

int record_upstream_connection_map(struct pt_regs *ctx) {
    struct connection_map_t conn_map = {};

    conn_map.upstream_id = PT_REGS_PARM2(ctx);
    conn_map.downstream_id = PT_REGS_PARM3(ctx);

    upstream_events.perf_submit(ctx, &conn_map, sizeof(conn_map));

    return 0;
}
"""
# --------------- add hook function --------------------
hook_dispatch_symbol = "_ZN5Envoy4Http5Http114ConnectionImpl17hookpointDispatchEi"
hook_on_headers_complete_symbol = "_ZN5Envoy4Http5Http114ConnectionImpl26hookpointOnHeadersCompleteEi"
hook_decode_headers_symbol = "_ZN5Envoy6Router6Filter22hookpointDecodeHeadersENSt3__117basic_string_viewIcNS2_11char_traitsIcEEEEim"
hook_upstream_symbol = "_ZN5Envoy6Router15UpstreamRequest17hookpointUpstreamEiim"

b = BPF(text=program)
binary_path = "/usr/local/bin/envoy"
b.attach_uprobe(name=binary_path, sym=hook_dispatch_symbol, fn_name="parse_start")
b.attach_uprobe(name=binary_path, sym=hook_on_headers_complete_symbol, fn_name="parse_end")
b.attach_uprobe(name=binary_path, sym=hook_decode_headers_symbol, fn_name="record_xid")
b.attach_uprobe(name=binary_path, sym=hook_upstream_symbol, fn_name="record_upstream_connection_map")

# -------------- extra data structure --------------
output_file = "/tmp/trace_output.log"
import queue, threading, time

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

# ----------- register callbacks ------------------
def parse_end_callback(cpu, data, size):
    class ConnIdTime(ctypes.Structure):
        _fields_ = [("connection_id", ctypes.c_uint),
                    ("elapsed_time", ctypes.c_ulonglong)]
    event = ctypes.cast(data, ctypes.POINTER(ConnIdTime)).contents
    log_queue.put(f"[parse-end] connection_id: {event.connection_id}, elapsed_time: {event.elapsed_time} \n")

def stream_decode_callback(cpu, data, size):
    class StreamInfo(ctypes.Structure):
        _fields_ = [
            ("x_request_id", ctypes.c_char * 40),
            ("connection_id", ctypes.c_uint),
            ("stream_id", ctypes.c_ulonglong)
        ]
    event = ctypes.cast(data, ctypes.POINTER(StreamInfo)).contents
    # decode stream
    x_request_id_str = event.x_request_id.split(b'\x00', 1)[0].decode(errors="replace")
    log_queue.put(f"[decode] x_id: {x_request_id_str}, connection_id: {event.connection_id}, stream_id: {event.stream_id}\n")

def upstream_callback(cpu, data, size): 
    class ResStreamInfo(ctypes.Structure):
        _fields_ = [
            ("upstream_id", ctypes.c_uint),
            ("downstream_id", ctypes.c_uint),
            ("stream_id", ctypes.c_ulonglong)
        ]
    event = ctypes.cast(data, ctypes.POINTER(ResStreamInfo)).contents
    log_queue.put(f"[upstream] upstreamId: {event.upstream_id}, downstreamId: {event.downstream_id}, streamId: {event.stream_id}\n")

b["parse_events"].open_perf_buffer(parse_end_callback, page_cnt=256)
b["decode_events"].open_perf_buffer(stream_decode_callback, page_cnt=256)
b["upstream_events"].open_perf_buffer(upstream_callback, page_cnt=256)

print("Tracing... Ctrl+C to stop.")
try:
    while True:
        b.perf_buffer_poll(timeout=100)
except KeyboardInterrupt:
    pass