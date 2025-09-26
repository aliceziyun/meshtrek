class HttpUprobe:
    program = r"""
    #include <uapi/linux/ptrace.h>
    struct request_info_t {
        char request_id[37];

        u64 time_http_start;
        u64 time_request_filters_start;
        u64 time_process_start;
        u64 time_response_filters_start;
        u64 time_end;

        u64 upstream_time_http_start;
    }

    BPF_HASH(request_map, u64, struct request_info_t);
    BPF_HASH(unique_stream_id_map, u32, u64);  // used for http2 to find upstream
    BPF_PERF_OUTPUT(trace_events);

    // ConnectionImpl::dispatch <connection_id>
    int http1_parse_start(struct pt_regs *ctx) {
        u32 connection_id = PT_REGS_PARM2(ctx);
        u64 ts = bpf_ktime_get_tai_ns();

        struct request_info_t info = {};
        info.time_http_start = ts;
        request_map.update(&info.key, &info);

        return 0;
    }

    // ConnectionImpl::Http2Visitor::OnBeginHeadersForStream <connection_id, plain_stream_id>
    int http2_parse_start(struct pt_regs *ctx) {
        u32 connection_id = PT_REGS_PARM2(ctx);
        u32 plain_stream_id = PT_REGS_PARM3(ctx);
        u64 ts = bpf_ktime_get_tai_ns();

        u64 key = ((u64)plain_stream_id << 32) | ((u64)connection_id);
        struct request_info_t info = {};
        info.time_http_start = ts;
        request_map.update(&key, &info);

        return 0;
    }

    // Http::ConnectionManagerImpl::ActiveStream::decodeHeaders <connection_id, plain_stream_id, stream_id>
    int request_filter_start(struct pt_regs *ctx) {
        u32 connection_id = PT_REGS_PARM2(ctx);
        u32 plain_stream_id = PT_REGS_PARM3(ctx);
        u64 stream_id = PT_REGS_PARM4(ctx);
        u64 ts = bpf_ktime_get_tai_ns();

        u64 key = ((u64)plain_stream_id << 32) | ((u64)connection_id);
        struct request_info_t *info = request_map.lookup(&key);
        if (info) {
            info->time_request_filters_start = ts;
            // for http2, we need to map stream_id to request_info_t
            request_map.update(&stream_id, info);
            request_map.delete(&key);
        } else {
            // bpf_trace_printk("Request info not found in map for key: %llu\\n", key);
        }

        return 0;
    }

    // Http::ConnectionManagerImpl::ActiveStream::decodeHeaders <stream_id, x_request_id>
    int process_start(struct pt_regs *ctx) {
        u64 stream_id = PT_REGS_PARM2(ctx);
        const char* str = (const char *)PT_REGS_PARM3(ctx);
        u64 ts = bpf_ktime_get_tai_ns();
        struct request_info_t *info = request_map.lookup(&stream_id);
        if (info) {
            u64 size = 36;
            bpf_probe_read_str(info->request_id, size, str);
            info->request_id[size] = '\0';
            info->time_process_start = ts;
        } else {
            // bpf_trace_printk("Request info not found in map for stream_id: %llu\\n", stream_id);
        }

        return 0;
    }

    // Somewhere <conenction_id, plain_stream_id, unique_stream_id>
    int record_unique_stream_id(struct pt_regs *ctx) {
        u32 connection_id = PT_REGS_PARM2(ctx);
        u32 plain_stream_id = PT_REGS_PARM3(ctx);
        u64 unique_stream_id = PT_REGS_PARM4(ctx);

        u64 key = ((u64)plain_stream_id << 32) | ((u64)connection_id);
        unique_stream_id_map.update(&key, &unique_stream_id);
        return 0;
    }

    // UpstreamRequest::decodeHeaders <stream_id, upstream_connection_id>
    int http1_response_filter_start(struct pt_regs *ctx) {
        u32 upstream_connection_id = PT_REGS_PARM2(ctx);
        u64 stream_id = (u64) PT_REGS_PARM3(ctx);
        u64 ts = bpf_ktime_get_tai_ns();

        struct request_info_t *upstream_info = request_map.lookup(&upstream_connection_id);
        if (upstream_info) {
            struct request_info_t *info = request_map.lookup(&stream_id);
            if (info) {
                info->time_response_filters_start = ts;
                info->upstream_time_http_start = upstream_info->time_http_start;
            }
            request_map.delete(&upstream_connection_id);
        } else {
            // bpf_trace_printk("Request info not found in map for connection_id: %llu\\n", stream_id);
        }
        return 0;
    }


    // UpstreamRequest::decodeHeaders <stream_id, unique_stream_id>
    int http2_response_filter_start(struct pt_regs *ctx) {
        u64 stream_id = (u64) PT_REGS_PARM2(ctx);
        u32 unique_stream_id = (u32) PT_REGS_PARM3(ctx);
        u64 ts = bpf_ktime_get_tai_ns();

        u64* key = unique_stream_id_map.lookup(&unique_stream_id);
        if (key) {
            struct request_info_t *upstream_info = request_map.lookup(key);
            if (upstream_info) {
                struct request_info_t *info = request_map.lookup(&stream_id);
                if (info) {
                    info->time_response_filters_start = ts;
                    info->upstream_time_http_start = upstream_info->time_http_start;
                }
                request_map.delete(key);
            } else {
                // bpf_trace_printk("Upstream request info not found in map for key: %llu\\n", *key);
            }
            unique_stream_id_map.delete(&unique_stream_id);
        }
        return 0;
    }

    // ConnectionManagerImpl::ActiveStream::onCodecEncodeComplete() <stream_id>
    int request_end(struct pt_regs *ctx) {
        u64 stream_id = (u64) PT_REGS_PARM2(ctx);
        u64 ts = bpf_ktime_get_tai_ns();

        struct request_info_t *info = request_map.lookup(&stream_id);
        if (info) {
            info->time_end = ts;
            trace_events.perf_submit(ctx, info, sizeof(*info));
            request_map.delete(&stream_id);
        } else {
            // bpf_trace_printk("Request info not found in map for stream_id: %llu\\n", stream_id);
        }

        return 0;
    }
    """

    hook_symbol_list = [
        "_ZN5Envoy4Http5Http114ConnectionImpl17hookpointDispatchEi",
        "_ZN5Envoy4Http5Http214ConnectionImpl12Http2Visitor32hookpointOnBeginHeadersForStreamEjj",
        "_ZN5Envoy4Http21ConnectionManagerImpl12ActiveStream21hookpointFiltersStartEiim",
        "_ZN5Envoy4Http21ConnectionManagerImpl12ActiveStream19hookpointFiltersEndENSt3__117basic_string_viewIcNS3_11char_traitsIcEEEEm",
        "_ZN5Envoy4Http5Http214ConnectionImpl16ClientStreamImpl29hookpointRecordUniqueStreamIdEjji",
        "_ZN5Envoy6Router15UpstreamRequest22hookpointUpstreamHttp1Emj",
        "_ZN5Envoy6Router15UpstreamRequest22hookpointUpstreamHttp2Emi",
        "_ZN5Envoy4Http21ConnectionManagerImpl12ActiveStream30hookpointOnCodecEncodeCompleteEm"
    ]

    hook_function_list = [
        "http1_parse_start", "http2_parse_start", "request_filter_start", "process_start",
        "record_unique_stream_id", "http1_response_filter_start", "http2_response_filter_start", "request_end"
    ]

    def __init__(self):
        pass