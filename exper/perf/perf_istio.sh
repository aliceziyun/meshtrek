#!/bin/bash
# This script is to attach perf to all worker threads in cilium-agent

mkdir -p /tmp/perf_results

PID=$(ps -aux | awk '/\/usr\/local\/bin\/envoy/ && !/awk/ {print $2}')

if [ -n "$PID" ]; then
    echo "Envoy PID: $PID"
else
    echo "Envoy not found"
    exit 1
fi

TIDS=$(ps -T -p $PID | awk '/wrk:worker/ && !/awk/ {print $2}')
for TID in $TIDS; do
    echo "Attaching perf to TID: $TID"
    sudo perf record -F 999 -g -e cycles:u -t $TID -o /tmp/perf_results/perf-$TID.data -- sleep 20 &
done

wait

echo "Perf recording completed."