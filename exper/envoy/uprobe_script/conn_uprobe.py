class ConnUprobe:
    program = r"""
    #include <uapi/linux/ptrace.h>
    struct conn_info_t {
        u32 connection_id;
        u32 position;       // current position in the stream id list
        u64 stream_id;      // a list, max 4 stream ids
        u64 stream_id_extra; // the number of stream ids might exceed 4
        u64 write_ready_start_time;
        u64 read_ready_start_time;
        u64 parse_start_time;
        u64 parse_end_time;
    };  // struct conn_info_t, size: 56 bytes

    BPF_HASH(conn_info_map, u32, struct conn_info_t);
    BPF_PERF_OUTPUT(conn_events);

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
            // submit to user
            if(conn_info->position != 0) {     // only submit when there is stream id
                conn_events.perf_submit(ctx, conn_info, sizeof(*conn_info));
            }
            // delete information
            conn_info_map.delete(&connection_id);
        }
        return 0;
    }

    // Http2Visitor::OnHeaders <connection_id, plain_stream_id>
    int record_stream(struct pt_regs *ctx) {
        u32 connection_id = PT_REGS_PARM2(ctx);
        u16 plain_stream_id = (u16) PT_REGS_PARM3(ctx);
        struct conn_info_t *conn_info = conn_info_map.lookup(&connection_id);
        if(conn_info) {
            u32 pos = conn_info->position;
            if(pos < 4) {
                // store stream id
                u64 stream_id = conn_info->stream_id;
                stream_id |= ((u64)plain_stream_id) << (pos * 16);
                conn_info->stream_id = stream_id;
                conn_info->position = pos + 1;
            }else{
                // the list is full, save the stream id in stream id extra list
                u64 stream_id_extra = conn_info->stream_id_extra;
                stream_id_extra |= ((u64)plain_stream_id) << ((pos - 4) * 16);
                conn_info->stream_id_extra = stream_id_extra;
                conn_info->position = pos + 1;
            }
        }
        return 0;
    }
    """

    hook_symbol_list = [
        "_ZN5Envoy7Network14ConnectionImpl16hookpointIOReadyEij",
        "_ZN5Envoy4Http5Http214ConnectionImpl28http2_hookpointDispatchStartEj",
        "_ZN5Envoy4Http5Http214ConnectionImpl26http2_hookpointDispatchEndEj",
        "_ZN5Envoy4Http5Http214ConnectionImpl27http2_hookpointRecordStreamEjj"
    ]

    hook_function_list = [
        "io_start",
        "parse_start",
        "parse_end",
        "record_stream"
    ]

    def __init__(self):
        pass