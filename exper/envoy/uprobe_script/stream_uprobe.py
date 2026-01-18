class StreamUprobe:
    program = r"""
    #include <uapi/linux/ptrace.h>
    struct stream_info_t {
        u64 key;        // <connection id, plain stream id>
        char request_id[32];
        u32 upstream_conn_id;
        u64 stream_id;
        u64 header_parse_start_time;
        u64 header_parse_end_time;
        u64 data_parse_start_time;
        u64 data_parse_end_time;
        u64 trailers_parse_start_time;
        u64 trailers_parse_end_time;
        u64 stream_end_time;
    };  // struct stream_info_t, size: 80 bytes

    BPF_HASH(stream_info_map, u64, struct stream_info_t);
    BPF_HASH(stream_key_map, u64, u64);     // <connection id, plain stream id> -> stream id
    BPF_PERF_OUTPUT(stream_events);

    // ConnectionImpl::Http2Visitor::OnBeginXXForStream <connection id, plain stream id, type>
    int parse_start(struct pt_regs *ctx) {
        u32 connection_id = PT_REGS_PARM2(ctx);
        u32 plain_stream_id = PT_REGS_PARM3(ctx);
        u32 type = PT_REGS_PARM4(ctx);  // 0: header or trailer, 1: data
        u64 key = ((u64)connection_id << 32) | (u64)plain_stream_id;
        u64 *stream_id = stream_key_map.lookup(&key);
        if(stream_id) {
            struct stream_info_t *stream_info = stream_info_map.lookup(stream_id);
            if(stream_info) {
                if(type == 0) {  // only trailer
                    stream_info->trailers_parse_start_time = bpf_ktime_get_tai_ns();
                }else if(type == 1){
                    stream_info->data_parse_start_time = bpf_ktime_get_tai_ns();
                }
            }
        }else{   // only possible is header and first time see the stream
            struct stream_info_t new_stream_info = {};
            new_stream_info.key = key;
            if(type == 0) {
                new_stream_info.header_parse_start_time = bpf_ktime_get_tai_ns();
            }
            stream_info_map.update(&key, &new_stream_info);
        }
        return 0;
    }

    // ConnectionManagerImpl::ActiveStream::decodeHeaders <request_id, connection_id, plain_stream_id, stream_id>
    int header_parse_end_req(struct pt_regs *ctx) {
        const char *request_id_ptr = (const char *)PT_REGS_PARM2(ctx);
        u32 connection_id = PT_REGS_PARM4(ctx);
        u32 plain_stream_id = (u32) ctx->r8;
        u64 stream_id = (u64) ctx->r9;
        u64 key = ((u64)connection_id << 32) | (u64)plain_stream_id;
        struct stream_info_t *stream_info = stream_info_map.lookup(&key);
        if(stream_info) {
            // fill info with request id, stream id, and parse end time
            u32 size = 32;
            bpf_probe_read_str(&stream_info->request_id, size, request_id_ptr);
            stream_info->stream_id = stream_id;
            stream_info->header_parse_end_time = bpf_ktime_get_tai_ns();
            // update stream info map with stream id as key
            stream_info_map.update(&stream_id, stream_info);
            stream_info_map.delete(&key);
            // update stream key map
            stream_key_map.update(&key, &stream_id);
        }
        return 0;
    }

    // UpstreamRequest::decodeHeaders <stream_id, upstream_conn_id, downstream_conn_id, plain_stream_id>
    int header_parse_end_resp(struct pt_regs *ctx) {
        u64 stream_id = PT_REGS_PARM2(ctx);
        u32 upstream_conn_id = PT_REGS_PARM3(ctx);
        u32 downstream_conn_id = PT_REGS_PARM4(ctx);
        u32 plain_stream_id = (u32) ctx->r8;
        u64 key = ((u64)upstream_conn_id << 32) | (u64)plain_stream_id;
        struct stream_info_t *stream_info = stream_info_map.lookup(&key);
        if(stream_info) {
            // fill info with upstream connection id, stream id, and parse end time
            stream_info->upstream_conn_id = upstream_conn_id;
            stream_info->stream_id = stream_id;
            stream_info->header_parse_end_time = bpf_ktime_get_tai_ns();
            // update stream info map with stream id as key
            stream_info_map.update(&stream_id, stream_info);
            stream_info_map.delete(&key);
            // update stream key map
            stream_key_map.update(&key, &stream_id);
        }
        return 0;
    }

    // ConnectionManagerImpl::ActiveStream::decodeData <connection id, stream_id>
    int data_parse_end_req(struct pt_regs *ctx) {
        u32 connection_id = PT_REGS_PARM2(ctx);
        u64 stream_id = PT_REGS_PARM3(ctx);
        struct stream_info_t *stream_info = stream_info_map.lookup(&stream_id);
        if(stream_info) {
            stream_info->data_parse_end_time = bpf_ktime_get_tai_ns();
        }
        return 0;
    }

    // ConnectionManagerImpl::ActiveStream::decodeData <connection id, stream_id>
    int stream_end_req(struct pt_regs *ctx) {
        u32 connection_id = PT_REGS_PARM2(ctx);
        u64 stream_id = PT_REGS_PARM3(ctx);
        struct stream_info_t *stream_info = stream_info_map.lookup(&stream_id);
        if(stream_info) {
            stream_info->stream_end_time = bpf_ktime_get_tai_ns();
            // submit to user
            stream_events.perf_submit(ctx, stream_info, sizeof(*stream_info));
            // delete information
            stream_info_map.delete(&stream_id);
            // also delete from stream key map
            stream_key_map.delete(&stream_info->key);
        }
        return 0;
    }

    // FilterManager::encodeData <connection id, stream_id, type>
    int data_trailer_parse_end_resp(struct pt_regs *ctx) {
        u32 connection_id = PT_REGS_PARM2(ctx);
        u64 stream_id = PT_REGS_PARM3(ctx);
        u32 type = PT_REGS_PARM4(ctx);  // 1: data, 2: trailer
        struct stream_info_t *stream_info = stream_info_map.lookup(&stream_id);
        if(stream_info) {
            if(type == 1) {
                if(stream_info->data_parse_end_time == 0){    // only record first time
                    stream_info->data_parse_end_time = bpf_ktime_get_tai_ns();
                }
            }else if(type == 2){
                if(stream_info->trailers_parse_end_time == 0){
                    stream_info->trailers_parse_end_time = bpf_ktime_get_tai_ns();
                }
            }
        }
        return 0;
    }

    // ConnectionManagerImpl::ActiveStream::onCodecEncodeComplete <connection id, stream_id>
    int stream_end_resp(struct pt_regs *ctx) {
        u32 connection_id = PT_REGS_PARM2(ctx);
        u64 stream_id = PT_REGS_PARM3(ctx);
        struct stream_info_t *stream_info = stream_info_map.lookup(&stream_id);
        if(stream_info) {
            stream_info->stream_end_time = bpf_ktime_get_tai_ns();
            // submit to user
            stream_events.perf_submit(ctx, stream_info, sizeof(*stream_info));
            // delete information
            stream_info_map.delete(&stream_id);
            // also delete from stream key map
            stream_key_map.delete(&stream_info->key);
        }
        return 0;
    }
    """

    hook_symbol_list = [
        "_ZN5Envoy4Http5Http214ConnectionImpl12Http2Visitor22hookpointOnXXForStreamEjjh",
        "_ZN5Envoy4Http21ConnectionManagerImpl12ActiveStream30hookpointHeaderFiltersStartReqENSt3__117basic_string_viewIcNS3_11char_traitsIcEEEEjjm",
        "_ZN5Envoy6Router19UpstreamCodecFilter11CodecBridge31hookpointHeaderFiltersStartRespEmjjj",
        "_ZN5Envoy4Http21ConnectionManagerImpl12ActiveStream28hookpointDataFiltersStartReqEjm",
        "_ZN5Envoy4Http21ConnectionManagerImpl12ActiveStream29hookpointRequestFiltersEndReqEjm",
        "_ZN5Envoy4Http13FilterManager27hookpointXXFiltersStartRespEjmh",
        "_ZN5Envoy4Http21ConnectionManagerImpl12ActiveStream30hookpointOnCodecEncodeCompleteEjm"
    ]

    hook_function_list = [
        "parse_start",
        "header_parse_end_req",
        "header_parse_end_resp",
        "data_parse_end_req",
        "stream_end_req",
        "data_trailer_parse_end_resp",
        "stream_end_resp",
    ]

    def __init__(self):
        pass