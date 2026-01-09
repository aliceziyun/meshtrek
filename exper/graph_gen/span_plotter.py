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
            self.draw_interval(y=index, start=norm_span["conn"]["Read Ready Start Time"], end=norm_span["conn"]["Parse End Time"],
                    color=CONN_COLOR, height=0.8, alpha=CONN_ALPHA, zorder=0)

            self.draw_interval(y=index, start=norm_span["upstream_conn"]["Read Ready Start Time"], end=norm_span["upstream_conn"]["Parse End Time"],
                            color=CONN_COLOR, height=0.8, alpha=CONN_ALPHA, zorder=0)
            
            # 两个conn之间的时间绘制成？色，为虚拟的处理时间
            self.draw_interval(y=index, start=norm_span["conn"]["Parse End Time"], end=norm_span["upstream_conn"]["Read Ready Start Time"],
                            color=GAP_COLOR, height=0.8, alpha=GAP_ALPHA, zorder=0)
            
            # 处理parse time, 绘制成橘色
            self.draw_interval(y=index, start=norm_span["req"]["Header Parse Start Time"], end=norm_span["req"]["Header Parse End Time"],
                            color=PARSE_COLOR, height=0.8, alpha=PARSE_ALPHA, zorder=1)
            self.draw_interval(y=index, start=norm_span["req"]["Data Parse Start Time"], end=norm_span["req"]["Data Parse End Time"],
                            color=PARSE_COLOR, height=0.8, alpha=PARSE_ALPHA, zorder=1)
            self.draw_interval(y=index, start=norm_span["resp"]["Header Parse Start Time"], end=norm_span["resp"]["Header Parse End Time"],
                            color=PARSE_COLOR, height=0.8, alpha=PARSE_ALPHA, zorder=1)
            self.draw_interval(y=index, start=norm_span["resp"]["Data Parse Start Time"], end=norm_span["resp"]["Data Parse End Time"],
                            color=PARSE_COLOR, height=0.8, alpha=PARSE_ALPHA, zorder=1)
            self.draw_interval(y=index, start=norm_span["resp"]["Trailer Parse Start Time"], end=norm_span["resp"]["Trailer Parse End Time"],
                            color=PARSE_COLOR, height=0.8, alpha=PARSE_ALPHA, zorder=1)
            
            # 处理filter time，绘制成蓝色
            self.draw_interval(y=index, start=norm_span["req"]["Header Parse End Time"], end=norm_span["req"]["Data Parse Start Time"],
                            color=FILTER_COLOR, height=0.8, alpha=FILTER_ALPHA, zorder=1)
            self.draw_interval(y=index, start=norm_span["req"]["Data Parse End Time"], end=norm_span["req"]["Stream End Time"],
                            color=FILTER_COLOR, height=0.8, alpha=FILTER_ALPHA, zorder=1)
            self.draw_interval(y=index, start=norm_span["resp"]["Header Parse End Time"], end=norm_span["resp"]["Data Parse Start Time"],
                            color=FILTER_COLOR, height=0.8, alpha=FILTER_ALPHA, zorder=1)
            self.draw_interval(y=index, start=norm_span["resp"]["Data Parse End Time"], end=norm_span["resp"]["Trailer Parse Start Time"],
                            color=FILTER_COLOR, height=0.8, alpha=FILTER_ALPHA, zorder=1)
            self.draw_interval(y=index, start=norm_span["resp"]["Trailer Parse End Time"], end=norm_span["resp"]["Stream End Time"],
                            color=FILTER_COLOR, height=0.8, alpha=FILTER_ALPHA, zorder=1)
            
        plt.xlabel("Time (ms)")
        plt.ylabel("Spans (ordered by start time)")
        plt.title("Span Time Breakdown")
        plt.grid(axis='x', linestyle='--', alpha=0.7)
        plt.tight_layout()
        plt.show()
