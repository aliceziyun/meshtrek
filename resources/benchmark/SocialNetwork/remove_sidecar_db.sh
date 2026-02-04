#!/bin/bash

NAMESPACE=social

for d in $(kubectl get deploy -n $NAMESPACE -o name | grep -E 'mongodb|redis|memcached'); do
  echo "Patching $d"
  kubectl patch $d -n $NAMESPACE \
    -p '{"spec":{"template":{"metadata":{"annotations":{"sidecar.istio.io/inject":"false"}}}}}'
done


NS=social
PATTERN="mongodb|redis|memcached"

pods=$(kubectl get pods -n "$NS" --no-headers | awk '{print $1}' | grep -E "$PATTERN")

for pod in $pods; do
  echo "Processing pod: $pod"

  owner=$(kubectl get pod "$pod" -n "$NS" -o jsonpath='{.metadata.ownerReferences[0].kind}')
  owner_name=$(kubectl get pod "$pod" -n "$NS" -o jsonpath='{.metadata.ownerReferences[0].name}')

  # ReplicaSet -> Deployment
  if [ "$owner" = "ReplicaSet" ]; then
    owner="Deployment"
    owner_name=$(kubectl get rs "$owner_name" -n "$NS" \
      -o jsonpath='{.metadata.ownerReferences[0].name}')
  fi

  echo "  → Controller: $owner/$owner_name"

  kubectl get "$owner" "$owner_name" -n "$NS" -o json | \
  jq '
    .spec.template.spec.containers |= map(select(.name != "istio-proxy"))
  ' | \
  kubectl replace -f -

done
