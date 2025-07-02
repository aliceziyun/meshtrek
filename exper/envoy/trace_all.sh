#!/bin/bash

NAMESPACE="bookinfo"

# get all pods in namespace
PODS=$(kubectl get pods -n "$NAMESPACE" -o jsonpath='{.items[*].metadata.name}')

# execute trace script in each pod
for pod in $PODS; do
  kubectl exec -i -n "$NAMESPACE" "$pod" -c istio-proxy -- sudo rm /tmp/trace_output.log
  echo "Running trace on pod: $pod"
  kubectl exec -i -n "$NAMESPACE" "$pod" -c istio-proxy -- sudo python3 /home/envoy_http_trace.py &
done

wait