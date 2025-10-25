#!/bin/bash

# download helm
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
chmod 700 get_helm.sh
./get_helm.sh

kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm install kps prometheus-community/kube-prometheus-stack \
  -n monitoring \
  --set grafana.enabled=false

kubectl -n monitoring rollout status deploy/kps-kube-prometheus-stack-operator

kubectl -n monitoring get pods -l app=kube-prometheus-stack-prometheus

kubectl -n monitoring patch svc kps-kube-prometheus-stack-prometheus \
  -p '{"spec":{"type":"NodePort"}}'