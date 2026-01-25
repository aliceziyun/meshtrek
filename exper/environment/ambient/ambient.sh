#!/bin/bash

NAMESPACE=$1

# First we still need to download Istio
cd ~
export ISTIO_VERSION=1.26.0
curl -L https://istio.io/downloadIstio | ISTIO_VERSION=$ISTIO_VERSION sh -
cd istio-1.26.0
export PATH=$PWD/bin:$PATH

# Now we can set up Istio in Ambient mode
kubectl create namespace $NAMESPACE
kubectl label namespace $NAMESPACE istio.io/dataplane-mode=ambient

kubectl get crd gateways.gateway.networking.k8s.io &> /dev/null || \
  { kubectl kustomize "github.com/kubernetes-sigs/gateway-api/config/crd?ref=v1.4.0" | kubectl apply -f -; }

istioctl install --set profile=ambient --set values.pilot.env.PILOT_ENABLE_GATEWAY_API=true -y

# remove resource limits
istioctl install -f ~/meshtrek/exper/environment/ambient/ambient_operator.yaml -y