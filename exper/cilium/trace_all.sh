#!/bin/bash

NAMESPACE="kube-system"
TRACE_SCRIPT="./envoy_http_trace.py"

PODS=$(kubectl get pods -n "$NAMESPACE" -o jsonpath='{.items[*].metadata.name}' \
  | tr ' ' '\n' | grep '^cilium-envoy')

for pod in $PODS; do
  kubectl cp "$TRACE_SCRIPT" "$NAMESPACE/$pod:/tmp/envoy_http_trace.py"
done

wait

# execute trace script in each pod
for pod in $PODS; do
  echo "Running trace on pod: $pod"
  kubectl exec -i -n "$NAMESPACE" "$pod" -- python3 /tmp/envoy_http_trace.py &
done

wait