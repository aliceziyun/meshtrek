#!/bin/bash

cd "$(dirname "$0")"

PODS=

MESH_TYPE=$1
NAMESPACE=$2
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
      kubectl cp ./uprobe_script/envoy_trace.py "$NAMESPACE/$pod:/tmp/envoy_trace.py"
      kubectl cp ./uprobe_script/http_uprobe.py "$NAMESPACE/$pod:/tmp/http_uprobe.py"
  else
      kubectl cp ./uprobe_script/envoy_trace.py "$NAMESPACE/$pod:/tmp/envoy_trace.py" -c istio-proxy
      kubectl cp ./uprobe_script/http_uprobe.py "$NAMESPACE/$pod:/tmp/http_uprobe.py" -c istio-proxy
  fi
done

wait


for pod in $PODS; do
  echo "Running trace on pod: $pod"
  if [ "$MESH_TYPE" == "cilium" ]; then
      kubectl exec -i -n "$NAMESPACE" "$pod" -- python3 /tmp/envoy_trace.py -t cilium &
  else
      kubectl exec -i -n "$NAMESPACE" "$pod" -c istio-proxy -- sudo python3 /tmp/envoy_trace.py -t istio&
  fi
done

wait