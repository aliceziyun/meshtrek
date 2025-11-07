#!/bin/bash

cd ~
cd istio-1.26.0
export PATH=$PWD/bin:$PATH

NEW_CPU="${1}m"

export NEW_CPU

yq eval -i "
  .spec.values.global.proxy.resources.requests.cpu = strenv(NEW_CPU) |
  .spec.values.global.proxy.resources.limits.cpu = strenv(NEW_CPU)
" ~/meshtrek/exper/metric/istio_config/operator.yaml

istioctl install -f ~/meshtrek/exper/metric/istio_config/operator.yaml -y

sleep 30