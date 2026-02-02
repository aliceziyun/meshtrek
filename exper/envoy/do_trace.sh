#!/bin/bash

TARGET_RPS=$1
MESH_TYPE=$2
RUNNING_TIME=$3

# 先调用benchmark trace，运行10秒后挂上trace_all，trace_all运行20秒后结束实验
~/meshtrek/exper/envoy/benchmark_trace.sh "$MESH_TYPE" hotel 20 80 "$TARGET_RPS" 60 &

sleep 10

~/meshtrek/exper/envoy/trace_all.sh "$MESH_TYPE" hotel "$RUNNING_TIME" &

wait

echo "Experiment completed with RPS: $TARGET_RPS"