#!/bin/bash

NAMESPACE=$1
OPERATION=$2

delete() {
    kubectl delete envoyfilter -n "$NAMESPACE" --all
    kubectl delete configmap -n "$NAMESPACE" opa-policy
    sleep 5
}

launch_tap() {
    kubectl apply -f ~/meshtrek/resources/envoy_filters/tap.yaml -n "$NAMESPACE"
}

launch_header() {
    kubectl apply -f ~/meshtrek/resources/envoy_filters/header.yaml -n "$NAMESPACE"
}

launch_opa() {
    # create config map
    kubectl create configmap opa-policy --from-file=~/meshtrek/resources/envoy_filters/opa-allow-all-find.rego -n hotel --dry-run=client -o yaml | kubectl apply -f -

    # apply opa filter
    kubectl apply -f ~/meshtrek/resources/envoy_filters/opa.yaml -n "$NAMESPACE"
}

launch_rate_limit() {
    kubectl apply -f ~/meshtrek/resources/envoy_filters/rate_limit.yaml -n "$NAMESPACE"
}


if [ "$OPERATION" == "tap" ]; then
    launch_tap
elif [ "$OPERATION" == "opa" ]; then
    launch_header
    launch_opa
elif [ "$OPERATION" == "header" ]; then
    launch_header
elif [ "$OPERATION" == "rate_limit" ]; then
    launch_rate_limit
elif [ "$OPERATION" == "all" ]; then
    launch_tap
    launch_header
    launch_opa
    launch_rate_limit
elif [ "$OPERATION" == "delete" ]; then
    delete
else
    echo "Unsupported operation: $OPERATION"
    exit 1
fi