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
    
    def _combine_connections(item, connections):
        pass

    def _cal_times(self, span):
        wait_time, parse_time, filter_time, process_time = 0, 0, 0, 0
        # 计算span的各个时间
        wait_time += span["req"]["Header Parse Start Time"] - span["conn"]["Read Ready Start Time"]
        wait_time += span["conn"]["Parse End Time"] - span["req"]["Stream End Time"]
        wait_time += span["resp"]["Header Parse Start Time"] - span["upstream_conn"]["Read Ready Start Time"]
        wait_time += span["upstream_conn"]["Parse End Time"] - span["resp"]["Stream End Time"]
        if span["req"]["Data Parse Start Time"] != 0:
            wait_time += span["req"]["Data Parse Start Time"] - span["req"]["Header Process End Time"]
        if span["req"]["Trailer Parse Start Time"] != 0:
            wait_time += span["req"]["Trailer Parse Start Time"] - span["req"]["Data Process End Time"]

        parse_time += span["req"]["Header Filter Start Time"] - span["req"]["Header Parse Start Time"]
        if span["req"]["Data Parse Start Time"] != 0:
            parse_time += span["req"]["Data Filter Start Time"] - span["req"]["Data Parse Start Time"]
        parse_time += span["resp"]["Header Filter Start Time"] - span["resp"]["Header Parse Start Time"]
        if span["resp"]["Data Parse Start Time"] != 0:
            parse_time += span["resp"]["Data Filter Start Time"] - span["resp"]["Data Parse Start Time"]
        if span["resp"]["Trailer Parse Start Time"] != 0:
            parse_time += span["resp"]["Trailer Filter Start Time"] - span["resp"]["Trailer Parse Start Time"]

        filter_time += span["req"]["Header Process End Time"] - span["req"]["Header Filter Start Time"]
        if span["req"]["Data Parse Start Time"] != 0:
            filter_time += span["req"]["Stream End Time"] - span["req"]["Data Filter Start Time"]
        filter_time += span["resp"]["Header Process End Time"] - span["resp"]["Header Filter Start Time"]
        if span["resp"]["Data Parse Start Time"] != 0:
            filter_time += span["resp"]["Data Process End Time"] - span["resp"]["Data Filter Start Time"]
        if span["resp"]["Trailer Parse Start Time"] != 0:
            filter_time += span["resp"]["Stream End Time"] - span["resp"]["Trailer Filter Start Time"]

        # TODO: deal with double counting in process_time
        process_time = span["upstream_conn"]["Read Ready Start Time"] - span["conn"]["Parse End Time"]

        return wait_time/1e6, parse_time/1e6, filter_time/1e6, process_time/1e6
    
    def _calculate_request_time(self, request_traces):
        # 计算request_time, 最大的"Stream End Time"减去最小的"Header Parse Start Time"
        min_start_time = float('inf')
        max_end_time = 0.0
        for trace in request_traces:
            req = trace["req"]
            resp = trace["resp"]
            if req.get("Header Parse Start Time") is not None:
                min_start_time = min(min_start_time, req["Header Parse Start Time"])
            if resp.get("Stream End Time") is not None:
                max_end_time = max(max_end_time, resp["Stream End Time"])

        request_time = (max_end_time - min_start_time)/1e6
        return request_time

    def _process_full_request(self, request_traces):
        metadata = {
            "total_sub_requests": len(request_traces),
            "wait": 0.0,
            "parse": 0.0,
            "filter": 0.0,
            "overhead": 0.0,
            "request_time": 0.0,
        }

        wait_sum = parse_sum = filter_sum = 0.0
        request_time = self._calculate_request_time(request_traces)
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
            if trace_data.get("Stream ID") == stream_id and trace_data.get("Upstream Connection ID") != 0:
                return self._extract_stream(trace_data, protocol)
            
    def _search_connection(self, file_lines, connection_id, plain_stream_id, protocol, stream_id):

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
                    # http1直接match stream id，但可能存在多个connection entry
                    if trace_data.get("Stream ID") == stream_id:
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
            print(f"[!] Incomplete span for stream id {request_id}")
            return None

        # search downstream connection
        connection_id = item["req"]["Connection ID"]
        downstream_plain_stream_id = item["req"]["Plain Stream ID"] # http1，此项为0
        stream_id = item["req"]["Stream ID"]
        connections = self._search_connection(file_lines, connection_id, downstream_plain_stream_id, protocol, stream_id)
        if len(connections) == 0:
            print(f"[!] Incomplete span for stream id {request_id}")
            return None
        if len(connections) == 1:
            item["conn"] = connections[0]
        else:
            # TODO:需要把connection进行合并，还需要把一些字段写入stream中
            self._combine_connections(item, connections)
            exit(1)

        # search upstream connection
        upstream_conn_id = item["resp"]["Upstream Connection ID"]
        upstream_plain_stream_id = item["resp"]["Plain Stream ID"]
        upstream_conns = self._search_connection(file_lines, upstream_conn_id, upstream_plain_stream_id, protocol, stream_id)
        if len(upstream_conns) == 0:
            print(f"[!] Incomplete span for stream id {request_id}")
            return None
        if len(upstream_conns) == 1:
            item["upstream_conn"] = upstream_conns[0]
        else:
            # TODO:需要把connection进行合并，还需要把一些字段写入stream中
            self._combine_connections(item, connections)
            exit(1)

        # 验证完整性
        if item["req"] is None or item["resp"] is None or item["conn"] is None or item["upstream_conn"] is None:
            print(f"[!] Incomplete span for stream id {request_id}")
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

                if request_id in self.spans:
                    continue    # 已经处理过该request id，跳过
                
                # 开始搜索和该request id有关的所有记录
                self.spans[request_id] = []

                # 在当前file中搜索和request id的相关记录
                current_file = entry_lines
                skip = False
                sub_requests = self._search_subrequests(current_file, request_id)
                for sub_request in sub_requests:
                    # 对于每一个sub_request，找寻其对应的其他entry

                    # 判断其是http1还是http2请求
                    protocol = self._which_protocol(sub_request)
                    item = self._search_other_entries(sub_request, current_file, protocol)
                    if item is None:    # 跳过该request id
                        skip = True
                        self.spans.pop(request_id, None)    # 删去entry
                        break
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
                        sub_requests = self._search_subrequests(current_file, request_id)
                        for sub_request in sub_requests:
                            protocol = self._which_protocol(sub_request)
                            item = self._search_other_entries(sub_request, current_file, protocol)
                            if item is None:
                                continue
                            self.spans[request_id].append(item)

                # 处理该request id的记录，获取一些关于请求的元数据
                metadata = self._process_full_request(self.spans[request_id])
                self.spans_meta[request_id] = metadata
                
                self.processed += 1
                if self.processed % 500 == 0:
                    print(f"[*] Processed {self.processed} requests.")
                    self._write_results_to_file(self.processed)
        self._write_results_to_file(self.processed)
        print(f"[*] Finished processing all requests, results written to file in {self.output_dir}.")

    def __init__(self, dir, entry_file):
        self.data_dir = dir
        self.entry_file = os.path.join(dir, entry_file)

        self.spans = {} # for output result
        self.spans_meta = {}
        self.processed = 0

        self.output_dir = os.path.dirname(os.path.abspath(__file__))