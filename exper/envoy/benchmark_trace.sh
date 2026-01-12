#!/bin/bash
# do experiment

NAMESPACE=

MESH_TYPE=$1
MICRO_SERVICE=$2
THREADS=$3
CONNECTIONS=$4
RPS=$5
DURATION=$6

trace_bookinfo() {
    NAMESPACE="bookinfo"
    local ip=$(kubectl get service productpage -n "$NAMESPACE" -o jsonpath='{.spec.clusterIP}')
    local port=9080
    local request_url="${ip}:${port}/productpage"

    echo "Request URL: $request_url"
    echo "Running RPS=$RPS..."

    ~/wrk2/wrk -t 10 -c 10 -d "$DURATION" -L "http://$request_url" -R $RPS

    wait

    copy_file_to_local

    wait

    echo "Experiment completed."
}

trace_hotel() {
    NAMESPACE="hotel"
    local ip=$(kubectl get service frontend2 -n "$NAMESPACE" -o jsonpath='{.spec.clusterIP}')
    local port=5001
    local request_url="${ip}:${port}"

    echo "Request URL: $request_url"
    echo "Running RPS=$RPS..."

    ~/DeathStarBench/wrk2/wrk -D exp -t "$THREADS" -c "$CONNECTIONS" -d "$DURATION" -L -s ~/meshtrek/resources/benchmark/HotelReserve/wrk2/frontend_proxy.lua "http://$request_url" -R $RPS

    wait

    copy_file_to_local

    wait

    echo "Experiment completed."
}

trace_social() {
    NAMESPACE="social"
    local ip=$(kubectl get service nginx-thrift -n "$NAMESPACE" -o jsonpath='{.spec.clusterIP}')
    local port=8080
    local request_url="${ip}:${port}"

    echo "Request URL: $request_url"
    echo "Running RPS=$RPS..."

    ~/DeathStarBench/wrk2/wrk -D exp -t "$THREADS" -c "$CONNECTIONS" -d "$DURATION" -L -s /users/aliceso/meshtrek/resources/benchmark/SocialNetwork/mixed_workload.lua "http://$request_url" -R $RPS

    wait

    copy_file_to_local

    wait

    echo "Experiment completed."
}

copy_file_to_local() {
    if [ "$MESH_TYPE" == "cilium" ]; then
        PODS=$(kubectl get pods -n kube-system -o jsonpath='{.items[*].metadata.name}')
        for pod in $PODS; do
            kubectl cp "kube-system/$pod:/tmp/trace_output.log" ~/trace_res/trace_output_"$pod".log
        done
    else if [ "$MESH_TYPE" == "istio" ]; then
        PODS=$(kubectl get pods -n $NAMESPACE -o jsonpath='{.items[*].metadata.name}')
        for pod in $PODS; do
            kubectl cp "$NAMESPACE/$pod:/tmp/trace_output.log" -c istio-proxy ~/trace_res/trace_output_"$pod".log
        done
    fi
    fi
}

if [ "$MICRO_SERVICE" == "hotel" ]; then
    trace_hotel
elif [ "$MICRO_SERVICE" == "bookinfo" ]; then
    trace_bookinfo
elif [ "$MICRO_SERVICE" == "social" ]; then
    trace_social
else
    echo "Unknown micro-service: $MICRO_SERVICE"
fi