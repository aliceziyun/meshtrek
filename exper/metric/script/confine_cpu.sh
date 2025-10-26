#!/bin/bash

DEFAULT_CPU="500m"
TARGET_CPU=$1
NAMESPACE=$2

deployments=$(kubectl get deployments -n $NAMESPACE -o jsonpath='{.items[*].metadata.name}')
for deploy in $deployments; do
  kubectl -n $NAMESPACE patch deployment $deploy \
    --type='json' \
    -p='[
      {"op": "replace", "path": "/spec/template/spec/containers/0/resources",
      "value": {"limits": {"cpu": "'$TARGET_CPU'"}, "requests": {"cpu": "'$DEFAULT_CPU'"}}}
    ]'
done
echo "Patched CPU limits to $TARGET_CPU for all deployments in namespace '$NAMESPACE'."

echo "Waiting for all pods in namespace '$NAMESPACE' to be ready..."
kubectl wait --for=condition=ready pod -n $NAMESPACE --all --timeout=300s
echo "All pods are ready."