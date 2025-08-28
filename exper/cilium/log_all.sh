cd dirname "$0"

helm upgrade cilium ../../setup/cilium/cilium_chart \
  --namespace kube-system \
  --set debug.enabled=true \
  --set debug.verbose="envoy" \
  --set envoy.log.defaultLevel=trace