#!/bin/bash

# For now, this script only supports Hotel-Reservation
cd ~/istio-1.26.0
export PATH=$PWD/bin:$PATH

delete() {
  istioctl waypoint delete --all -n hotel
  waypoints_deploy=$(kubectl get deploy -n hotel | grep waypoint | awk '{print $1}')
  for deploy in $waypoints_deploy; do
    kubectl delete deploy "$deploy" -n hotel
  done

  sleep 10
}

apply_each_service() {
  node1_services=("search")
  node2_services=("profile" "rate" "user")
  node3_services=("geo" "reservation")
  node4_services=("frontend" "recommendation")

  nodes=($(kubectl get nodes --no-headers | awk '!/control-plane/ {print $1}'))

  for i in {1..4}; do
    node="${nodes[$((i-1))]}"
    services_arr="node${i}_services[@]"

    for svc in "${!services_arr}"; do
      waypoint="waypoint-${svc}"

      echo "Applying waypoint [$waypoint] for service [$svc] on node [$node]"

      istioctl waypoint apply -n default --name "$waypoint"

      sleep 1

      kubectl patch deploy "$waypoint" -n default --type=json \
      -p='[
        {
          "op": "add",
          "path": "/spec/template/spec/nodeSelector",
          "value": { "kubernetes.io/hostname": "'"$node"'" }
        }
      ]'

      echo "Patched waypoint [$waypoint] to node [$node]"
    done
  done

  sleep 5
}

bind_each_service() {
  node1_services=("search")
  node2_services=("profile" "rate" "user")
  node3_services=("geo" "reservation")
  node4_services=("frontend" "recommendation")

  for i in {1..4}; do
    services_arr="node${i}_services[@]"

    for svc in "${!services_arr}"; do
      waypoint="waypoint-${svc}"
      kubectl label service "$svc" -n default istio.io/use-waypoint="$waypoint" --overwrite
      echo "Labeled service [$svc] to use waypoint [$waypoint]"
    done
  done

  bind_frontend

  sleep 5
}

if [ "$1" == "delete" ]; then
  delete
elif [ "$1" == "apply_each_service" ]; then
  apply_each_service
elif [ "$1" == "bind_each_service" ]; then
  bind_each_service
else
  echo "Usage"
  exit 1
fi