#!/bin/bash

cd "$(dirname "$0")"

NAMESPACE=""
PODS=
TRACE_SCRIPT="./uprobe_script/xxxx" # fill the script you want to run here!

MESH_TYPE=$1
if [ "$MESH_TYPE" == "cilium" ]; then
  NAMESPACE="kube-system"
  PODS=$(kubectl get pods -n "$NAMESPACE" -o jsonpath='{.items[*].metadata.name}' \
  | tr ' ' '\n' | grep '^cilium-envoy')
elif [ "$MESH_TYPE" == "istio" ]; then
  NAMESPACE="bookinfo"  # change to your istio namespace
  PODS=$(kubectl get pods -n "$NAMESPACE" -o jsonpath='{.items[*].metadata.name}')
else
  echo "Unsupported mesh type. Please specify 'cilium' or 'istio'."
  exit 1
fi


for pod in $PODS; do
  if [ "$MESH_TYPE" == "cilium" ]; then
      kubectl cp "$TRACE_SCRIPT" "$NAMESPACE/$pod:/tmp/envoy_http_trace.py"
  else
      kubectl cp "$TRACE_SCRIPT" "$NAMESPACE/$pod:/tmp/envoy_http_trace.py" -c istio-proxy
  fi
done

wait


for pod in $PODS; do
  echo "Running trace on pod: $pod"
  if [ "$MESH_TYPE" == "cilium" ]; then
      kubectl exec -i -n "$NAMESPACE" "$pod" -- python3 /tmp/envoy_http_trace.py &
  else
      kubectl exec -i -n "$NAMESPACE" "$pod" -c istio-proxy -- python3 /tmp/envoy_http_trace.py &
  fi
done

wait