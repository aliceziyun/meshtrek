#!/bin/bash
# This shows a basic example to measure the overhead of the benchmark

MICRO_SERVICE=$1
THREADS=$2
CONNECTIONS=$3
TARGET_RPS=$4
DURATION=$5

benchmark_hotel() {
    NAMESPACE="hotel"
    local ip=$(kubectl get service frontend -n "$NAMESPACE" -o jsonpath='{.spec.clusterIP}')
    local port=5000
    local request_url="${ip}:${port}"
    OUTPUT_FILE="hotel_benchmark_results.txt"

    echo "Benchmarking Hotel Reservation Service" | tee -a "$OUTPUT_FILE"
    echo "Threads: $THREADS, Connections: $CONNECTIONS, Target RPS: $TARGET_RPS, Duration: $DURATION seconds" | tee -a "$OUTPUT_FILE"

    ~/DeathStarBench/wrk2/wrk -D exp -t "$THREADS" -c "$CONNECTIONS" -d "$DURATION" -L -s ~/meshtrek/resources/benchmark/HotelReserve/wrk2/frontend_normal.lua "http://$request_url" -R "$TARGET_RPS"

    wait
}

benchmark_social() {
    NAMESPACE="social"
    local ip=$(kubectl get service nginx -n "$NAMESPACE" -o jsonpath='{.spec.clusterIP}')
    local port=8080
    local request_url="${ip}:${port}/wrk2-api/post/compose"
    OUTPUT_FILE="social_benchmark_results.txt"

    echo "Benchmarking Social Network Service" | tee -a "$OUTPUT_FILE"
    echo "Threads: $THREADS, Connections: $CONNECTIONS, Target RPS: $TARGET_RPS, Duration: $DURATION seconds" | tee -a "$OUTPUT_FILE"

    ~/DeathStarBench/wrk2/wrk -D exp -t "$THREADS" -c "$CONNECTIONS" -d "$DURATION" -L ~/meshtrek/resources/benchmark/SocialNetwork/wrk2/mixed_workload.lua "http://$request_url" -R "$TARGET_RPS"

    wait
}

if [ "$MICRO_SERVICE" == "hotel" ]; then
    benchmark_hotel
elif [ "$MICRO_SERVICE" == "social" ]; then
    benchmark_social
else
    echo "Unsupported microservice: $MICRO_SERVICE"
    exit 1
fi