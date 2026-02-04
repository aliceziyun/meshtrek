import json
import os
import span_constant as span_constant

class SpanFormatter:
    def _write_results_to_file(self, processed):
        '''
        write spans and spans_meta to files
        '''
        print("[*] Writing all results to file...")
        # 写span数据
        output_path = os.path.join(self.output_dir, "formatted_spans_{}.json".format(processed))
        with open(output_path, 'a') as out_f:
            json.dump(self.spans, out_f)
            out_f.write('\n')
        # 写metadata数据
        output_meta_path = os.path.join(self.output_dir, "formatted_spans_meta_{}.json".format(processed))
        with open(output_meta_path, 'a') as out_f:
            json.dump(self.spans_meta, out_f)
            out_f.write('\n')
        self.spans = {}
        self.spans_meta = {}
    
    def _combine_connections(self, item, connections, upstream=False):
        """
        对于http1请求，可能存在多个connection entry，需要把connections进行合并，并把一些字段写入stream中
        """
        # 根据connection的Parse Start Time进行升序排序
        connections.sort(key=lambda c: c.get("Parse Start Time", float("inf")))
        # 将connection中的一些字段写入stream中
        for i, conn in enumerate(connections):
            if i == 0: # 这个connection是header connection
                if upstream == False:
                    item["req"]["Header Parse Start Time"] = conn["Parse Start Time"]
                else:
                    item["resp"]["Header Parse Start Time"] = conn["Parse Start Time"]
            if i == 1:
                if upstream == False:
                    item["req"]["Data Parse Start Time"] = conn["Parse Start Time"]
                else:
                    item["resp"]["Data Parse Start Time"] = conn["Parse Start Time"]
        # 合并connection，取最早的Parse Start Time和最晚的Parse End Time
        combined_conn = connections[0]
        combined_conn["Read Ready Start Time"] = min(conn["Read Ready Start Time"] for conn in connections)
        combined_conn["Parse End Time"] = max(conn["Parse End Time"] for conn in connections)
        if upstream:
            item["upstream_conn"] = combined_conn
        else:
            item["conn"] = combined_conn
    
    def _cal_wait_time(self, span):
        wait_time = 0.0
        wait_time += span["req"]["Header Parse Start Time"] - span["conn"]["Parse Start Time"]
        wait_time += span["conn"]["Parse End Time"] - span["req"]["Stream End Time"]
        wait_time += span["resp"]["Header Parse Start Time"] - span["upstream_conn"]["Parse Start Time"]
        wait_time += span["upstream_conn"]["Parse End Time"] - span["resp"]["Stream End Time"]
        if span["req"]["Data Parse Start Time"] != 0:
            wait_time += span["req"]["Data Parse Start Time"] - span["req"]["Header Process End Time"]
        if span["req"]["Trailer Parse Start Time"] != 0:
            wait_time += span["req"]["Trailer Parse Start Time"] - span["req"]["Data Process End Time"]
        return wait_time
    
    def _cal_parse_time(self, span):
        parse_time = 0.0
        parse_time += span["req"]["Header Filter Start Time"] - span["req"]["Header Parse Start Time"]
        if span["req"]["Data Parse Start Time"] != 0:
            parse_time += span["req"]["Data Filter Start Time"] - span["req"]["Data Parse Start Time"]
        parse_time += span["resp"]["Header Filter Start Time"] - span["resp"]["Header Parse Start Time"]
        if span["resp"]["Data Parse Start Time"] != 0:
            parse_time += span["resp"]["Data Filter Start Time"] - span["resp"]["Data Parse Start Time"]
        if span["resp"]["Trailer Parse Start Time"] != 0:
            parse_time += span["resp"]["Trailer Filter Start Time"] - span["resp"]["Trailer Parse Start Time"]
        return parse_time

    def _cal_filter_time(self, span):
        filter_time = 0.0
        filter_time += span["req"]["Header Process End Time"] - span["req"]["Header Filter Start Time"]
        if span["req"]["Data Parse Start Time"] != 0:
            filter_time += span["req"]["Stream End Time"] - span["req"]["Data Filter Start Time"]
        filter_time += span["resp"]["Header Process End Time"] - span["resp"]["Header Filter Start Time"]
        if span["resp"]["Data Parse Start Time"] != 0:
            filter_time += span["resp"]["Data Process End Time"] - span["resp"]["Data Filter Start Time"]
        if span["resp"]["Trailer Parse Start Time"] != 0:
            filter_time += span["resp"]["Stream End Time"] - span["resp"]["Trailer Filter Start Time"]
        return filter_time

    def _cal_times(self, span):
        wait_time = self._cal_wait_time(span)
        parse_time = self._cal_parse_time(span)
        filter_time = self._cal_filter_time(span)

        # TODO: deal with double counting in process_time
        process_time = span["upstream_conn"]["Read Ready Start Time"] - span["conn"]["Parse End Time"]

        return wait_time/1e6, parse_time/1e6, filter_time/1e6, process_time/1e6
    
    def _cal_times_layer(self, layer_services, type):
        '''
        计算当一层存在并行请求时的请求时延
        type: overhead / wait / parse / filter
        '''
        max_request_time = self._find_max_request_end_time(layer_services, type)
        max_request_time_no_mesh = self._find_max_request_end_time_no_mesh(layer_services)
        type_time = (max_request_time - max_request_time_no_mesh)/1e6
        return type_time

    def _find_max_request_end_time_no_mesh(self, layer_services):
        # 去除上半区overhead后的max end time
        # 公式：conn_Parse Start Time(开始时间) + upstream_Parse Start Time - conn_Parse End Time
        max_end_time = 0
        for trace in layer_services:
                conn = trace["conn"]
                upconn = trace["upstream_conn"]
                if upconn.get("Parse Start Time") is not None and conn.get("Parse End Time") is not None and conn.get("Parse Start Time") is not None:
                    max_end_time = max(max_end_time, conn["Parse Start Time"] + (upconn["Parse Start Time"] - conn["Parse End Time"]))
        return max_end_time

    def _find_max_request_end_time(self, layer_services, type):
        # 寻找最大的Parse End Time
        if type == "overhead":
            # 直接寻找最大的request end time即可
            max_end_time = 0.0
            for trace in layer_services:
                upconn = trace["upstream_conn"]
                if upconn.get("Parse End Time") is not None:
                    max_end_time = max(max_end_time, upconn["Parse End Time"])
            return max_end_time
        elif type == "wait":
            # 只保留wait time的情况下，寻找最大的request end time
            # 对于每个span，需要从connection end的时间中减去两部分
            # downstream的filter和parse time，以及upstream的filter和parse time
            max_end_time = 0.0
            for trace in layer_services:
                upconn = trace["upstream_conn"]
                if upconn.get("Parse End Time") is not None:
                    end_time = upconn.get("Parse End Time")
                    filter_time = self._cal_filter_time(trace)
                    parse_time = self._cal_parse_time(trace)
                    max_end_time = max(max_end_time, end_time - filter_time - parse_time)
            return max_end_time
        elif type == "parse":
            # 同理，需要减去wait和filter time
            max_end_time = 0.0
            for trace in layer_services:
                upconn = trace["upstream_conn"]
                if upconn.get("Parse End Time") is not None:
                    end_time = upconn.get("Parse End Time")
                    filter_time = self._cal_filter_time(trace)
                    wait_time = self._cal_wait_time(trace)
                    max_end_time = max(max_end_time, end_time - filter_time - wait_time)
            return max_end_time
        elif type == "filter":
            # 同理，需要减去parse和wait time
            max_end_time = 0.0
            for trace in layer_services:
                upconn = trace["upstream_conn"]
                if upconn.get("Parse End Time") is not None:
                    end_time = upconn.get("Parse End Time")
                    parse_time = self._cal_parse_time(trace)
                    wait_time = self._cal_wait_time(trace)
                    max_end_time = max(max_end_time, end_time - parse_time - wait_time)
            return max_end_time
        else:
            print("[!] Unsupported type")
            exit(1)
    
    def _calculate_request_time(self, request_traces):
        # 计算request_time, 最大的"Parse End Time"减去最小的"Header Parse Start Time"
        min_start_time = float('inf')
        max_end_time = 0.0
        for trace in request_traces:
            conn = trace["conn"]
            upconn = trace["upstream_conn"]
            if conn.get("Parse Start Time") is not None:
                min_start_time = min(min_start_time, conn["Parse Start Time"])
            if upconn.get("Parse End Time") is not None:
                max_end_time = max(max_end_time, upconn["Parse End Time"])

        request_time = (max_end_time - min_start_time)/1e6
        return request_time
    
    def _fill_topology(self, request_traces):
        '''
        使用request_traces中的service字段，从上到下填充拓扑结构
        拓扑文件的格式为：
        {
            "layer_number": ["service_1", "service_2", ...],
            ...
        }
        '''
        # read topology file
        service_topology = []   # 存储服务的拓扑顺序，二级列表
        request_traces_copied = request_traces.copy()

        with open(self.topology_path, 'r') as topo_f:
            topology = json.load(topo_f)
            # 遍历每一层
            for layer, services in topology.items():
                # 遍历request_traces，找到该层的service，对于同层的同名service，不需要注意顺序
                layer_services = []
                for service in services:
                    services_match = []
                    # 找到所有符合service name的trace，根据起始时间的顺序排序，选择最小的那个加入layer_services
                    for trace in request_traces_copied:
                        if trace["service"] == service:
                            services_match.append(trace)
                    # 找到起始时间最小的trace, 起始时间使用Parse Start Time
                    min_start_time = float('inf')
                    selected_trace = None
                    for svc in services_match:
                        conn = svc["conn"]
                        if conn.get("Parse Start Time") is not None and conn["Parse Start Time"] < min_start_time:
                            min_start_time = conn["Parse Start Time"]
                            selected_trace = svc
                    if selected_trace is not None:
                        layer_services.append(selected_trace)
                        request_traces_copied.remove(selected_trace)
                service_topology.append(layer_services)

        return service_topology
    
    def _merge_service_times(self, topologied_service):
        overhead = 0.0
        filter_time, parse_time, wait_time = 0.0, 0.0, 0.0

        # 合并每一层
        for layer_services in topologied_service:
            f, p, w, o = self._merge_layer(layer_services)
            filter_time += f
            parse_time += p
            wait_time += w
            overhead += o

        return filter_time, parse_time, wait_time, overhead

    def _merge_layer(self, layer_services):
        '''
        # TODO: 验证overhead是否等于f + p + w
        return f, p, w, overhead
        '''
        if len(layer_services) == 0:
            return 0.0, 0.0, 0.0, 0.0
        elif len(layer_services) == 1:
            f, p, w, _ = self._cal_times(layer_services[0])
            return f, p, w, f + p + w
        else:
            overhead = self._cal_times_layer(layer_services, type="overhead")
            f = self._cal_times_layer(layer_services, type="filter")
            p = self._cal_times_layer(layer_services, type="parse")
            w = self._cal_times_layer(layer_services, type="wait")
            # 判断f+p+w和overhead的误差是否可忽略
            # if abs((f + p + w) - overhead) / overhead > 0.1:
            #     print("[!] Warning: overhead time does not equal to f + p + w")
            #     print(f"Filter time: {f}, Parse time: {p}, Wait time: {w}, Overhead time: {overhead}, Sum: {f + p + w}")
            return f, p, w, overhead

    def _process_full_request(self, request_traces, request_len):
        metadata = {
            "total_sub_requests": request_len,
            "wait": 0.0,
            "parse": 0.0,
            "filter": 0.0,
            "overhead": 0.0,
            "request_time": 0.0,
        }

        # 计算request_time
        request_time = self._calculate_request_time(request_traces)

        wait_sum, parse_sum, filter_sum = 0.0, 0.0, 0.0

        if self.topology_path == "":
            for span in request_traces:
                w, p, f, _ = self._cal_times(span)
                wait_sum += w
                parse_sum += p
                filter_sum += f

            metadata["wait"] = wait_sum
            metadata["parse"] = parse_sum
            metadata["filter"] = filter_sum
            metadata["overhead"] = wait_sum + parse_sum + filter_sum
            metadata["request_time"] = request_time
        elif self.topology_path != "":
            # print("[*] In topology...")
            # 填充拓扑结构
            topologied_service = self._fill_topology(request_traces)

            # 从下到上merge时间
            f, p, w, o = self._merge_service_times(topologied_service)
            metadata["wait"] = w
            metadata["parse"] = p
            metadata["filter"] = f
            metadata["overhead"] = o
            metadata["request_time"] = request_time

        return metadata
    
    def _which_protocol(self, sub_request):
        if sub_request.get("Key") is not None:
            return span_constant.PROTOCOL_HTTP2
        else:
            return span_constant.PROTOCOL_HTTP1

    def _extract_stream(self, sub_request, protocol):
        # 假设是parse完立刻进入filter，中间的处理时间可以忽略
        if protocol == span_constant.PROTOCOL_HTTP2:
            key = sub_request.get("Key")
            connection_id = (key >> 32) & 0xffffffff
            plain_stream_id = key & 0xffffffff
            sub_request.pop("Key", None)
            sub_request["Connection ID"] = connection_id
            sub_request["Plain Stream ID"] = plain_stream_id

            # 进行一些特殊处理，确保http2和http1的字段一致
            sub_request["Header Filter Start Time"] = sub_request["Header Parse End Time"]
            sub_request.pop("Header Parse End Time", None)
            sub_request["Header Process End Time"] = sub_request["Data Parse Start Time"]
            sub_request["Data Filter Start Time"] = sub_request["Data Parse End Time"]
            sub_request.pop("Data Parse End Time", None)
            if sub_request["Trailer Parse Start Time"] != 0:
                sub_request["Data Process End Time"] = sub_request["Trailer Parse Start Time"]
            else:
                sub_request["Data Process End Time"] = sub_request["Stream End Time"]
            sub_request["Trailer Filter Start Time"] = sub_request["Trailer Parse End Time"]
            sub_request.pop("Trailer Parse End Time", None)
            return sub_request
        elif protocol == span_constant.PROTOCOL_HTTP1:
            sub_request["Plain Stream ID"] = 0
            sub_request["Trailer Parse Start Time"] = 0
            sub_request["Trailer Filter Start Time"] = 0

            #这两个字段之后用connection的数据来填
            sub_request["Header Parse Start Time"] = 0
            sub_request["Data Parse Start Time"] = 0

            sub_request["Header Process End Time"] = sub_request["Header Filter End Time"]
            sub_request.pop("Header Filter End Time", None)
            sub_request["Data Process End Time"] = sub_request["Data Filter End Time"]
            sub_request.pop("Data Filter End Time", None)
            return sub_request

    def _search_subrequests(self, file_lines, request_id):
        """
        在给定的文件内容中，搜索所有包含指定request id的记录
        返回这些记录的列表
        """
        sub_requests = []
        for line in file_lines:
            trace_data = json.loads(line)
            # 前16位match
            if trace_data.get("Request ID") and trace_data.get("Request ID")[:16] == request_id:
                sub_requests.append(trace_data)
        return sub_requests

    def _search_response(self, file_lines, stream_id, protocol):
        for line in file_lines:
            trace_data = json.loads(line)
            if trace_data.get("Stream ID") == stream_id and trace_data.get("Upstream Connection ID") != 0 and trace_data.get("Upstream Connection ID") is not None:
                return self._extract_stream(trace_data, protocol)
            
    def _search_connection(self, file_lines, connection_id, plain_stream_id, protocol, stream_id):
        # print(f"[*] Searching connection for connection id {connection_id}, plain stream id {plain_stream_id}, protocol {protocol}, stream id {stream_id}")

        def u64_to_u16_list(x):
            # tool function
            parts = [
                (x >> 48) & 0xffff,
                (x >> 32) & 0xffff,
                (x >> 16) & 0xffff,
                x & 0xffff,
            ]
            return [p for p in parts if p != 0]
        
        def is_in_stream_id_list(trace_data, target_plain_stream_id):
            stream_ids = trace_data.get("Stream IDs")
            if stream_ids is None:
                return False
            stream_id_list = u64_to_u16_list(stream_ids)
            if target_plain_stream_id in stream_id_list:
                return True
            
            # 再找extra stream id
            extra_stream_ids = trace_data.get("Stream IDs Extra")
            if extra_stream_ids is None:
                return False
            extra_stream_id_list = u64_to_u16_list(extra_stream_ids)
            if target_plain_stream_id in extra_stream_id_list:
                return True
            return False
        
        connections = []
        for line in file_lines:
            trace_data = json.loads(line)
            if trace_data.get("Connection ID") == connection_id:
                if protocol == span_constant.PROTOCOL_HTTP2:
                    if is_in_stream_id_list(trace_data, plain_stream_id):
                        return [trace_data] # http2只可能有一个connection entry（不完备，但目前实现如此）
                    
                elif protocol == span_constant.PROTOCOL_HTTP1:
                    # http1直接match stream id和connection id，但可能存在多个connection entry
                    # 选择connection，而不是stream
                    if trace_data.get("Stream ID") == stream_id and trace_data.get("Connection ID") == connection_id:
                        if trace_data.get("Parse Start Time") is not None:
                            connections.append(trace_data)
                            continue
        return connections

    def _search_other_entries(self, sub_request, file_lines, protocol):
        """
        返回：
            item{
                "req": {},
                "resp": {},
                "conn": {},
                "upstream_conn": {}
            }
        """
        item = {}
        # 在sub_request中提取req
        item["req"] = self._extract_stream(sub_request, protocol)
        request_id = item["req"]["Request ID"][:16]

        # search包含相同stream id的行，该行为resp
        stream_id = item["req"]["Stream ID"]
        item["resp"] = self._search_response(file_lines, stream_id, protocol)

        if item["resp"] is None:
            print(f"[!] Incomplete span (No Response) for stream id {request_id}")
            return None

        # search downstream connection
        connection_id = item["req"]["Connection ID"]
        downstream_plain_stream_id = item["req"]["Plain Stream ID"] # http1，此项为0
        stream_id = item["req"]["Stream ID"]
        request_id = item["req"]["Request ID"][:16]
        # print(f"[*] Searching downstream connection for request id {request_id}, connection id {connection_id}, plain stream id {downstream_plain_stream_id}, stream id {stream_id}")
        connections = self._search_connection(file_lines, connection_id, downstream_plain_stream_id, protocol, stream_id)
        if len(connections) == 0:
            print(f"[!] Incomplete span (No Connection) for stream id {request_id}")
            return None
        else:
            if protocol == span_constant.PROTOCOL_HTTP2:
                item["conn"] = connections[0]
            else:
                self._combine_connections(item, connections, upstream=False)

        # search upstream connection
        upstream_conn_id = item["resp"]["Upstream Connection ID"]
        upstream_plain_stream_id = item["resp"]["Plain Stream ID"]
        # print(f"[*] Searching upstream connection for request id {request_id}, upstream connection id {upstream_conn_id}, upstream plain stream id {upstream_plain_stream_id}, stream id {stream_id}")
        upstream_conns = self._search_connection(file_lines, upstream_conn_id, upstream_plain_stream_id, protocol, stream_id)
        if len(upstream_conns) == 0:
            print(f"[!] Incomplete span (No Upstream Connection) for stream id {request_id}")
            return None
        else:
            if protocol == span_constant.PROTOCOL_HTTP2:
                item["upstream_conn"] = upstream_conns[0]
            else:
                self._combine_connections(item, upstream_conns, upstream=True)

        # 验证完整性
        if item["req"] is None or item["resp"] is None or item["conn"] is None or item["upstream_conn"] is None:
            print(f"[!] Incomplete span (Missing Entry) for stream id {request_id}")
            return None

        # print(f"[*] Found complete span for stream id {request_id}")
        return item

    def format_span_file(self):
        """
        从entry file开始处理，读取每一行
        当遇到包含Request ID的行时，对该行进行处理
        1. 在目录中依次读取每一个文件，寻找包含该Request ID的行
        2. 对于每一个找到的行，在相同文件中找寻其另一半，即包含相同stream id的行，并标注其对应的是response还是request
        3. 对这些行，找寻其对应的connection。
            具体而言，request直接使用key的connection + plain stream id。response使用key的plain stream id和upstream connection id
        4. 将内容整合成一份记录，存入全局字典中
        """
        with open(self.entry_file, 'r') as ef:
            entry_lines = ef.readlines()
            for line in entry_lines:
                trace_data = json.loads(line)
                request_id = trace_data.get("Request ID")
                if request_id is None or request_id == "":
                    continue    # 不是stream记录，是connection，跳过该行

                request_id = request_id[:16]
                # print(f"[*] Processing request id: {request_id}")

                if self.span_processed.__contains__(request_id):
                    continue    # 已经处理过该request id，跳过
                
                # 开始搜索和该request id有关的所有记录
                self.spans[request_id] = []

                # 在当前file中搜索和request id的相关记录
                current_file = entry_lines
                current_service = os.path.basename(self.entry_file).split('_')[2].split('-')[0]     # TODO: 使用正则表达式匹配，这里提取的name不完整
                skip = False
                sub_requests = self._search_subrequests(current_file, request_id)
                for sub_request in sub_requests:
                    # 对于每一个sub_request，找寻其对应的其他entry

                    # 判断其是http1还是http2请求
                    protocol = self._which_protocol(sub_request)
                    item = self._search_other_entries(sub_request, current_file, protocol)
                    if item is None:    # 跳过该request id
                        skip = True
                        self.span_processed.add(request_id)
                        self.spans.pop(request_id, None)    # 删去entry
                        break
                    item["service"] = current_service
                    self.spans[request_id].append(item)

                if skip:
                    continue

                # 在其他file中搜索相关记录，每个记录对应4条信息
                for fname in os.listdir(self.data_dir):
                    fpath = os.path.join(self.data_dir, fname)
                    if fpath == self.entry_file:
                        continue    # 跳过entry file本身

                    # 选择.log结尾的文件
                    if not fname.endswith('.log'):
                        continue

                    with open(fpath, 'r') as f:
                        file_lines = f.readlines()
                        current_file = file_lines
                        current_service = os.path.basename(fpath).split('_')[2].split('-')[0]     # TODO: 使用正则表达式匹配，这里提取的name不完整
                        sub_requests = self._search_subrequests(current_file, request_id)
                        for sub_request in sub_requests:
                            protocol = self._which_protocol(sub_request)
                            item = self._search_other_entries(sub_request, current_file, protocol)
                            if item is None:
                                continue
                            item["service"] = current_service
                            self.spans[request_id].append(item)

                # 筛选长度符合的请求
                if len(self.spans[request_id]) != span_constant.TARGET_SPAN_LEN:
                    self.spans.pop(request_id, None)
                    self.span_processed.add(request_id)
                    continue

                # 处理该request id的记录，获取一些关于请求的元数据
                metadata = self._process_full_request(self.spans[request_id], len(self.spans[request_id]))
                self.spans_meta[request_id] = metadata

                # 标记该request id为已处理
                self.span_processed.add(request_id)
                
                self.processed += 1
                if self.processed % span_constant.WRITE_BATCH_SIZE == 0:
                    print(f"[*] Processed {self.processed} requests.")
                    self._write_results_to_file(self.processed)
        self._write_results_to_file(self.processed)
        print(f"[*] Finished processing all requests, results written to file in {self.output_dir}.")

    def __init__(self, dir, entry_file):
        self.data_dir = dir
        self.entry_file = os.path.join(dir, entry_file)

        self.spans = {} # for output result
        self.spans_meta = {}
        self.span_processed = set()
        self.processed = 0

        self.topology_path = "/Users/alicesong/Desktop/research/meshtrek/exper/graph_gen/topology/synthetic.json"       # for parallel
        # self.topology_path = ""

        self.output_dir = os.path.dirname(os.path.abspath(__file__))