class HTTP2Uprobe:
    program = r"""
    #include <uapi/linux/ptrace.h>
    struct request_info_t {
        char uber_id[17];
        u64 stream_id;

        u64 time_start;
        u64 time_request_filter_start;
        u64 time_process_start;
        u64 time_response_filter_start;
        u64 time_end;

        u64 upstream_time_http_parse_start;
        u64 upstream_time_end;
    }

    BPF_HASH(conn_stream_id_map, u64, struct request_info_t);
    // BPF_HASH(connection_stream_map, u32, u64);
    BPF_HASH(request_id_map, u64, struct request_info_t);

    BPF_PERF_OUTPUT(trace_events);

    // ConnectionImpl::Http2Visitor::OnBeginHeadersForStream <connection_id, tmp_stream_id>
    int request_and_http_parse_start(struct pt_regs *ctx) {
        u32 conn_id = PT_REGS_PARM2(ctx);
        u32 stream_id = PT_REGS_PARM3(ctx);
        u64 ts = bpf_ktime_get_tai_ns();

        u64 key = ((u64)conn_id << 32) | (u64)stream_id;
        struct request_info_t info = {};


        u64* p_stream_id = connection_stream_map.lookup(&connection_id);
        if(p_stream_id) {
            // use this stream_id to search for request_info_t  
            struct request_info_t *info = request_id_map.lookup(p_stream_id);
            if(info) {
                info->upstream_time_http_parse_start = ts;
            }
        }else{
            // create a new one
            struct request_info_t info = {};
            info.tmp_stream_id = tmp_stream_id;
            info.time_start = ts;

            stream_id_map.update(&tmp_stream_id, &info);
        }

        return 0;
    }

    // ConnectionImpl::Http2Visitor::OnEndHeadersForStream <connection_id, tmp_stream_id>
    int request_filter_start(struct pt_regs *ctx) {
        u32 connection_id = PT_REGS_PARM2(ctx);
        u32 tmp_stream_id = PT_REGS_PARM3(ctx);
        u64 ts = bpf_ktime_get_tai_ns();

        u64* p_stream_id = connection_stream_map.lookup(&connection_id);
        if(p_stream_id) {
            struct request_info_t *info = request_id_map.lookup(p_stream_id);
            if(info) {
                info->upstream_time_end = ts;
                connection_stream_map.delete(&connection_id);
            }
        } else{
            struct request_info_t *info = stream_id_map.lookup(&tmp_stream_id);
            if(info) {
                info->time_request_filter_start = ts;
            } else{
                // bpf_trace_printk("request_filter_start: not found tmp_stream_id %d\n", tmp_stream_id);
            }
        }

        return 0;
    }

    // ConnectionManagerImpl::ActiveStream::decodeHeaders <x_request_id, connection_id, stream_id>
    int process_start(struct pt_regs *ctx) {
        u64 stream_id = (u64)ctx->r8;
        int plain_stream_id = (u64)ctx->r9;
        struct request_info_t *info = stream_id_map.lookup(&plain_stream_id);
        if(info) {
            info->stream_id = stream_id;
            stream_id_map.delete(&plain_stream_id);
            request_id_map.update(&stream_id, info);

            const char* str = (const char *)PT_REGS_PARM2(ctx);
            u64 size = 16;
            bpf_probe_read_str(info->uber_id, sizeof(info->uber_id), str);
            info->uber_id[size] = '\0';
            info->time_process_start = bpf_ktime_get_tai_ns();
        } else{
            // bpf_trace_printk("process_start: not found stream_id %d\n", stream_id);
        }
        return 0;
    }

    // UpstreamRequest::decodeHeaders <upstream_connection_id, connection_id, stream_id>
    // TODO: I want to change this hookpoint to <upstream_id, stream_id>
    int response_filter_start(struct pt_regs *ctx) {
        u64 upstream_stream_id = (u64) PT_REGS_PARM2(ctx);
        u64 stream_id = (64) PT_REGS_PARM3(ctx);
        struct request_info_t *upstream_info = request_id_map.lookup(&upstream_stream_id);
        if(upstream_info) {
            struct request_info_t *info = request_id_map.lookup(&stream_id);
            if(info) {
                info->time_response_filter_start = bpf_ktime_get_tai_ns();

                info->upstream_time_http_parse_start = upstream_info->time_start;
                info->upstream_time_end = upstream_info->time_request_filter_start;

                request_id_map.delete(&upstream_stream_id);
            }
        } else{
            // bpf_trace_printk("response_filter_start: not found upstream_stream_id %d\n", upstream_stream_id);
        }
        return 0;
    }

    // ConnectionManagerImpl::ActiveStream::onCodecEncodeComplete <connection_id, stream_id>
    int request_end(struct pt_regs *ctx) {
        u64 stream_id = (u64) PT_REGS_PARM3(ctx);
        struct request_info_t *info = request_id_map.lookup(&stream_id);
        if(info) {
            info->time_end = bpf_ktime_get_tai_ns();
            trace_events.perf_submit(ctx, info, sizeof(*info));
            request_id_map.delete(&stream_id);
        } else{
            // bpf_trace_printk("request_end: not found stream_id %d\n", stream_id);
        }
        return 0;
    }
    """

    hook_symbol_list = [

    ]

    hook_function_list = ["request_and_http_parse_start",
                        "request_filter_start",
                        "associate_stream_id",
                        "process_start",
                        "response_filter_start",
                        "request_end"]