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

        u64 write_start_time;
        u64 write_end_time;
        u64 read_start_time;
        u64 read_end_time;
    };

    struct IO_info_t {
        u32 downstream_conn_id;

        u64 write_start_time;
        u64 write_end_time;
        u64 read_start_time;
        u64 read_end_time;
    };

    BPF_HASH(request_map, u64, struct request_info_t);
    BPF_HASH(unique_stream_id_map, u64, u64);  // used for http2 to find upstream
    BPF_HASH(conn_map, u64, struct IO_info_t);   // used for IO conenction id to find stream id
    BPF_PERF_OUTPUT(trace_events);

    // ConnectionImpl::dispatch <connection_id>
    int http1_parse_start(struct pt_regs *ctx) {
        u32 connection_id = PT_REGS_PARM2(ctx);
        u64 key = (u64) connection_id;
        u64 ts = bpf_ktime_get_tai_ns();

        struct request_info_t info = {};
        info.time_http_start = ts;
        request_map.update(&key, &info);

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

    // UpstreamRequest::onPoolReady <protocol, upstream_conn_id, unique_stream_id>
    int bind_downstream_upstream(struct pt_regs *ctx) {
        u32 protocol = PT_REGS_PARM2(ctx);
        u32 upstream_conn_id = PT_REGS_PARM3(ctx);
        u64 unique_stream_id = PT_REGS_PARM4(ctx);

        struct IO_info_t io_info = {};

        if(protocol == 1) {     // Http 1
            u64 key = (u64) upstream_conn_id;
            conn_map.update(&key, &io_info);
        } else if(protocol == 2) {  // Http 2
            conn_map.update(&unique_stream_id, &io_info);
        }
        return 0;
    }

    // Http::ConnectionManagerImpl::ActiveStream::decodeHeaders <x_request_id, stream_id>
    int process_start(struct pt_regs *ctx) {
        u64 stream_id = PT_REGS_PARM4(ctx);
        const char* str = (const char *)PT_REGS_PARM2(ctx);
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

    // ConnectionImpl::ClientStreamImpl::decodeHeaders() <conenction_id, plain_stream_id, unique_stream_id>
    int record_unique_stream_id(struct pt_regs *ctx) {
        u32 connection_id = PT_REGS_PARM2(ctx);
        u32 plain_stream_id = PT_REGS_PARM3(ctx);
        u64 unique_stream_id = PT_REGS_PARM4(ctx);

        u64 key = ((u64)plain_stream_id << 32) | ((u64)connection_id);
        unique_stream_id_map.update(&unique_stream_id, &key);
        return 0;
    }

    // IoResult RawBufferSocket::doRead() / IoResult RawBufferSocket::doWrite() <type, upstream_connection_id>
    int IO_start(struct pt_regs *ctx) {
        u32 type = PT_REGS_PARM2(ctx);  // 1: read, 2: write
        u32 upstream_connection_id = PT_REGS_PARM3(ctx);
        u64 unique_stream_id = PT_REGS_PARM4(ctx);
        u64 ts = bpf_ktime_get_tai_ns();
        if(unique_stream_id == 0) {
            u64 key = (u64) upstream_connection_id;
            struct IO_info_t *io_info = conn_map.lookup(&key);
            if (io_info) {
                if (type == 1) {
                    io_info->read_start_time = ts;      // only record the last read start time
                } else if (type == 2) {
                    if(io_info->write_end_time == 0) {
                        io_info->write_start_time = ts;     // only record the first write start time
                    }
                }
            }
        }else{
            struct IO_info_t *io_info = conn_map.lookup(&unique_stream_id);
            if (io_info) {
                if (type == 1) {
                    io_info->read_start_time = ts;     // only record the last read start time
                } else if (type == 2) {
                    if(io_info->write_end_time == 0) {
                        io_info->write_start_time = ts;     // only record the first write start time
                    }
                }
            }
        }
        
        return 0;
    }

    // IoResult RawBufferSocket::doRead() / IoResult RawBufferSocket::doWrite() <type, upstream_connection_id, unique_stream_id>
    int IO_end(struct pt_regs *ctx) {
        u32 type = PT_REGS_PARM2(ctx);  // 1: read, 2: write
        u32 upstream_connection_id = PT_REGS_PARM3(ctx);
        u64 unique_stream_id = PT_REGS_PARM4(ctx);
        u64 ts = bpf_ktime_get_tai_ns();
        if(unique_stream_id == 0) {
            u64 key = (u64) upstream_connection_id;
            struct IO_info_t *io_info = conn_map.lookup(&key);
            if (io_info) {
                if (type == 1) {
                    io_info->read_end_time = ts;
                } else if (type == 2) {
                    if(io_info->write_end_time == 0) {      // record the first write end time
                        io_info->write_end_time = ts;
                    }
                }
            }
            return 0;
        }else{
            struct IO_info_t *io_info = conn_map.lookup(&unique_stream_id);
            if (io_info) {
                if (type == 1) {
                    io_info->read_end_time = ts;
                } else if (type == 2) {
                    if(io_info->write_end_time == 0) {      // record the first write end time
                        io_info->write_end_time = ts;
                    }
                }
            }
        }
        
        return 0;
    }

    // UpstreamRequest::decodeHeaders <stream_id, upstream_connection_id>
    int http1_response_filter_start(struct pt_regs *ctx) {
        u32 upstream_connection_id = PT_REGS_PARM3(ctx);
        u64 key = (u64) upstream_connection_id;
        u64 stream_id = (u64) PT_REGS_PARM2(ctx);
        u64 ts = bpf_ktime_get_tai_ns();

        struct request_info_t *upstream_info = request_map.lookup(&key);
        u64 upstream_id = (u64) upstream_connection_id;
        if (upstream_info) {
            struct request_info_t *info = request_map.lookup(&stream_id);
            if (info) {
                info->time_response_filters_start = ts;
                info->upstream_time_http_start = upstream_info->time_http_start;

                // get IO info
                struct IO_info_t *io_info = conn_map.lookup(&upstream_id);
                if (io_info) {
                    info->write_start_time = io_info->write_start_time;
                    info->write_end_time = io_info->write_end_time;
                    info->read_start_time = io_info->read_start_time;
                    info->read_end_time = io_info->read_end_time;
                }
            }
            request_map.delete(&key);
        } else {
            // bpf_trace_printk("Request info not found in map for connection_id: %llu\\n", stream_id);
        }
        conn_map.delete(&upstream_id);
        return 0;
    }


    // UpstreamRequest::decodeHeaders <stream_id, unique_stream_id, upstream_connection_id>
    int http2_response_filter_start(struct pt_regs *ctx) {
        u64 stream_id = (u64) PT_REGS_PARM2(ctx);
        u64 unique_stream_id = (u64) PT_REGS_PARM3(ctx);
        u32 upstream_connection_id = (u32) PT_REGS_PARM4(ctx);
        u64 ts = bpf_ktime_get_tai_ns();

        u64* key = unique_stream_id_map.lookup(&unique_stream_id);
        if (key) {
            struct request_info_t *upstream_info = request_map.lookup(key);
            if (upstream_info) {
                struct request_info_t *info = request_map.lookup(&stream_id);
                if (info) {
                    info->time_response_filters_start = ts;
                    info->upstream_time_http_start = upstream_info->time_http_start;

                    // get IO info
                    struct IO_info_t *io_info = conn_map.lookup(&unique_stream_id);
                    if (io_info) {
                        info->write_start_time = io_info->write_start_time;
                        info->write_end_time = io_info->write_end_time;
                        info->read_start_time = io_info->read_start_time;
                        info->read_end_time = io_info->read_end_time;
                    } else {
                        // bpf_trace_printk("IO info not found in map for unique_stream_id: %llu\\n", unique_stream_id);
                    }
                }
                request_map.delete(key);
            } else {
                // bpf_trace_printk("Upstream request info not found in map for key: %llu\\n", *key);
            }
            unique_stream_id_map.delete(&unique_stream_id);
            conn_map.delete(&unique_stream_id);
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
        "_ZN5Envoy4Http5Http214ConnectionImpl16ClientStreamImpl29hookpointRecordUniqueStreamIdEjjm",
        "_ZN5Envoy6Router15UpstreamRequest22hookpointUpstreamHttp1Emj",
        "_ZN5Envoy6Router15UpstreamRequest22hookpointUpstreamHttp2Emmj",
        "_ZN5Envoy4Http21ConnectionManagerImpl12ActiveStream30hookpointOnCodecEncodeCompleteEm",
        "_ZN5Envoy6Router15UpstreamRequest23hookpointUpstreamCreateEjjm",
        "_ZN5Envoy7Network14ConnectionImpl16hookpointIOReadyEijm",
        "_ZN5Envoy7Network14ConnectionImpl14hookpointIOEndEijm"
    ]

    hook_function_list = [
        "http1_parse_start", "http2_parse_start", "request_filter_start", "process_start",
        "record_unique_stream_id", "http1_response_filter_start", "http2_response_filter_start", "request_end",
        "bind_downstream_upstream", "IO_start", "IO_end"
    ]

    def __init__(self):
        pass