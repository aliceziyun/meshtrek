#!/bin/bash

NAMESPACE="bookinfo"
TRACE_SCRIPT="./envoy_http_trace.py"

# get all pods in namespace
PODS=$(kubectl get pods -n "$NAMESPACE" -o jsonpath='{.items[*].metadata.name}')

for pod in $PODS; do
    kubectl cp "$TRACE_SCRIPT" "$NAMESPACE/$pod:/tmp/envoy_http_trace.py" -c istio-proxy
done

wait

# execute trace script in each pod
for pod in $PODS; do
  echo "Running trace on pod: $pod"
  kubectl exec -i -n "$NAMESPACE" "$pod" -c istio-proxy -- sudo python3 /tmp/envoy_http_trace.py &
done

wait