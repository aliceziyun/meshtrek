NAMESPACE=$1

deployments=$(kubectl get deployments -n $NAMESPACE -o jsonpath='{.items[*].metadata.name}')
for deploy in $deployments; do
  kubectl -n $NAMESPACE patch deployment $deploy \
    --type='json' \
    -p='[
      {"op": "remove", "path": "/spec/template/spec/containers/0/resources"}
    ]' 2>/dev/null || echo "No resources field in $deploy"
done

echo "Removed CPU limits for all deployments in namespace '$NAMESPACE'."

wait

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