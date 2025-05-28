#!/bin/bash

NAMESPACE="bookinfo-no-istio"

PRODUCTPAGE_IP=$(kubectl get service productpage -n "$NAMESPACE" -o jsonpath='{.spec.clusterIP}')
PRODUCTPAGE_PORT=$(kubectl get service productpage -n "$NAMESPACE" -o jsonpath='{.spec.ports[0].port}')
REQUEST_URL="${PRODUCTPAGE_IP}:${PRODUCTPAGE_PORT}"

echo "Request URL: $REQUEST_URL"

# begin experiment
OUTPUT_FILE="result.log"
> "$OUTPUT_FILE"

echo "Starting experiment..."
for i in 100 200 300 400 500 600; do
    echo "Running RPS=$i..." | tee -a "$OUTPUT_FILE"
    for j in {1..3}; do
        ./wrk2/wrk -t 16 -c 20 -d 60 -L http://$REQUEST_URL/productpage -R "$i" | tee -a "$OUTPUT_FILE"
        sleep 5
    done

    echo "" | tee -a "$OUTPUT_FILE"
done