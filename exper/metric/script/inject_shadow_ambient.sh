#!/bin/bash

NAMESPACE=$1

# clean the environment before this file

cd istio-1.26.0
export PATH=$PWD/bin:$PATH
istioctl waypoint delete --all -n $NAMESPACE
kubectl label ns $NAMESPACE istio.io/use-waypoint-

# apply gateway
kubectl apply -f ~/resources/ambient/gateway.yaml -n $NAMESPACE

# get uid
kubectl get deploy -n $NAMESPACE waypoint -o yaml | grep uid

# replace uid in shadow files

# apply shadow deployment
kubectl apply -f ~/resources/ambient/deploy-shadow.yaml -n $NAMESPACE

# apply shadow service
kubectl apply -f ~/resources/ambient/service-shadow.yaml -n $NAMESPACE

# apply real gateway
kubectl apply -f ~/resources/ambient/gateway-shadow.yaml -n $NAMESPACE

# wait for ready
sleep 10

kubectl label ns $NAMESPACE istio.io/use-waypoint=test