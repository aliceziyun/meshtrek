#!/bin/bash

NAMESPACE="bookinfo"

PRODUCTPAGE_IP=$(kubectl get service productpage -n "$NAMESPACE" -o jsonpath='{.spec.clusterIP}')
PRODUCTPAGE_PORT=$(kubectl get service productpage -n "$NAMESPACE" -o jsonpath='{.spec.ports[0].port}')
REQUEST_URL="${PRODUCTPAGE_IP}:${PRODUCTPAGE_PORT}"

echo "Request URL: $REQUEST_URL"

# begin experiment
OUTPUT_FILE="result.log"
> "$OUTPUT_FILE"

echo "Starting experiment..."
for i in $(seq 0 15); do
    RPS=$((300 + i * 10))
    echo "Running RPS=$RPS..." | tee -a "$OUTPUT_FILE"
    for j in {1..3}; do
        ./wrk2/wrk -t 16 -c 20 -d 60 -L http://$REQUEST_URL/productpage -R $RPS | tee -a "$OUTPUT_FILE"
        sleep 5
    done

    echo "" | tee -a "$OUTPUT_FILE"
done