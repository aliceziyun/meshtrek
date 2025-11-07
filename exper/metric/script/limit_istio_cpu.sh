#!/bin/bash

cd ~
cd istio-1.26.0
export ISTIO_VERSION=1.26.0

NEW_CPU="${1}m"

export NEW_CPU

yq eval -i "
  .spec.values.global.proxy.resources.requests.cpu = strenv(NEW_CPU) |
  .spec.values.global.proxy.resources.limits.cpu = strenv(NEW_CPU)
" ~/meshtrek/exper/metric/istio_config/istio-operator.yaml

istioctl install -f ~/meshtrek/exper/metric/istio_config/istio-operator.yaml -y

sleep 30