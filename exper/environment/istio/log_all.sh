#!/bin/bash

NAMESPACE=$1

cd ~/istio-1.26.0
export PATH=$PWD/bin:$PATH
# get all pods in namespace
PODS=$(kubectl get pods -n "$NAMESPACE" -o jsonpath='{.items[*].metadata.name}')

for pod in $PODS; do
    istioctl proxy-config log "$pod" -n "$NAMESPACE" --level router=trace
    istioctl proxy-config log "$pod" -n "$NAMESPACE" --level upstream=trace
    istioctl proxy-config log "$pod" -n "$NAMESPACE" --level http=trace
    istioctl proxy-config log "$pod" -n "$NAMESPACE" --level connection=trace
done