class HttpUprobe:
    program = r"""
    #include <uapi/linux/ptrace.h>
    struct connection_info_t {
        char x_request_id[40];
        u32 connection_id;
        u32 upstream_id;
        u64 time_start;
        u64 time_http_parsed;
        u64 time_request_filters_end;
        u64 time_upstream_recorded;
        u64 time_end;

        u64 upstream_time_start;
        u64 upstream_time_http_parsed;
    };

    BPF_HASH(connection_id_map, u32, struct connection_info_t);
    BPF_PERF_OUTPUT(trace_events);

    int http_parse_start(struct pt_regs *ctx) {
        u32 connection_id = PT_REGS_PARM2(ctx);
        u64 ts = bpf_ktime_get_tai_ns();

        struct connection_info_t info = {};
        info.connection_id = connection_id;
        info.time_start = ts;

        connection_id_map.update(&connection_id, &info);

        return 0;
    }

    int http_parse_end(struct pt_regs *ctx) {
        u32 connection_id = PT_REGS_PARM2(ctx);
        u64 ts = bpf_ktime_get_tai_ns();
        
        struct connection_info_t *info = connection_id_map.lookup(&connection_id);
        if (info) {
            info->time_http_parsed = ts;
        }

        return 0;
    }

    int filters_end(struct pt_regs *ctx) {
        u32 connection_id = PT_REGS_PARM4(ctx);
        struct connection_info_t *info = connection_id_map.lookup(&connection_id);
        if (info) {
            const char* str = (const char *)PT_REGS_PARM2(ctx);

            u64 size = 36; // we know its 36 bytes
            bpf_probe_read_str(info->x_request_id, sizeof(info->x_request_id), str);
            info->x_request_id[size] = '\0';
            info->time_request_filters_end = bpf_ktime_get_tai_ns();

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
        "_ZN5Envoy4Http5Http114ConnectionImpl17hookpointDispatchEi",
        "_ZN5Envoy4Http5Http114ConnectionImpl26hookpointOnHeadersCompleteEi",
        "_ZN5Envoy6Router15UpstreamRequest17hookpointUpstreamEiim",
        "_ZN5Envoy4Http21ConnectionManagerImpl12ActiveStream19hookpointFiltersEndENSt3__117basic_string_viewIcNS3_11char_traitsIcEEEEim",
        "_ZN5Envoy4Http21ConnectionManagerImpl12ActiveStream30hookpointOnCodecEncodeCompleteEim",
    ]

    hook_function_list = ["http_parse_start", "http_parse_end", "upstream", "filters_end", "request_end"]