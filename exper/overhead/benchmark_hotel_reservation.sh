#!/bin/bash

NAMESPACE="hotel"

PRODUCTPAGE_IP=$(kubectl get service frontend -n "$NAMESPACE" -o jsonpath='{.spec.clusterIP}')
PRODUCTPAGE_PORT=5000
REQUEST_URL="${PRODUCTPAGE_IP}:${PRODUCTPAGE_PORT}"

echo "Request URL: $REQUEST_URL"

# begin experiment
OUTPUT_FILE="result.log"
> "$OUTPUT_FILE"

echo "Starting experiment..."
for i in $(seq 0 6); do
    RPS=$((60 + i * 10))
    echo "Running RPS=$RPS..." | tee -a "$OUTPUT_FILE"
    for j in {1..3}; do
        ../wrk2/wrk -D exp -t 10 -c 20 -d 30 -L -s ./wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua http://$REQUEST_URL -R $RPS | tee -a "$OUTPUT_FILE"
        sleep 5
    done

    echo "" | tee -a "$OUTPUT_FILE"
done