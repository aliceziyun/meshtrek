#!/usr/bin/python3
from bcc import BPF
import ctypes

program = r"""
#include <uapi/linux/ptrace.h>
struct connection_info_t {
    char x_request_id[40];
    u32 connection_id;
    u32 upstream_id;
    u64 elapsed_time;
    u64 stream_id;
};

BPF_HASH(connection_id_map, u32, struct connection_info_t);  // <connection_id, time>
// BPF_PERF_OUTPUT(parse_events);
// BPF_PERF_OUTPUT(decode_events);
BPF_PERF_OUTPUT(upstream_events);

int parse_start(struct pt_regs *ctx) {
    // get the second parameter of the function
    u32 connection_id = PT_REGS_PARM2(ctx);
    u64 ts = bpf_ktime_get_ns();

    struct connection_info_t info = {};
    info.connection_id = connection_id;
    info.elapsed_time = ts;

    connection_id_map.update(&connection_id, &info);
    return 0;
}

int parse_end(struct pt_regs *ctx) {
    u32 connection_id = PT_REGS_PARM2(ctx);
    u64 ts = bpf_ktime_get_ns();

    struct connection_info_t *info = connection_id_map.lookup(&connection_id);
    if(info) {
        // update the elapsed time
        info->elapsed_time = ts - info->elapsed_time;
        connection_id_map.update(&connection_id, info);

        return 0;
    } else {
        // this should not happen, error
        bpf_trace_printk("Connection ID not found in map: %d\\n", connection_id);
        return 0;
    }
}

int record_xid(struct pt_regs *ctx) {
    bpf_trace_printk("hook hit! pid=%d\n", bpf_get_current_pid_tgid() >> 32);

    u32 connection_id = PT_REGS_PARM4(ctx);
    struct connection_info_t *info = connection_id_map.lookup(&connection_id);
    if (info) {
        const char* str = (const char *)PT_REGS_PARM2(ctx);

        u64 size = 36; // we know its 36 bytes
        bpf_probe_read_str(info->x_request_id, sizeof(info->x_request_id), str);
        info->x_request_id[size] = '\0';

        info->stream_id = (u64)(ctx->r8);

        bpf_trace_printk("X-Request-ID: %s, connection_id: %d, stream_id: %llu\\n",
                         info->x_request_id, connection_id, info->stream_id);
        return 0;
    } else {
        bpf_trace_printk("Connection ID not found in map: %d\\n", PT_REGS_PARM2(ctx));
        return 0;
    }
}

int record_upstream_connection_map(struct pt_regs *ctx) {
    u32 upstream_id = PT_REGS_PARM2(ctx);
    u32 downstream_id = PT_REGS_PARM3(ctx);
    
    // Find the connection info from the map
    struct connection_info_t *info = connection_id_map.lookup(&downstream_id);
    if (info) {
        info->upstream_id = upstream_id;

        // Find upstream info in the map
        struct connection_info_t *upstream_info = connection_id_map.lookup(&upstream_id);
        if (upstream_info) {
            info->elapsed_time = info->elapsed_time + upstream_info->elapsed_time;

            // remove upstream and downstream connection info from the map
            connection_id_map.delete(&upstream_id);
            connection_id_map.delete(&downstream_id);

            // send info to the perf buffer
            upstream_events.perf_submit(ctx, info, sizeof(*info));
        } else {
            bpf_trace_printk("Upstream ID not found in map: %d\\n", upstream_id);
            return 0;
        }
    } else {
        bpf_trace_printk("Connection ID not found in map: %d\\n", downstream_id);
        return 0;
    }

    return 0;
}

int inspect_headers(struct pt_regs *ctx) {
    u32 connection_id = PT_REGS_PARM2(ctx);
    u32 attempt_count = (u32)PT_REGS_PARM3(ctx);
    bpf_trace_printk("Inspecting headers for connection_id: %d, attempt_count: %d\\n", connection_id, attempt_count);

    return 0;
}
"""
# --------------- add hook function --------------------
hook_dispatch_symbol = "_ZN5Envoy4Http5Http114ConnectionImpl17hookpointDispatchEi"
hook_on_headers_complete_symbol = "_ZN5Envoy4Http5Http114ConnectionImpl26hookpointOnHeadersCompleteEi"
hook_decode_headers_symbol = "_ZN5Envoy6Router6Filter22hookpointDecodeHeadersENSt3__117basic_string_viewIcNS2_11char_traitsIcEEEEim"
hook_upstream_symbol = "_ZN5Envoy6Router15UpstreamRequest17hookpointUpstreamEiim"
hook_inspect_headers = "_ZN5Envoy6Router6Filter23hookpointInspectHeadersEii"

b = BPF(text=program)
binary_path = "/usr/local/bin/envoy"
b.attach_uprobe(name=binary_path, sym=hook_dispatch_symbol, fn_name="parse_start")
b.attach_uprobe(name=binary_path, sym=hook_on_headers_complete_symbol, fn_name="parse_end")
b.attach_uprobe(name=binary_path, sym=hook_decode_headers_symbol, fn_name="record_xid")
b.attach_uprobe(name=binary_path, sym=hook_upstream_symbol, fn_name="record_upstream_connection_map")
b.attach_uprobe(name=binary_path, sym=hook_inspect_headers, fn_name="inspect_headers")

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

# ----------- register callbacks ------------------
# def parse_end_callback(cpu, data, size):
#     class ConnIdTime(ctypes.Structure):
#         _fields_ = [("connection_id", ctypes.c_uint),
#                     ("elapsed_time", ctypes.c_ulonglong)]
#     event = ctypes.cast(data, ctypes.POINTER(ConnIdTime)).contents
#     log_queue.put(f"[parse-end] connection_id: {event.connection_id}, elapsed_time: {event.elapsed_time} \n")

# def stream_decode_callback(cpu, data, size):
def upstream_callback(cpu, data, size):
    class ConnInfo(ctypes.Structure):
        _fields_ = [
            ("x_request_id", ctypes.c_char * 40),
            ("connection_id", ctypes.c_uint),
            ("upstream_id", ctypes.c_uint),
            ("elapsed_time", ctypes.c_ulonglong),
            ("stream_id", ctypes.c_ulonglong),
        ]
    event = ctypes.cast(data, ctypes.POINTER(ConnInfo)).contents
    # decode stream
    x_request_id_str = event.x_request_id.split(b'\x00', 1)[0].decode(errors="replace")
    log_queue.put(f"[decode] x_request_id: {x_request_id_str}, connection_id: {event.connection_id}, "
                  f"upstream_id: {event.upstream_id}, elapsed_time: {event.elapsed_time}, "
                  f"stream_id: {event.stream_id}\n")

# def upstream_callback(cpu, data, size): 
#     class ResStreamInfo(ctypes.Structure):
#         _fields_ = [
#             ("upstream_id", ctypes.c_uint),
#             ("downstream_id", ctypes.c_uint),
#             ("stream_id", ctypes.c_ulonglong)
#         ]
#     event = ctypes.cast(data, ctypes.POINTER(ResStreamInfo)).contents
#     log_queue.put(f"[upstream] upstreamId: {event.upstream_id}, downstreamId: {event.downstream_id}, streamId: {event.stream_id}\n")

# b["parse_events"].open_perf_buffer(parse_end_callback, page_cnt=256)
# b["decode_events"].open_perf_buffer(stream_decode_callback, page_cnt=256)
b["upstream_events"].open_perf_buffer(upstream_callback, page_cnt=256)

print("Tracing... Ctrl+C to stop.")
try:
    while True:
        b.perf_buffer_poll(timeout=10)
except KeyboardInterrupt:
    pass