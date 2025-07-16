#!/usr/bin/python3
from bcc import BPF
import ctypes

# warning: real total time = read time + write time + total time

program = r"""
#include <uapi/linux/ptrace.h>
struct connection_info_t {
    char x_request_id[40];
    u32 connection_id;
    u32 upstream_id;
    u64 read_time;
    u64 write_time;
    u64 total_time;
};

BPF_HASH(connection_id_map, u32, struct connection_info_t);  // <connection_id, time>
BPF_PERF_OUTPUT(end_events);

// hook read
int perform_read(struct pt_regs *ctx) {
    u32 connection_id = PT_REGS_PARM2(ctx);
    u64 bytes_read = PT_REGS_PARM3(ctx);
    u64 ts = bpf_ktime_get_ns();

    struct connection_info_t* info = connection_id_map.lookup(&connection_id);
    if (info) {
        if(bytes_read == -1) {
            info->read_time = ts;
        }else if(bytes_read == 0){
            info->total_time = info->total_time + ts - info->read_time;
            info->read_time = 0;
        }else {
            info->read_time = ts - info->read_time;
        }
        connection_id_map.update(&connection_id, info);
        
        bpf_trace_printk("Read operation for connection ID: %d, bytes_read = %llu \n", connection_id, bytes_read);
    } else {
        // create a new entry if it doesn't exist
        struct connection_info_t new_info = {};
        new_info.connection_id = connection_id;
        new_info.read_time = ts;
        new_info.write_time = 0;
        new_info.total_time = 0;
        new_info.upstream_id = 0;
        connection_id_map.update(&connection_id, &new_info);

        bpf_trace_printk("New connection ID: %d, initialized with time: %llu ns\\n", connection_id, ts);
    }

    return 0;
}

// hook write
int perform_write(struct pt_regs *ctx) {
    u32 connection_id = PT_REGS_PARM2(ctx);
    u64 bytes_write = PT_REGS_PARM3(ctx);
    u64 ts = bpf_ktime_get_ns();

    struct connection_info_t* info = connection_id_map.lookup(&connection_id);
    if (info) {
        if(bytes_write == -1) {
            info->write_time = ts;
            connection_id_map.update(&connection_id, info);
        }else if(bytes_write == 0){
            info->total_time = info->total_time + ts - info->write_time;
            info->write_time = 0;
        }else{
            info->write_time = ts - info->write_time;
            connection_id_map.update(&connection_id, info);

            // has read time as a pair
            if(info->read_time != 0) {
                // the first write after the upstream connection, commmit it
                if(info->upstream_id != 0) {
                    bpf_trace_printk("Commit connection info for connection ID: %d\n", connection_id);

                    // commit this info to the end_events
                    end_events.perf_submit(ctx, info, sizeof(*info));
                }

                // remove the connection info from the map
                connection_id_map.delete(&connection_id);
                return 0;
            }

            bpf_trace_printk("Write operation for connection ID: %d, bytes_write = %llu \n", connection_id, bytes_write);
        }
    } else {
        // create a new entry if it doesn't exist
        struct connection_info_t new_info = {};
        new_info.connection_id = connection_id;
        new_info.write_time = ts;
        new_info.read_time = 0;
        new_info.total_time = 0;
        new_info.upstream_id = 0;
        connection_id_map.update(&connection_id, &new_info);

        bpf_trace_printk("New connection ID: %d, initialized with time: %llu ns\\n", connection_id, ts);
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

        bpf_trace_printk("X-Request-ID for connection ID: %d is %s\\n", connection_id, info->x_request_id);

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
        // Find upstream info in the map
        struct connection_info_t *upstream_info = connection_id_map.lookup(&upstream_id);
        if (upstream_info) {
            info->total_time = info->total_time + upstream_info->read_time + upstream_info->write_time + upstream_info->total_time;
            info->upstream_id = upstream_id;

            // remove upstream connection info from the map
            connection_id_map.delete(&upstream_id);

            bpf_trace_printk("Upstream connection ID: %d, Downstream connection ID: %d\\n", upstream_id, downstream_id);
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
"""
# --------------- add hook function --------------------
hook_do_read_symbol = "_ZN5Envoy7Network15RawBufferSocket15hookpointDoReadEil"
hook_do_write_symbol = "_ZN5Envoy7Network15RawBufferSocket16hookpointDoWriteEil"
hook_ssl_do_read_symbol = "_ZN5Envoy10Extensions16TransportSockets3Tls9SslSocket18hookpointSslDoReadEil"
hook_ssl_do_write_symbol = "_ZN5Envoy10Extensions16TransportSockets3Tls9SslSocket19hookpointSslDoWriteEil"
hook_decode_headers_symbol = "_ZN5Envoy6Router6Filter22hookpointDecodeHeadersENSt3__117basic_string_viewIcNS2_11char_traitsIcEEEEim"
hook_upstream_symbol = "_ZN5Envoy6Router15UpstreamRequest17hookpointUpstreamEiim"

b = BPF(text=program)
binary_path = "/usr/local/bin/envoy"
b.attach_uprobe(name=binary_path, sym=hook_do_read_symbol, fn_name="perform_read")
b.attach_uprobe(name=binary_path, sym=hook_do_write_symbol, fn_name="perform_write")
b.attach_uprobe(name=binary_path, sym=hook_ssl_do_read_symbol, fn_name="perform_read")
b.attach_uprobe(name=binary_path, sym=hook_ssl_do_write_symbol, fn_name="perform_write")
b.attach_uprobe(name=binary_path, sym=hook_decode_headers_symbol, fn_name="record_xid")
b.attach_uprobe(name=binary_path, sym=hook_upstream_symbol, fn_name="record_upstream_connection_map")

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

def end_callback(cpu, data, size):
    class ConnInfo(ctypes.Structure):
        _fields_ = [
            ("x_request_id", ctypes.c_char * 40),
            ("connection_id", ctypes.c_uint),
            ("upstream_id", ctypes.c_uint),
            ("read_time", ctypes.c_ulonglong),
            ("write_time", ctypes.c_ulonglong),
            ("total_time", ctypes.c_ulonglong),
        ]
    event = ctypes.cast(data, ctypes.POINTER(ConnInfo)).contents
    x_request_id_str = event.x_request_id.split(b'\x00', 1)[0].decode(errors="replace")
    total_time = event.read_time + event.write_time + event.total_time
    log_queue.put(f"Connection ID: {event.connection_id}, X-Request-ID: {x_request_id_str}, Elapsed Time: {total_time} ns\n")

# ----------- register callbacks ------------------
b["end_events"].open_perf_buffer(end_callback, page_cnt=256)

print("Tracing... Ctrl+C to stop.")
try:
    while True:
        b.perf_buffer_poll(timeout=10)
except KeyboardInterrupt:
    pass