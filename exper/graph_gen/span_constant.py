# constant and util definitions for span tracing

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
