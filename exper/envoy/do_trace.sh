#!/bin/bash

MESH_TYPE=$1
NAMESPACE=$2
THREADS=$3
CONNECTIONS=$4
RUNNING_TIME=$5
TARGET_RPS=$6


# 先调用benchmark trace，运行10秒后挂上trace_all，trace_all运行20秒后结束实验
~/meshtrek/exper/envoy/benchmark_trace.sh "$MESH_TYPE" "$NAMESPACE" "$THREADS" "$CONNECTIONS" "$TARGET_RPS" 60 &

sleep 10

~/meshtrek/exper/envoy/trace_all.sh "$MESH_TYPE" "$NAMESPACE" "$RUNNING_TIME" &

wait

echo "Experiment completed with RPS: $TARGET_RPS"