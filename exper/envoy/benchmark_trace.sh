#!/bin/bash
# do experiment

NAMESPACE=

MESH_TYPE=$1
MICRO_SERVICE=$2
RPS=$3

trace_bookinfo() {
    NAMESPACE="bookinfo"
    local ip=$(kubectl get service productpage -n "$NAMESPACE" -o jsonpath='{.spec.clusterIP}')
    local port=9080
    local request_url="${ip}:${port}/productpage"

    echo "Request URL: $request_url"
    echo "Running RPS=$RPS..."

    ~/DeathStarBench/wrk2/wrk -t 10 -c 10 -d 30 -L "http://$request_url" -R $RPS

    wait

    if [ "$MESH_TYPE" == "cilium" ]; then
        PODS=$(kubectl get pods -n kube-system -o jsonpath='{.items[*].metadata.name}')
        for pod in $PODS; do
            kubectl cp "kube-system/$pod:/tmp/trace_output.log" ~/trace_res/trace_output_"$pod".log
        done
    else
        PODS=$(kubectl get pods -n $NAMESPACE -o jsonpath='{.items[*].metadata.name}')
        for pod in $PODS; do
            kubectl cp "$NAMESPACE/$pod:/tmp/trace_output.log" -c istio-proxy ~/trace_res/trace_output_"$pod".log
        done
    fi

    echo "Experiment completed."
}


trace_hotel() {
    NAMESPACE="hotel"
    local ip=$(kubectl get service frontend2 -n "$NAMESPACE" -o jsonpath='{.spec.clusterIP}')
    local port=5001
    local request_url="${ip}:${port}"

    echo "Request URL: $request_url"
    echo "Running RPS=$RPS..."

    # change the url in mixed-workload_type_1.lua
    # cp ~/DeathStarBench/hotelReservation/wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua ~/DeathStarBench/hotelReservation/wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua.bak
    # sed -i "s|http://localhost:5000|http://${ip}:5000|g" ~/DeathStarBench/hotelReservation/wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua/

    ~/DeathStarBench/wrk2/wrk -D exp -t 10 -c 20 -d 30 -L -s ~/DeathStarBench/hotelReservation/wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua "http://$request_url" -R $RPS

    wait

    if [ "$MESH_TYPE" == "cilium" ]; then
        PODS=$(kubectl get pods -n kube-system -o jsonpath='{.items[*].metadata.name}')
        for pod in $PODS; do
            kubectl cp "kube-system/$pod:/tmp/trace_output.log" ~/trace_res/trace_output_"$pod".log
        done
    else
        PODS=$(kubectl get pods -n $NAMESPACE -o jsonpath='{.items[*].metadata.name}')
        for pod in $PODS; do
            kubectl cp "$NAMESPACE/$pod:/tmp/trace_output.log" -c istio-proxy ~/trace_res/trace_output_"$pod".log
        done
    fi

    wait

    # restore the lua file
    mv ~/DeathStarBench/hotelReservation/wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua.bak ~/DeathStarBench/hotelReservation/wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua

    echo "Experiment completed."
}

if [ "$MICRO_SERVICE" == "hotel" ]; then
    trace_hotel
elif [ "$MICRO_SERVICE" == "bookinfo" ]; then
    trace_bookinfo
fi