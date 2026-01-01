import json
import os

class SpanFormatter:
    def _write_results_to_file(self):
        print("[*] Writing all results to file...")
        # 写span数据
        output_path = os.path.join(self.output_dir, "formatted_spans.json")
        with open(output_path, 'a') as out_f:
            json.dump({
                "spans": self.spans,
            }, out_f, indent=4)
        # 写metadata数据
        output_meta_path = os.path.join(self.output_dir, "formatted_spans_meta.json")
        with open(output_meta_path, 'a') as out_f:
            json.dump({
                "spans_meta": self.spans_meta
            }, out_f, indent=4)
        self.spans = {}
        self.spans_meta = {}

    def _process_full_request(self, request_traces):
        """
        metadata = {
            "total_sub_requests": int,
            "request_time": float
        }
        """
        metadata = {
            "total_sub_requests": len(request_traces),
            "request_time": 0.0,
        }
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

        # 转换成ms
        metadata["request_time"] = (max_end_time - min_start_time)/1e6
        return metadata

    def _extract_stream(self, sub_request):
        key = sub_request.get("Key")
        connection_id = (key >> 32) & 0xffffffff
        plain_stream_id = key & 0xffffffff
        sub_request.pop("Key", None)
        sub_request["Connection ID"] = connection_id
        sub_request["Plain Stream ID"] = plain_stream_id
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

    def _search_response(self, file_lines, stream_id):
        for line in file_lines:
            trace_data = json.loads(line)
            if trace_data.get("Stream ID") == stream_id and trace_data.get("Upstream Connection ID") != 0:
                return self._extract_stream(trace_data)
            
    def _search_connection(self, file_lines, connection_id, plain_stream_id):

        def u64_to_u16_list(x):
            # tool function
            parts = [
                (x >> 48) & 0xffff,
                (x >> 32) & 0xffff,
                (x >> 16) & 0xffff,
                x & 0xffff,
            ]
            return [p for p in parts if p != 0]
        
        for line in file_lines:
            trace_data = json.loads(line)
            if trace_data.get("Connection ID") == connection_id:
                stream_ids = trace_data.get("Stream IDs")
                if stream_ids == None:
                    continue

                stream_id_list = u64_to_u16_list(stream_ids)
                if plain_stream_id in stream_id_list:
                    return trace_data

    def _search_other_entries(self, sub_request, file_lines):
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
        item["req"] = self._extract_stream(sub_request)
        request_id = item["req"]["Request ID"][:16]

        # search包含相同stream id的行，该行为resp
        stream_id = item["req"]["Stream ID"]
        item["resp"] = self._search_response(file_lines, stream_id)

        if item["resp"] is None:
            print(f"[!] Incomplete span for stream id {request_id}")
            return None

        # search connection
        connection_id = item["req"]["Connection ID"]
        downstream_plain_stream_id = item["req"]["Plain Stream ID"]
        item["conn"] = self._search_connection(file_lines, connection_id, downstream_plain_stream_id)

        # search upstream connection
        upstream_conn_id = item["resp"]["Upstream Connection ID"]
        upstream_plain_stream_id = item["resp"]["Plain Stream ID"]
        item["upstream_conn"] = self._search_connection(file_lines, upstream_conn_id, upstream_plain_stream_id)

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

                # 在当前file中搜索相关记录，每个记录对应4条信息
                current_file = entry_lines
                skip = False
                sub_requests = self._search_subrequests(current_file, request_id)
                for sub_request in sub_requests:
                    item = self._search_other_entries(sub_request, current_file)
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

                    with open(fpath, 'r') as f:
                        file_lines = f.readlines()
                        current_file = file_lines
                        sub_requests = self._search_subrequests(current_file, request_id)
                        for sub_request in sub_requests:
                            item = self._search_other_entries(sub_request, current_file)
                            if item is None:
                                continue
                            self.spans[request_id].append(item)

                # 处理该request id的记录，获取一些关于请求的元数据
                metadata = self._process_full_request(self.spans[request_id])
                self.spans_meta[request_id] = metadata
                
                self.processed += 1
                if self.processed % 50 == 0:
                    print(f"[*] Processed {self.processed} requests.")
                    self._write_results_to_file()
        self._write_results_to_file()
        print(f"[*] Finished processing all requests, results written to file in {self.output_dir}.")

    def __init__(self, dir, entry_file):
        self.data_dir = dir
        self.entry_file = os.path.join(dir, entry_file)

        self.spans = {} # for output result
        self.spans_meta = {}
        self.processed = 0

        self.output_dir = os.path.dirname(os.path.abspath(__file__))