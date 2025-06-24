#!/usr/bin/python3  
from bcc import BPF
import ctypes
import time

program = r"""
#include <uapi/linux/ptrace.h>

struct data_t {
    u32 connection_id;
    u64 elapsed_time;
};

BPF_HASH(connection_id_map, u32, u64);  // <connection_id, time>
BPF_PERF_OUTPUT(events);

int hook_start(struct pt_regs *ctx) {
    // get the second parameter of the function
    u32 connection_id = PT_REGS_PARM2(ctx);
    u64 ts = bpf_ktime_get_ns();
    connection_id_map.update(&connection_id, &ts);
    return 0;
}

int hook_end(struct pt_regs *ctx) {
    u32 connection_id = PT_REGS_PARM2(ctx);
    u64 ts = bpf_ktime_get_ns();
    u64 *existing_ts = connection_id_map.lookup(&connection_id);
    if(existing_ts) {
        // send the elapsed time to userspace
        struct data_t data = {};
        data.connection_id = connection_id;
        data.elapsed_time = ts - *existing_ts;
        connection_id_map.delete(&connection_id);
        events.perf_submit(ctx, &data, sizeof(data));
        return 0;
    }else{
        // this should not happen, error
        bpf_trace_printk("Connection ID not found in map: %d\\n", connection_id);
        return 0;
    }
}
"""

symbol1 = "_ZN5Envoy4Http5Http114ConnectionImpl17hookpointDispatchEi"
symbol2 = "_ZN5Envoy4Http5Http114ConnectionImpl26hookpointOnHeadersCompleteEi"

b = BPF(text=program)
binary_path = "/usr/local/bin/envoy"
b.attach_uprobe(name=binary_path, sym=symbol1, fn_name="hook_start")
b.attach_uprobe(name=binary_path, sym=symbol2, fn_name="hook_end")

# register a callback when the perf event is triggered
def callback(cpu, data, size):
    class Data(ctypes.Structure):
        _fields_ = [("connection_id", ctypes.c_uint),
                    ("elapsed_time", ctypes.c_ulonglong)]
    event = ctypes.cast(data, ctypes.POINTER(Data)).contents
    print(f"Connection ID: {event.connection_id}, Elapsed Time: {event.elapsed_time} ns")
b["events"].open_perf_buffer(callback)

print("Tracing... Ctrl+C to stop.")
try:
    while True:
        b.perf_buffer_poll()
except KeyboardInterrupt:
    pass