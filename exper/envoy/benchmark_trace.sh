#!/bin/bash
# do experiment

NAMESPACE=

MESH_TYPE=$1
MICRO_SERVICE=$2
RPS=$3
DURATION=$4

trace_bookinfo() {
    NAMESPACE="bookinfo"
    local ip=$(kubectl get service productpage -n "$NAMESPACE" -o jsonpath='{.spec.clusterIP}')
    local port=9080
    local request_url="${ip}:${port}/productpage"

    echo "Request URL: $request_url"
    echo "Running RPS=$RPS..."

    ~/wrk2/wrk -t 10 -c 10 -d "$DURATION" -L "http://$request_url" -R $RPS

    wait

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

    echo "Experiment completed."
}

trace_hotel() {
    NAMESPACE="hotel"
    local ip=$(kubectl get service frontend -n "$NAMESPACE" -o jsonpath='{.spec.clusterIP}')
    local port=5000
    local request_url="${ip}:${port}"

    echo "Request URL: $request_url"
    echo "Running RPS=$RPS..."

    ~/DeathStarBench/wrk2/wrk -D exp -t 6 -c 10 -d "$DURATION" -L -s ~/meshtrek/resources/benchmark/HotelReserve/wrk2/frontend_normal.lua "http://$request_url" -R $RPS

    wait

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

    wait

    echo "Experiment completed."
}

if [ "$MICRO_SERVICE" == "hotel" ]; then
    trace_hotel
elif [ "$MICRO_SERVICE" == "bookinfo" ]; then
    trace_bookinfo
fi