import matplotlib.pyplot as plt
import json
import copy
import span_constant as span_constant

CONN_COLOR = "#E6E6E6"
CONN_ALPHA = 0.9

PARSE_COLOR = "#E69F00"
PARSE_ALPHA = 0.85

FILTER_COLOR = "#0072B2"
FILTER_ALPHA = 0.75

GAP_COLOR = "#56B4E9"
GAP_ALPHA = 0.35

class SpanPlotter:
    def __init__(self):
        self.norm_span = None

    def _normalize_spans(self, spans):
        all_ts = []
        norm_spans = []
        for span in spans:
            for comp in span_constant.COMPONENTS:
                obj = span.get(comp, {})
                for k in span_constant.TIME_FIELDS:
                    if k == "Write Ready Start Time":
                        continue
                    ts = obj.get(k, 0)
                    if ts > 0:
                        all_ts.append(ts)

        if not all_ts:
            print("[!] No valid timestamps found for normalization.")
            exit(1)

        t0 = min(all_ts)

        norm_spans = copy.deepcopy(spans)

        for span in norm_spans:
            for comp in span_constant.COMPONENTS:
                obj = span.get(comp, {})
                for k in span_constant.TIME_FIELDS:
                    if k in obj and obj[k] > 0:
                        obj[k] -= t0
                        obj[k] = obj[k] / 1e6
        
        norm_spans.sort(
            key=lambda s: s.get("req", {}).get("Header Parse Start Time", float("inf"))
        )

        return norm_spans
    
    def draw_interval(self, y, start, end, *, color, height, alpha, zorder, label=None):
        if end <= start:
            print("[!] End time is less than the start time")
            exit(1)
        plt.barh(y=y, width=end - start, left=start, height=height, color=color, alpha=alpha, zorder=zorder, label=label)

    def read_data(self, file_path, request_id):
        # 从json文件中读取span数据，一个大的json文件，先读"spans"，然后读"request-id"对应的list
        with open(file_path, 'r') as f:
            data = json.load(f)
        spans = data.get(request_id, [])
        return spans

    def plot_span(self, spans):
        norm_spans = self._normalize_spans(spans)

        for i, span in enumerate(norm_spans):
            index = len(norm_spans) - i - 1
            norm_span = span
            # 处理conn time, 绘制成灰色
            self.draw_interval(y=index, start=norm_span["conn"]["Read Ready Start Time"], end=norm_span["conn"]["Parse End Time"],
                    color=CONN_COLOR, height=0.8, alpha=CONN_ALPHA, zorder=0)

            self.draw_interval(y=index, start=norm_span["upstream_conn"]["Read Ready Start Time"], end=norm_span["upstream_conn"]["Parse End Time"],
                            color=CONN_COLOR, height=0.8, alpha=CONN_ALPHA, zorder=0)
            
            # 两个conn之间的时间绘制成？色，为虚拟的处理时间
            self.draw_interval(y=index, start=norm_span["conn"]["Parse End Time"], end=norm_span["upstream_conn"]["Read Ready Start Time"],
                            color=GAP_COLOR, height=0.8, alpha=GAP_ALPHA, zorder=0)
            
            # 处理parse time, 绘制成橘色
            self.draw_interval(y=index, start=norm_span["req"]["Header Parse Start Time"], end=norm_span["req"]["Header Filter Start Time"],
                            color=PARSE_COLOR, height=0.8, alpha=PARSE_ALPHA, zorder=1)
            if norm_span["req"]["Data Parse Start Time"] != 0:
                self.draw_interval(y=index, start=norm_span["req"]["Data Parse Start Time"], end=norm_span["req"]["Data Filter Start Time"],
                                color=PARSE_COLOR, height=0.8, alpha=PARSE_ALPHA, zorder=1)
            self.draw_interval(y=index, start=norm_span["resp"]["Header Parse Start Time"], end=norm_span["resp"]["Header Filter Start Time"],
                            color=PARSE_COLOR, height=0.8, alpha=PARSE_ALPHA, zorder=1)
            if norm_span["resp"]["Data Parse Start Time"] != 0:
                self.draw_interval(y=index, start=norm_span["resp"]["Data Parse Start Time"], end=norm_span["resp"]["Data Filter Start Time"],
                                color=PARSE_COLOR, height=0.8, alpha=PARSE_ALPHA, zorder=1)
            if norm_span["resp"]["Trailer Parse Start Time"] != 0:
                self.draw_interval(y=index, start=norm_span["resp"]["Trailer Parse Start Time"], end=norm_span["resp"]["Trailer Filter Start Time"],
                                color=PARSE_COLOR, height=0.8, alpha=PARSE_ALPHA, zorder=1)
            
            # 处理filter time，绘制成蓝色
            self.draw_interval(y=index, start=norm_span["req"]["Header Filter Start Time"], end=norm_span["req"]["Header Process End Time"],
                            color=FILTER_COLOR, height=0.8, alpha=FILTER_ALPHA, zorder=1)
            if norm_span["req"]["Data Parse Start Time"] != 0:
                self.draw_interval(y=index, start=norm_span["req"]["Data Filter Start Time"], end=norm_span["req"]["Data Process End Time"],
                                color=FILTER_COLOR, height=0.8, alpha=FILTER_ALPHA, zorder=1)
            self.draw_interval(y=index, start=norm_span["resp"]["Header Filter Start Time"], end=norm_span["resp"]["Header Process End Time"],
                            color=FILTER_COLOR, height=0.8, alpha=FILTER_ALPHA, zorder=1)
            if norm_span["resp"]["Data Parse Start Time"] != 0:
                self.draw_interval(y=index, start=norm_span["resp"]["Data Filter Start Time"], end=norm_span["resp"]["Data Process End Time"],
                                color=FILTER_COLOR, height=0.8, alpha=FILTER_ALPHA, zorder=1)
            if norm_span["resp"]["Trailer Parse Start Time"] != 0:
                self.draw_interval(y=index, start=norm_span["resp"]["Trailer Filter Start Time"], end=norm_span["resp"]["Stream End Time"],
                                color=FILTER_COLOR, height=0.8, alpha=FILTER_ALPHA, zorder=1)
            
        plt.xlabel("Time (ms)")
        plt.ylabel("Spans (ordered by start time)")
        plt.title("Span Time Breakdown")
        plt.grid(axis='x', linestyle='--', alpha=0.7)
        plt.tight_layout()
        plt.show()

    def plot_dist_graph(self, span_meta, dist_type, length):
        # filter by request length
        span_meta = [(request_id, meta) for request_id, meta in span_meta.items() if meta.get("total_sub_requests", 0) == length]
        
        ratios = []
        color = ""
        for _, meta in span_meta:
            # calculate the ratio of the dist_type time to the total request time
            if dist_type == "filter":
                color = "#FF5722"
                ratios.append(meta.get("filter", 0) / meta.get("request_time", 1))
            elif dist_type == "wait":
                color = "#2196F3"
                ratios.append(meta.get("wait", 0) / meta.get("request_time", 1))
            elif dist_type == "parse":
                color = "#4CAF50"
                ratios.append(meta.get("parse", 0) / meta.get("request_time", 1))
            elif dist_type == "overhead":
                color = "#9C27B0"
                ratios.append(meta.get("overhead", 0) / meta.get("request_time", 1))
        
        plt.figure(figsize=(10, 6))
        plt.hist(ratios, bins=30, color=color, alpha=0.7)
        plt.xlabel(f"{dist_type.capitalize()} Ratio in Request Time")
        plt.ylabel("Frequency")
        plt.title(f"Distribution of {dist_type.capitalize()} Time Ratio in Request Time for Requests of Length {length}")
        plt.grid()
        plt.tight_layout()
        plt.savefig(f"{dist_type}_dist_len_{length}.png")
        plt.show()