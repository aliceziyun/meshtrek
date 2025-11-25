#!/bin/bash

# For now, this script only supports Hotel-Reservation
cd ~/istio-1.26.0
export PATH=$PWD/bin:$PATH

delete() {
  istioctl waypoint delete --all -n bookinfo
  sleep 10
}

apply_three_node() {
  nodes=($(kubectl get nodes --no-headers | awk '!/control-plane/ {print $1}'))
  waypoints=("waypoint1" "waypoint2" "waypoint3")

  for waypoint in "${waypoints[@]}"; do
    istioctl waypoint apply -n bookinfo --name "$waypoint"
  done

  for i in "${!nodes[@]}"; do
    # skip the last node
    if [ $i -ge 3 ]; then
      break
    fi
    node="${nodes[$i]}"
    waypoint="${waypoints[$((i % 3))]}"

    kubectl patch deploy "$waypoint" -n bookinfo --type=json \
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
    istioctl waypoint apply -n bookinfo --name "$waypoint"
  done

  for i in "${!nodes[@]}"; do
    node="${nodes[$i]}"
    waypoint="${waypoints[$i]}"

    kubectl patch deploy "$waypoint" -n bookinfo --type=json \
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

apply_each_service() {
  node1_services=("productpage")
  node2_services=("reviews")
  node3_services=("ratings")
  node4_services=("details")

  nodes=($(kubectl get nodes --no-headers | awk '!/control-plane/ {print $1}'))

  for i in {1..4}; do
    node="${nodes[$((i-1))]}"
    services_arr="node${i}_services[@]"

    for svc in "${!services_arr}"; do
      waypoint="waypoint-${svc}"

      echo "Applying waypoint [$waypoint] for service [$svc] on node [$node]"

      istioctl waypoint apply -n bookinfo --name "$waypoint"

      sleep 1

      kubectl patch deploy "$waypoint" -n bookinfo --type=json \
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

bind_each_node() {
  nodes=($(kubectl get nodes --no-headers | awk '!/control-plane/ {print $1}'))
  waypoints=("waypoint1" "waypoint2" "waypoint3" "waypoint4")

  node1_services=("productpage")
  node2_services=("reviews")
  node3_services=("ratings")
  node4_services=("details")

  for i in "${!nodes[@]}"; do
      waypoint="${waypoints[$i]}"
      services_var="node$((i+1))_services[@]"
      for svc in "${!services_var}"; do
          kubectl label service "$svc" -n bookinfo istio.io/use-waypoint="$waypoint"
          echo "Labeled service [$svc] to use waypoint [$waypoint]"
      done
  done

  sleep 5
}

bind_three_node() {
  nodes=($(kubectl get nodes --no-headers | awk '!/control-plane/ {print $1}'))
  waypoints=("waypoint1" "waypoint2" "waypoint3")

  node1_services=("productpage" "details")
  node2_services=("reviews")
  node3_services=("ratings")

  for i in {1..3}; do
      waypoint="${waypoints[$((i-1))]}"
      services_var="node${i}_services[@]"
      for svc in "${!services_var}"; do
          kubectl label service "$svc" -n bookinfo istio.io/use-waypoint="$waypoint"
          echo "Labeled service [$svc] to use waypoint [$waypoint]"
      done
  done

  sleep 5
}

bind_each_service() {
  node1_services=("productpage")
  node2_services=("reviews")
  node3_services=("ratings")
  node4_services=("details")

  for i in {1..4}; do
    services_arr="node${i}_services[@]"

    for svc in "${!services_arr}"; do
      waypoint="waypoint-${svc}"
      kubectl label service "$svc" -n bookinfo istio.io/use-waypoint="$waypoint"
      echo "Labeled service [$svc] to use waypoint [$waypoint]"
    done
  done

  sleep 5
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
elif [ "$1" == "apply_each_service" ]; then
  apply_each_service
elif [ "$1" == "bind_each_service" ]; then
  bind_each_service
else
  echo "Usage"
  exit 1
fi