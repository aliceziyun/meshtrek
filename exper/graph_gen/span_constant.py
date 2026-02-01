# constant and util definitions for span tracing

TIME_FIELDS = [
    "Header Parse Start Time",
    ## header parse time
    "Header Filter Start Time",
    ## header filter time
    "Header Process End Time",
    ## wait time
    "Data Parse Start Time",
    ## data parse time
    "Data Filter Start Time",
    ## data filter time
    "Data Process End Time",
    ## wait time
    "Trailer Parse Start Time",
    ## trailer parse time
    "Trailer Filter Start Time",
    ## trailer filter time
    "Stream End Time",
    "Read Ready Start Time",
    "Write Ready Start Time",
    "Parse Start Time",
    "Parse End Time",
]

COMPONENTS = ["req", "resp", "conn", "upstream_conn"]

TARGET_SPAN_LEN = [3,6]   # hotel的请求长度 in ambient

PROTOCOL_HTTP2 = "http2"
PROTOCOL_HTTP1 = "http1"