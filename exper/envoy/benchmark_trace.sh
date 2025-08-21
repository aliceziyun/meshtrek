#!/bin/bash
# do experiment
NAMESPACE="bookinfo"

PRODUCTPAGE_IP=$(kubectl get service productpage -n "$NAMESPACE" -o jsonpath='{.spec.clusterIP}')
PRODUCTPAGE_PORT=$(kubectl get service productpage -n "$NAMESPACE" -o jsonpath='{.spec.ports[0].port}')

# PRODUCTPAGE_IP=$(kubectl get service frontend -n "$NAMESPACE" -o jsonpath='{.spec.clusterIP}')
# PRODUCTPAGE_PORT=5000
REQUEST_URL="${PRODUCTPAGE_IP}:${PRODUCTPAGE_PORT}"

echo "Request URL: $REQUEST_URL"

# begin experiment
echo "Starting experiment..."
RPS=60
echo "Running RPS=$RPS..."
./wrk2/wrk -t 10 -c 10 -d 60 -L http://$REQUEST_URL/productpage -R $RPS
# ../wrk2/wrk -D exp -t 10 -c 20 -d 30 -L -s ./wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua http://$REQUEST_URL -R $RPS

wait

# copy trace output back
# get all pods in namespace
PODS=$(kubectl get pods -n "$NAMESPACE" -o jsonpath='{.items[*].metadata.name}')

for pod in $PODS; do
    kubectl cp "$NAMESPACE/$pod:/tmp/trace_output.log" -c istio-proxy ~/trace_res/trace_output_"$pod".log
done