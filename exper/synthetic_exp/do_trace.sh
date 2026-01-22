#!/bin/bash

TARGET_RPS=$1

# 先调用benchmark trace，运行10秒后挂上trace_all，trace_all运行20秒后结束实验
~/meshtrek/exper/envoy/benchmark_trace.sh istio hotel 10 40 "$TARGET_RPS" 60 &

sleep 10

~/meshtrek/exper/envoy/trace_all.sh istio hotel 20

wait

echo "Experiment completed with RPS: $TARGET_RPS"