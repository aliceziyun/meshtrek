#!/bin/bash

# For now, this script only supports Hotel-Reservation
cd ~/istio-1.26.0
export PATH=$PWD/bin:$PATH

delete() {
  istioctl waypoint delete --all -n hotel
  sleep 10
}

apply_three_node() {
  nodes=($(kubectl get nodes --no-headers | awk '!/control-plane/ {print $1}'))
  waypoints=("waypoint1" "waypoint2" "waypoint3")

  for waypoint in "${waypoints[@]}"; do
    istioctl waypoint apply -n hotel --name "$waypoint"
  done

  for i in "${!nodes[@]}"; do
    node="${nodes[$i]}"
    waypoint="${waypoints[$((i % 3))]}"

    kubectl patch deploy "$waypoint" -n hotel --type=json \
    -p='[
      {
        "op": "add",
        "path": "/spec/template/spec/nodeSelector",
        "value": { "kubernetes.io/hostname": "'"$node"'" }
      }
    ]'
    echo "Patched waypoint [$waypoint] to node [$node]"
  done
}

apply_each_node() {
  nodes=($(kubectl get nodes --no-headers | awk '!/control-plane/ {print $1}'))
  waypoints=("waypoint1" "waypoint2" "waypoint3" "waypoint4")
  for waypoint in "${waypoints[@]}"; do
    istioctl waypoint apply -n hotel --name "$waypoint"
  done

  for i in "${!nodes[@]}"; do
    node="${nodes[$i]}"
    waypoint="${waypoints[$i]}"

    kubectl patch deploy "$waypoint" -n hotel --type=json \
    -p='[
      {
        "op": "add",
        "path": "/spec/template/spec/nodeSelector",
        "value": { "kubernetes.io/hostname": "'"$node"'" }
      }
    ]'
    echo "Patched waypoint [$waypoint] to node [$node]"
  done
}

bind_each_node() {
  nodes=($(kubectl get nodes --no-headers | awk '!/control-plane/ {print $1}'))
  waypoints=("waypoint1" "waypoint2" "waypoint3" "waypoint4")

  node1_services=("search")
  node2_services=("profile" "rate" "memcached-profile" "memcached-rate" "mongodb-profile" "mongodb-rate" "user" "mongodb-user")
  node3_services=("geo" "mongodb-geo" "reservation" "memcached-reserve" "mongodb-reservation")
  node4_services=("frontend" "recommendation" "mongodb-recommendation")

  for i in "${!nodes[@]}"; do
      waypoint="${waypoints[$i]}"
      services_var="node$((i+1))_services[@]"
      for svc in "${!services_var}"; do
          kubectl label service "$svc" -n hotel istio.io/use-waypoint="$waypoint"
          echo "Labeled service [$svc] to use waypoint [$waypoint]"
      done
  done
}

bind_three_node() {
  nodes=($(kubectl get nodes --no-headers | awk '!/control-plane/ {print $1}'))
  waypoints=("waypoint1" "waypoint2" "waypoint3")

  node1_services=("search" "frontend" "recommendation" "mongodb-recommendation")
  node2_services=("profile" "rate" "memcached-profile" "memcached-rate" "mongodb-profile" "mongodb-rate" "user" "mongodb-user")
  node3_services=("geo" "mongodb-geo" "reservation" "memcached-reserve" "mongodb-reservation")

  for i in "${!nodes[@]}"; do
      waypoint="${waypoints[$((i % 3))]}"
      services_var="node$(( (i % 3) +1 ))_services[@]"
      for svc in "${!services_var}"; do
          kubectl label service "$svc" -n hotel istio.io/use-waypoint="$waypoint"
          echo "Labeled service [$svc] to use waypoint [$waypoint]"
      done
  done
}

if [ "$1" == "delete" ]; then
  delete
elif [ "$1" == "apply_each_node" ]; then
  apply_each_node
elif [ "$1" == "bind_each_node" ]; then
  bind_each_node
elif [ "$1" == "apply_three_node" ]; then
  apply_three_node
elif [ "$1" == "bind_three_node" ]; then
  bind_three_node
else
  echo "Usage: $0"
fi