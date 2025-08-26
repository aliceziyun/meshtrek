#!/bin/bash
NAMESPACE="test"

PRODUCTPAGE_IP=$(kubectl get service echo-service-2 -n "$NAMESPACE" -o jsonpath='{.spec.clusterIP}')
PRODUCTPAGE_PORT=$(kubectl get service echo-service-2 -n "$NAMESPACE" -o jsonpath='{.spec.ports[0].port}')
REQUEST_URL="${PRODUCTPAGE_IP}:${PRODUCTPAGE_PORT}"

echo "Request URL: $REQUEST_URL"

# begin experiment
OUTPUT_FILE="result.log"
> "$OUTPUT_FILE"

echo "Starting experiment..."
RPS=50
echo "Running RPS=$RPS..." | tee -a "$OUTPUT_FILE"
~/wrk2/wrk -t 10 -c 10 -d 60 -L http://$REQUEST_URL -R $RPS | tee -a "$OUTPUT_FILE"
sleep 5

echo "" | tee -a "$OUTPUT_FILE"