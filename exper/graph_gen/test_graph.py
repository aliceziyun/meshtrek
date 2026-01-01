import matplotlib.pyplot as plt
import json
import copy

TIME_FIELDS = [
    "Header Parse Start Time",
    "Header Parse End Time",
    "Data Parse Start Time",
    "Data Parse End Time",
    "Trailer Parse Start Time",
    "Trailer Parse End Time",
    "Stream End Time",
    "Read Ready Start Time",
    "Write Ready Start Time",
    "Parse Start Time",
    "Parse End Time",
]

COMPONENTS = ["req", "resp", "conn", "upstream_conn"]

CONN_COLOR = "#E6E6E6"     # very light gray
CONN_ALPHA = 0.9

PARSE_COLOR = "#E69F00"    # Okabe–Ito palette
PARSE_ALPHA = 0.85

FILTER_COLOR = "#0072B2"   # deep blue
FILTER_ALPHA = 0.75

GAP_COLOR = "#56B4E9"   # very light cyan
GAP_ALPHA = 0.35

def read_spans(file_path, request_id):
    # 从json文件中读取span数据，一个大的json文件，先读"spans"，然后读"request-id"对应的list
    with open(file_path, 'r') as f:
        data = json.load(f)
    spans = data.get("spans", {}).get(request_id, [])
    return spans

def draw_interval(y, start, end, *, color, height, alpha, zorder, label=None):
    if end <= start:
        print("[!] End time is less than the start time")
        exit(1)
    plt.barh(y=y, width=end - start, left=start, height=height, color=color, alpha=alpha, zorder=zorder, label=label)

def normalize_spans(spans):
    all_ts = []
    norm_spans = []
    for span in spans:
        for comp in COMPONENTS:
            obj = span.get(comp, {})
            for k in TIME_FIELDS:
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
        for comp in COMPONENTS:
            obj = span.get(comp, {})
            for k in TIME_FIELDS:
                if k in obj and obj[k] > 0:
                    obj[k] -= t0
                    obj[k] = obj[k] / 1e6
    
    norm_spans.sort(
        key=lambda s: s.get("req", {}).get("Header Parse Start Time", float("inf"))
    )

    return norm_spans

def plot_single(span, index):
    # 默认已经归一化
    norm_span = span

    # 先处理两个conn，两个conn的底色涂成灰色，并用竖线标出parse start time
    # write ready time先忽略掉
    # TODO: 之后考虑处理write ready time，实在处理不了算了
    draw_interval(y=index, start=norm_span["conn"]["Read Ready Start Time"], end=norm_span["conn"]["Parse End Time"],
                    color=CONN_COLOR, height=0.8, alpha=CONN_ALPHA, zorder=0)

    draw_interval(y=index, start=norm_span["upstream_conn"]["Read Ready Start Time"], end=norm_span["upstream_conn"]["Parse End Time"],
                    color=CONN_COLOR, height=0.8, alpha=CONN_ALPHA, zorder=0)
    
    # 两个conn之间的时间绘制成？色，为虚拟的处理时间
    draw_interval(y=index, start=norm_span["conn"]["Parse End Time"], end=norm_span["upstream_conn"]["Read Ready Start Time"],
                    color=GAP_COLOR, height=0.8, alpha=GAP_ALPHA, zorder=0)
    
    # 处理parse time, 绘制成橘色
    draw_interval(y=index, start=norm_span["req"]["Header Parse Start Time"], end=norm_span["req"]["Header Parse End Time"],
                    color=PARSE_COLOR, height=0.8, alpha=PARSE_ALPHA, zorder=1)
    draw_interval(y=index, start=norm_span["req"]["Data Parse Start Time"], end=norm_span["req"]["Data Parse End Time"],
                    color=PARSE_COLOR, height=0.8, alpha=PARSE_ALPHA, zorder=1)
    draw_interval(y=index, start=norm_span["resp"]["Header Parse Start Time"], end=norm_span["resp"]["Header Parse End Time"],
                    color=PARSE_COLOR, height=0.8, alpha=PARSE_ALPHA, zorder=1)
    draw_interval(y=index, start=norm_span["resp"]["Data Parse Start Time"], end=norm_span["resp"]["Data Parse End Time"],
                    color=PARSE_COLOR, height=0.8, alpha=PARSE_ALPHA, zorder=1)
    draw_interval(y=index, start=norm_span["resp"]["Trailer Parse Start Time"], end=norm_span["resp"]["Trailer Parse End Time"],
                    color=PARSE_COLOR, height=0.8, alpha=PARSE_ALPHA, zorder=1)
    
    # 处理filter time，绘制成蓝色
    draw_interval(y=index, start=norm_span["req"]["Header Parse End Time"], end=norm_span["req"]["Data Parse Start Time"],
                    color=FILTER_COLOR, height=0.8, alpha=FILTER_ALPHA, zorder=1)
    draw_interval(y=index, start=norm_span["req"]["Data Parse End Time"], end=norm_span["req"]["Stream End Time"],
                    color=FILTER_COLOR, height=0.8, alpha=FILTER_ALPHA, zorder=1)
    draw_interval(y=index, start=norm_span["resp"]["Header Parse End Time"], end=norm_span["resp"]["Data Parse Start Time"],
                    color=FILTER_COLOR, height=0.8, alpha=FILTER_ALPHA, zorder=1)
    draw_interval(y=index, start=norm_span["resp"]["Data Parse End Time"], end=norm_span["resp"]["Trailer Parse Start Time"],
                    color=FILTER_COLOR, height=0.8, alpha=FILTER_ALPHA, zorder=1)
    draw_interval(y=index, start=norm_span["resp"]["Trailer Parse End Time"], end=norm_span["resp"]["Stream End Time"],
                    color=FILTER_COLOR, height=0.8, alpha=FILTER_ALPHA, zorder=1)
    
def plot_multiple(spans):
    norm_spans = normalize_spans(spans)

    for i, span in enumerate(norm_spans):
        index = len(norm_spans) - i - 1
        plot_single(span, index)

plt.figure(figsize=(14, 2))
test_spans = read_spans("/Users/alicesong/Desktop/research/meshtrek/exper/graph_gen/span_test.json", "735621ec83e08746")
plot_multiple(test_spans)
plt.tight_layout()
plt.show()