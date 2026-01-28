#!/bin/bash

cd "$(dirname "$0")"

PODS=

MESH_TYPE=$1
NAMESPACE=$2
RUNNING_TIME=$3

TRACE_MAIN_PATH="./uprobe_script/envoy_trace.py"
CONN_UPROBE_PATH="./uprobe_script/conn_uprobe.py"
STREAM_UPROBE_PATH="./uprobe_script/stream_uprobe.py"
HTTP1_UPROBE_PATH="./uprobe_script/http1_uprobe.py"

# Argument Check
if [ -z "$MESH_TYPE" ] || [ -z "$NAMESPACE" ] || [ -z "$RUNNING_TIME" ]; then
  echo "Usage: $0 <mesh_type:cilium|istio> <namespace> <running_time_in_seconds>"
  exit 1
fi

if [ "$MESH_TYPE" == "cilium" ]; then
  NAMESPACE="kube-system"
  PODS=$(kubectl get pods -n "$NAMESPACE" -o jsonpath='{.items[*].metadata.name}' \
  | tr ' ' '\n' | grep '^cilium-envoy')
elif [ "$MESH_TYPE" == "istio" ]; then
  PODS=$(kubectl get pods -n "$NAMESPACE" -o jsonpath='{.items[*].metadata.name}')
elif [ "$MESH_TYPE" == "ambient" ]; then
  PODS=$(kubectl get pods -n "$NAMESPACE" | grep waypoint | awk '{print $1}')
else
  echo "Unsupported mesh type. Please specify 'cilium', 'istio', or 'ambient'."
  exit 1
fi

for pod in $PODS; do
  if [ "$MESH_TYPE" == "cilium" ]; then
      kubectl cp "$TRACE_MAIN_PATH" "$NAMESPACE/$pod:/tmp/envoy_trace.py" >/dev/null 2>&1
      kubectl cp "$CONN_UPROBE_PATH" "$NAMESPACE/$pod:/tmp/conn_uprobe.py" >/dev/null 2>&1
      kubectl cp "$STREAM_UPROBE_PATH" "$NAMESPACE/$pod:/tmp/stream_uprobe.py" >/dev/null 2>&1
      kubectl cp "$HTTP1_UPROBE_PATH" "$NAMESPACE/$pod:/tmp/http1_uprobe.py" >/dev/null 2>&1
  elif [ "$MESH_TYPE" == "istio" ]; then
      kubectl cp "$TRACE_MAIN_PATH" "$NAMESPACE/$pod:/tmp/envoy_trace.py" -c istio-proxy >/dev/null 2>&1
      kubectl cp "$CONN_UPROBE_PATH" "$NAMESPACE/$pod:/tmp/conn_uprobe.py" -c istio-proxy >/dev/null 2>&1
      kubectl cp "$STREAM_UPROBE_PATH" "$NAMESPACE/$pod:/tmp/stream_uprobe.py" -c istio-proxy >/dev/null 2>&1
      kubectl cp "$HTTP1_UPROBE_PATH" "$NAMESPACE/$pod:/tmp/http1_uprobe.py" -c istio-proxy >/dev/null 2>&1
  elif [ "$MESH_TYPE" == "ambient" ]; then
      kubectl cp "$TRACE_MAIN_PATH" "$NAMESPACE/$pod:/tmp/envoy_trace.py" >/dev/null 2>&1
      kubectl cp "$CONN_UPROBE_PATH" "$NAMESPACE/$pod:/tmp/conn_uprobe.py" >/dev/null 2>&1
      kubectl cp "$STREAM_UPROBE_PATH" "$NAMESPACE/$pod:/tmp/stream_uprobe.py" >/dev/null 2>&1
      kubectl cp "$HTTP1_UPROBE_PATH" "$NAMESPACE/$pod:/tmp/http1_uprobe.py" >/dev/null 2>&1
  fi
done

wait

trace_hotel() {
  for pod in $PODS; do
    echo "Running trace on pod: $pod"
    if [[ "$pod" =~ frontend ]]; then
        if [ "$MESH_TYPE" == "ambient" ]; then
            PROTOCOL="http1"  # for ambient, frontend proxy only handles http1 traffic
            CURRENT_RUNNING_TIME=$RUNNING_TIME
        else
            PROTOCOL="all"
            CURRENT_RUNNING_TIME=$((RUNNING_TIME + 10))
        fi
    else
        PROTOCOL="http2"
        CURRENT_RUNNING_TIME=$RUNNING_TIME
    fi
    if [ "$MESH_TYPE" == "cilium" ]; then
        kubectl exec -i -n "$NAMESPACE" "$pod" -- \ 
        timeout "$CURRENT_RUNNING_TIME"s python3 /tmp/envoy_trace.py -t cilium -p "$PROTOCOL" &
    else
        echo "Tracing pod $pod with protocol $PROTOCOL for $CURRENT_RUNNING_TIME seconds"
        kubectl exec -i -n "$NAMESPACE" "$pod" -c istio-proxy -- \
        sudo timeout "$CURRENT_RUNNING_TIME"s python3 /tmp/envoy_trace.py -t istio -p "$PROTOCOL" &
    fi
  done
}

if [ "$NAMESPACE" == "hotel" ]; then
  trace_hotel
fi

wait