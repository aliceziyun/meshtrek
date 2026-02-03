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
  node2_services=("profile" "rate" "user")
  node3_services=("geo" "reservation")
  node4_services=("frontend" "recommendation")

  for i in "${!nodes[@]}"; do
      waypoint="${waypoints[$i]}"
      services_var="node$((i+1))_services[@]"
      for svc in "${!services_var}"; do
          kubectl label service "$svc" -n hotel istio.io/use-waypoint="$waypoint"
          echo "Labeled service [$svc] to use waypoint [$waypoint]"
      done
  done

  sleep 5
}

bind_each_node_remote() {
  nodes=($(kubectl get nodes --no-headers | awk '!/control-plane/ {print $1}'))
  waypoints=("waypoint1" "waypoint2" "waypoint3" "waypoint4")

  node1_services=("search")
  node2_services=("profile" "rate" "user")
  node3_services=("geo" "reservation")
  node4_services=("frontend" "recommendation")

  num_nodes=${#nodes[@]}

  for i in "${!nodes[@]}"; do
      wp_index=$(( (i + 1) % num_nodes ))
      waypoint="${waypoints[$wp_index]}"

      services_var="node$((i+1))_services[@]"
      for svc in "${!services_var}"; do
          kubectl label service "$svc" -n hotel istio.io/use-waypoint="$waypoint" --overwrite
          echo "Labeled service [$svc] on node$((i+1)) to use waypoint [$waypoint]"
      done
  done

  sleep 5
}



if [ "$1" == "delete" ]; then
  delete
elif [ "$1" == "apply_each_node" ]; then
  apply_each_node
elif [ "$1" == "bind_each_service" ]; then
  bind_each_node
elif [ "$1" == "bind_each_service_remote" ]; then
  bind_each_node_remote
else
  echo "Usage"
  exit 1
fi