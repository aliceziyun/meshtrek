#!/usr/bin/python3

# is this the final goal? At least for now!
# 1st stage: read from socket
# 2nd stage: http parsing - from dispatch() to on HeaderComplete()
# 3rd stage: filters(request) from onHeaderComplete() to dispatch()
# 4th stage: write to endpoint
# 5th stage: read response from endpoint
# 6th stage: http parsing - from dispatch() to on HeaderComplete()
# 7th stage: filters(response) from Upstream::decodeHeaders() to doDeferredStreamDestroy()
# 8th stage: write response to socket

# and the 4,5,6 happens in upstream connection

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

    // for read and write
    u64 read_time;
    u64 write_time;
    u64 total_time;
};

BPF_HASH(connection_id_map, u32, struct connection_info_t);
BPF_PERF_OUTPUT(trace_events);

// hook read function, this is the actual start point of a request
// but it might also record the upstream time, so we need to be careful
int perform_read(struct pt_regs *ctx) {
    u32 connection_id = PT_REGS_PARM2(ctx);
    u64 bytes_read = PT_REGS_PARM3(ctx);
    u64 ts = bpf_ktime_get_tai_ns();

    struct connection_info_t* info = connection_id_map.lookup(&connection_id);
    if (info) {
        if(bytes_read == -1) {          // read start
            info->read_time = ts;
        }else if(bytes_read == 0){       // sometimes it will read nothing, so we can add it to the total time and reset the read time
            info->total_time = info->total_time + ts - info->read_time;
            info->read_time = 0;
        }else {
            info->read_time = ts - info->read_time;
        }
    } else {
        // create a new entry as the read operation is the first operation
        struct connection_info_t new_info = {};
        new_info.connection_id = connection_id;
        new_info.read_time = ts;
        connection_id_map.update(&connection_id, &new_info);
    }
    
    return 0;
}

// hook write function, this is the actual end point of a request
int perform_write(struct pt_regs *ctx) {
    u32 connection_id = PT_REGS_PARM2(ctx);
    u64 bytes_write = PT_REGS_PARM3(ctx);
    u64 ts = bpf_ktime_get_tai_ns();

    struct connection_info_t* info = connection_id_map.lookup(&connection_id);
    if (info) {
        if(bytes_write == -1) {          // write start
            info->write_time = ts;
        }else if(bytes_write == 0){
            info->total_time = info->total_time + ts - info->write_time;
            info->write_time = 0;
        }else{
            info->write_time = ts - info->write_time;

            // has read time as a pair
            if(info->read_time != 0) {
                // the first write after the upstream connection, commmit it
                if(info->upstream_id != 0) {
                    // commit this info to the trace_events
                    trace_events.perf_submit(ctx, info, sizeof(*info));
                }

                // remove the connection info from the map
                connection_id_map.delete(&connection_id);
            }
        }
    } else {
        // create a new entry if it doesn't exist (in upstream)
        struct connection_info_t new_info = {};
        new_info.connection_id = connection_id;
        new_info.write_time = ts;
        connection_id_map.update(&connection_id, &new_info);
    }

    return 0;
}

int http_parse_start(struct pt_regs *ctx) {
    u32 connection_id = PT_REGS_PARM2(ctx);
    u64 ts = bpf_ktime_get_tai_ns();
    
    struct connection_info_t *info = connection_id_map.lookup(&connection_id);
    if (info) {
        info->time_start = ts;
    }

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
    struct connection_info_t *info = connection_id_map.lookup(&connection_id);
    if (info) {
        const char* str = (const char *)PT_REGS_PARM2(ctx);

        u64 size = 36; // we know its 36 bytes
        bpf_probe_read_str(info->x_request_id, sizeof(info->x_request_id), str);
        info->x_request_id[size] = '\0';

        return 0;
    } else {
        // bpf_trace_printk("Connection ID not found in map: %d\\n", PT_REGS_PARM2(ctx));
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

            info->total_time = info->total_time + upstream_info->read_time + upstream_info->write_time + upstream_info->total_time;
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
    } else {
        // bpf_trace_printk("Connection ID not found in map: %d\\n", connection_id);
    }
    
    return 0;
}
"""

hook_symbol_list = [
    "_ZN5Envoy10Extensions16TransportSockets3Tls9SslSocket18hookpointSslDoReadEil",
    "_ZN5Envoy10Extensions16TransportSockets3Tls9SslSocket19hookpointSslDoWriteEil",
    "_ZN5Envoy4Http21ConnectionManagerImpl12ActiveStream30hookpointOnCodecEncodeCompleteEi",
    "_ZN5Envoy4Http5Http114ConnectionImpl17hookpointDispatchEi",
    "_ZN5Envoy4Http5Http114ConnectionImpl20hookpointDispatchEndEi",
    "_ZN5Envoy6Router15UpstreamRequest17hookpointUpstreamEiim",
    "_ZN5Envoy6Router6Filter22hookpointDecodeHeadersENSt3__117basic_string_viewIcNS2_11char_traitsIcEEEEim",
    "_ZN5Envoy4Http5Http114ConnectionImpl26hookpointOnHeadersCompleteEi",
    "_ZN5Envoy7Network15RawBufferSocket15hookpointDoReadEil",
    "_ZN5Envoy7Network15RawBufferSocket16hookpointDoWriteEil"
]

hook_function_list = ["perform_read", "perform_write", "request_end", "http_parse_start", "filters_end", "upstream", "record_xid", "http_parsed", "perform_read", "perform_write"]

b = BPF(text=program)
binary_path = "/usr/local/bin/envoy"

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
            ("read_time", ctypes.c_ulonglong),
            ("write_time", ctypes.c_ulonglong),
            ("total_time", ctypes.c_ulonglong),
        ]
    event = ctypes.cast(data, ctypes.POINTER(ConnInfo)).contents
    x_request_id_str = event.x_request_id.split(b'\x00', 1)[0].decode(errors="replace")
    log_queue.put(f"Connection ID: {event.connection_id}, X-Request-ID: {x_request_id_str}, Time Start: {event.time_start}, Time HTTP Parsed: {event.time_http_parsed}, Time Filters End: {event.time_filters_end}, Upstream Time Start: {event.time_upstream_start}, Upstream Time HTTP Parsed: {event.time_upstream_http_parsed}, Time End: {event.time_end}, Read Time: {event.read_time}, Write Time: {event.write_time}, Total Time: {event.total_time}\n")

# ----------- register callbacks ------------------
b["trace_events"].open_perf_buffer(callback, page_cnt=256)

print("Tracing... Ctrl+C to stop.")
try:
    while True:
        b.perf_buffer_poll(timeout=5)
except KeyboardInterrupt:
    pass