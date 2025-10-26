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

wait
echo "Patched CPU limits to $TARGET_CPU for all deployments in namespace '$NAMESPACE'."

echo "Waiting for pods to be ready..."
for i in {1..60}; do
  not_ready=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | grep -v 'Running' | wc -l)
  if [ "$not_ready" -eq 0 ]; then
    echo "All pods ready."
    exit 0
  fi
  sleep 5
done
echo "Timeout: Some pods not ready."
exit 1