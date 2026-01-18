class Http1Uprobe:
    program = r"""
    #include <uapi/linux/ptrace.h>
    struct conn_info_t {
        u32 connection_id;
        u64 stream_id;
        u64 write_ready_start_time;
        u64 read_ready_start_time;
        u64 parse_start_time;
        u64 parse_end_time;
    };  // struct conn_info_t, size: 60 bytes

    BPF_HASH(conn_info_map, u32, struct conn_info_t);   // key: connection_id -> conn_info_t
    BPF_PERF_OUTPUT(conn_events);

    struct stream_info_t {
        char request_id[32];
        u32 upstream_conn_id;
        u64 stream_id;
        u64 header_filter_start_time;
        u64 header_filter_end_time;
        u64 data_filter_start_time;
        u64 data_filter_end_time;
        u64 trailers_filter_start_time;
        u64 trailers_filter_end_time;
        u64 stream_end_time;
    };  // struct stream_info_t, size: 72 bytes

    BPF_HASH(stream_info_map, u32, struct stream_info_t);   // key: <connection_id> -> stream_info_t
    BPF_HASH(up_down_stream_map, u32, u32);    // key: <upstream connection id> -> <downstream connection id>
    BPF_PERF_OUTPUT(stream_events);

    // ConnectionImpl::onFileEvent <connection_id, type>
    int io_start(struct pt_regs *ctx) {
        u32 connection_id = PT_REGS_PARM2(ctx);
        u32 type = PT_REGS_PARM3(ctx);  // 2: write ready, 3: read ready
        struct conn_info_t *conn_info = conn_info_map.lookup(&connection_id);
        if(conn_info) {
            if(conn_info->parse_start_time != 0) {
                return 0;   // skip if parsing is ongoing
            }
            if(type == 2){
                conn_info->write_ready_start_time = bpf_ktime_get_tai_ns();
            }else if(type == 3){
                conn_info->read_ready_start_time = bpf_ktime_get_tai_ns();
            }
        }else{
            struct conn_info_t new_conn_info = {};
            new_conn_info.connection_id = connection_id;
            if(type == 2){
                new_conn_info.write_ready_start_time = bpf_ktime_get_tai_ns();
            }else if(type == 3){
                new_conn_info.read_ready_start_time = bpf_ktime_get_tai_ns();
            }
            conn_info_map.update(&connection_id, &new_conn_info);
        }
        return 0;
    }

    // ConnectionImpl::dispatch <connection_id>
    int parse_start(struct pt_regs *ctx) {
        u32 connection_id = PT_REGS_PARM2(ctx);
        struct conn_info_t *conn_info = conn_info_map.lookup(&connection_id);
        if(conn_info) {
            conn_info->parse_start_time = bpf_ktime_get_tai_ns();
        }
        return 0;
    }

    // ConnectionImpl::dispatch <connection_id>
    int parse_end(struct pt_regs *ctx) {
        u32 connection_id = PT_REGS_PARM2(ctx);
        struct conn_info_t *conn_info = conn_info_map.lookup(&connection_id);
        if(conn_info) {
            conn_info->parse_end_time = bpf_ktime_get_tai_ns();

            // find the stream id from stream_info_map
            struct stream_info_t *stream_info = stream_info_map.lookup(&connection_id);
            if(stream_info) {
                conn_info->stream_id = stream_info->stream_id;
                // submit conn info
                conn_events.perf_submit(ctx, conn_info, sizeof(*conn_info));
                if(stream_info->stream_end_time != 0) {
                    stream_info_map.delete(&connection_id);     // the stream is ended
                }
            } else{
                // the stream info maybe in the downstream connection map
                u32 *downstream_conn_id = up_down_stream_map.lookup(&connection_id);
                if(downstream_conn_id) {
                    struct stream_info_t *downstream_stream_info = stream_info_map.lookup(downstream_conn_id);
                    if(downstream_stream_info) {
                        conn_info->stream_id = downstream_stream_info->stream_id;
                        // submit conn info
                        conn_events.perf_submit(ctx, conn_info, sizeof(*conn_info));
                        if(downstream_stream_info->stream_end_time != 0) {
                            stream_info_map.delete(downstream_conn_id);
                            down_up_stream_map.delete(&connection_id);
                        }
                    }
                }
            }

            // delete information
            conn_info_map.delete(&connection_id);
        }
        return 0;
    }

    // ConnectionManagerImpl::ActiveStream::decodeHeaders <request_id, connection_id, plain_stream_id, stream_id>
    int header_filter_start_req(struct pt_regs *ctx) {
        const char *request_id_ptr = (const char *)PT_REGS_PARM2(ctx);
        u32 connection_id = PT_REGS_PARM4(ctx);
        u64 stream_id = (u64) ctx->r9;
        struct stream_info_t stream_info = {};

        // fill info with request id, stream id, and parse end time
        u32 size = 32;
        bpf_probe_read_str(&stream_info.request_id, size, request_id_ptr);
        stream_info.stream_id = stream_id;
        stream_info.header_filter_end_time = bpf_ktime_get_tai_ns();

        // update stream info map with stream id as key
        stream_info_map.update(&connection_id, &stream_info);
        
        return 0;
    }

    // UpstreamRequest::decodeHeaders <stream_id, upstream_conn_id, downstream_conn_id, plain_stream_id>
    int header_filter_start_resp(struct pt_regs *ctx) {
        u64 stream_id = PT_REGS_PARM2(ctx);
        u32 upstream_conn_id = PT_REGS_PARM3(ctx);
        u32 downstream_conn_id = PT_REGS_PARM4(ctx);

        stream_info_t stream_info = {};

        // fill info with upstream connection id, stream id, and parse end time
        stream_info.upstream_conn_id = upstream_conn_id;
        stream_info.stream_id = stream_id;
        stream_info.header_filter_end_time = bpf_ktime_get_tai_ns();
        // update stream info map with stream id as key
        stream_info_map.update(&downstream_conn_id, &stream_info);
        // update up_down_stream_map
        up_down_stream_map.update(&upstream_conn_id, &downstream_conn_id);

        return 0;
    }

    // ConnectionManagerImpl::ActiveStream::decodeHeaders <connection_id, stream_id>
    int header_filter_end_req(struct pt_regs *ctx) {
        u32 connection_id = PT_REGS_PARM2(ctx);
        u64 stream_id = PT_REGS_PARM3(ctx);
        struct stream_info_t *stream_info = stream_info_map.lookup(&connection_id);
        if(stream_info) {
            stream_info->header_filter_end_time = bpf_ktime_get_tai_ns();
        }
        return 0;
    }

    // ConnectionManagerImpl::ActiveStream::encodeHeaders <connection_id, stream_id>
    int header_filter_end_resp(struct pt_regs *ctx) {
        u32 connection_id = PT_REGS_PARM2(ctx);
        u64 stream_id = PT_REGS_PARM3(ctx);
        struct stream_info_t *stream_info = stream_info_map.lookup(&connection_id);
        if(stream_info) {
            stream_info->header_filter_end_time = bpf_ktime_get_tai_ns();
        }
        return 0;
    }

    // ConnectionManagerImpl::ActiveStream::decodeData <connection_id, stream_id>
    int data_filter_start_req(struct pt_regs *ctx) {
        u32 connection_id = PT_REGS_PARM2(ctx);
        u64 stream_id = PT_REGS_PARM3(ctx);
        struct stream_info_t *stream_info = stream_info_map.lookup(&connection_id);
        if(stream_info) {
            stream_info->data_parse_end_time = bpf_ktime_get_tai_ns();
        }
        return 0;
    }

    // ConnectionManagerImpl::ActiveStream::decodeData <connection_id, stream_id>
    int data_filter_end_req(struct pt_regs *ctx) {
        u32 connection_id = PT_REGS_PARM2(ctx);
        u64 stream_id = PT_REGS_PARM3(ctx);
        struct stream_info_t *stream_info = stream_info_map.lookup(&connection_id);
        if(stream_info) {
            stream_info->data_parse_end_time = bpf_ktime_get_tai_ns();
            stream_info->stream_end_time = bpf_ktime_get_tai_ns();
            // submit to user
            stream_events.perf_submit(ctx, stream_info, sizeof(*stream_info));
        }
        return 0;
    }

    // FilterManager::encodeData / FilterManager::encodeTrailer <connection_id, stream_id, type>
    int data_trailer_filter_start_resp(struct pt_regs *ctx) {
        u32 connection_id = PT_REGS_PARM2(ctx);
        u64 stream_id = PT_REGS_PARM3(ctx);
        u32 type = PT_REGS_PARM4(ctx);  // 1: data, 2: trailer
        struct stream_info_t *stream_info = stream_info_map.lookup(&connection_id);
        if(stream_info) {
            if(type == 1) {
                stream_info->data_filter_start_time = bpf_ktime_get_tai_ns();
            }else if(type == 2){
                stream_info->trailers_filter_start_time = bpf_ktime_get_tai_ns();
            }
        }
        return 0;
    }

    // FilterManager::encodeData / FilterManager::encodeTrailer <connection_id, stream_id, type>
    int data_trailer_filter_end_resp(struct pt_regs *ctx) {
        u32 connection_id = PT_REGS_PARM2(ctx);
        u64 stream_id = PT_REGS_PARM3(ctx);
        u32 type = PT_REGS_PARM4(ctx);  // 1: data, 2: trailer
        struct stream_info_t *stream_info = stream_info_map.lookup(&connection_id);
        if(stream_info) {
            if(type == 1) {
                stream_info->data_filter_end_time = bpf_ktime_get_tai_ns();
            }else if(type == 2){
                stream_info->trailers_filter_end_time = bpf_ktime_get_tai_ns();
            }
        }
        return 0;
    }

    // ConnectionManagerImpl::ActiveStream::onCodecEncodeComplete <connection_id, stream_id>
    int stream_end(struct pt_regs *ctx) {
        u32 connection_id = PT_REGS_PARM2(ctx);
        u64 stream_id = PT_REGS_PARM3(ctx);
        struct stream_info_t *stream_info = stream_info_map.lookup(&connection_id);
        if(stream_info) {
            stream_info->stream_end_time = bpf_ktime_get_tai_ns();
            // submit to user
            stream_events.perf_submit(ctx, stream_info, sizeof(*stream_info));
        }
        return 0;
    }
    """

    hook_symbol_list = [
        "_ZN5Envoy7Network14ConnectionImpl16hookpointIOReadyEij",
        "_ZN5Envoy4Http5Http114ConnectionImpl23http1_hookpointDispatchEi",
        "_ZN5Envoy4Http5Http114ConnectionImpl26http1_hookpointDispatchEndEi",
        "_ZN5Envoy4Http21ConnectionManagerImpl12ActiveStream36http1_hookpointHeaderFiltersStartReqENSt3__117basic_string_viewIcNS3_11char_traitsIcEEEEjm",
        "_ZN5Envoy6Router19UpstreamCodecFilter11CodecBridge37http1_hookpointHeaderFiltersStartRespEmjj",
        "_ZN5Envoy4Http21ConnectionManagerImpl12ActiveStream34http1_hookpointHeaderFiltersEndReqEjm",
        "_ZN5Envoy4Http21ConnectionManagerImpl12ActiveStream35http1_hookpointHeaderFiltersEndRespEjm",
        "_ZN5Envoy4Http21ConnectionManagerImpl12ActiveStream34http1_hookpointDataFiltersStartReqEjm",
        "_ZN5Envoy4Http21ConnectionManagerImpl12ActiveStream32http1_hookpointDataFiltersEndReqEjm",
        "_ZN5Envoy4Http13FilterManager33http1_hookpointXXFiltersStartRespEjmh",
        "_ZN5Envoy4Http13FilterManager33http1_hookpointXXFiltersEndRespEjmh",
        "_ZN5Envoy4Http21ConnectionManagerImpl12ActiveStream30http1_hookpointOnCodecEncodeCompleteEjm",
    ]

    hook_function_list = [
        "io_start",
        "parse_start",
        "parse_end",
        "header_filter_start_req",
        "header_filter_start_resp",
        "header_filter_end_req",
        "header_filter_end_resp",
        "data_filter_start_req",
        "data_filter_end_req",
        "data_trailer_filter_start_resp",
        "data_trailer_filter_end_resp",
        "stream_end",
    ]

    def __init__(self):
        pass