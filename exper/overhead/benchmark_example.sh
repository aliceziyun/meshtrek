#!/bin/bash
# This shows a basic example to measure the overhead of the benchmark

NAMESPACE="bookinfo"
SERVICE_ENTRY="productpage"

IP=$(kubectl get service $SERVICE_ENTRY -n "$NAMESPACE" -o jsonpath='{.spec.clusterIP}')
PORT=$(kubectl get service $SERVICE_ENTRY -n "$NAMESPACE" -o jsonpath='{.spec.ports[0].port}')
REQUEST_URL="${IP}:${PORT}"

echo "Request URL: $REQUEST_URL"

# begin experiment
OUTPUT_FILE="result.log"
> "$OUTPUT_FILE"

echo "Starting experiment..."
for i in $(seq 0 10); do
    RPS=$((300 + i * 10))
    echo "Running RPS=$RPS..." | tee -a "$OUTPUT_FILE"
    for j in {1..3}; do
        ./wrk2/wrk -t 10 -c 10 -d 60 -L http://$REQUEST_URL/productpage -R $RPS | tee -a "$OUTPUT_FILE"
        sleep 5
    done

    echo "" | tee -a "$OUTPUT_FILE"
done