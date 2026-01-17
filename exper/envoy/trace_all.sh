#!/bin/bash

cd "$(dirname "$0")"

PODS=

MESH_TYPE=$1
NAMESPACE=$2
RUNNING_TIME=$3

TRACE_MAIN_PATH="./uprobe_script/envoy_trace.py"
CONN_UPROBE_PATH="./uprobe_script/conn_uprobe.py"
STREAM_UPROBE_PATH="./uprobe_script/stream_uprobe.py"

if [ "$MESH_TYPE" == "cilium" ]; then
  NAMESPACE="kube-system"
  PODS=$(kubectl get pods -n "$NAMESPACE" -o jsonpath='{.items[*].metadata.name}' \
  | tr ' ' '\n' | grep '^cilium-envoy')
elif [ "$MESH_TYPE" == "istio" ]; then
  PODS=$(kubectl get pods -n "$NAMESPACE" -o jsonpath='{.items[*].metadata.name}')
else
  echo "Unsupported mesh type. Please specify 'cilium' or 'istio'."
  exit 1
fi

for pod in $PODS; do
  if [ "$MESH_TYPE" == "cilium" ]; then
      kubectl cp "$TRACE_MAIN_PATH" "$NAMESPACE/$pod:/tmp/envoy_trace.py"
      kubectl cp "$CONN_UPROBE_PATH" "$NAMESPACE/$pod:/tmp/conn_uprobe.py"
      kubectl cp "$STREAM_UPROBE_PATH" "$NAMESPACE/$pod:/tmp/stream_uprobe.py"
  else
      kubectl cp "$TRACE_MAIN_PATH" "$NAMESPACE/$pod:/tmp/envoy_trace.py" -c istio-proxy
      kubectl cp "$CONN_UPROBE_PATH" "$NAMESPACE/$pod:/tmp/conn_uprobe.py" -c istio-proxy
      kubectl cp "$STREAM_UPROBE_PATH" "$NAMESPACE/$pod:/tmp/stream_uprobe.py" -c istio-proxy
  fi
done

wait

for pod in $PODS; do
  echo "Running trace on pod: $pod"
  if [ "$MESH_TYPE" == "cilium" ]; then
      kubectl exec -i -n "$NAMESPACE" "$pod" -- \ 
      timeout "$RUNNING_TIME"s python3 /tmp/envoy_trace.py -t cilium &
  else
      kubectl exec -i -n "$NAMESPACE" "$pod" -c istio-proxy -- \
      sudo timeout "$RUNNING_TIME"s python3 /tmp/envoy_trace.py -t istio&
  fi
done

wait