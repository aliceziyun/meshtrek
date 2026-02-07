#!/bin/bash

# For now, this script only supports Hotel-Reservation
cd ~/istio-1.26.0
export PATH=$PWD/bin:$PATH

delete() {
  istioctl waypoint delete --all -n default
  waypoints_deploy=$(kubectl get deploy -n default | grep waypoint | awk '{print $1}')
  for deploy in $waypoints_deploy; do
    kubectl delete deploy "$deploy" -n default
  done

  sleep 10
}

apply_each_node() {
  nodes=($(kubectl get nodes --no-headers | awk '!/control-plane/ {print $1}'))
  waypoints=("waypoint1" "waypoint2" "waypoint3" "waypoint4")
  for waypoint in "${waypoints[@]}"; do
    istioctl waypoint apply  --name "$waypoint"
  done

  for i in "${!nodes[@]}"; do
    node="${nodes[$i]}"
    waypoint="${waypoints[$i]}"

    kubectl patch deploy "$waypoint" --type=json \
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

bind_to_single_node() {
  nodes=($(kubectl get nodes --no-headers | awk '!/control-plane/ {print $1}'))

  node1_services=("service0")
  node2_services=("service1")
  node3_services=("service2")
  node4_services=("service3")

  for i in "${!nodes[@]}"; do
      waypoint="waypoint1"
      services_var="node$((i+1))_services[@]"
      for svc in "${!services_var}"; do
          kubectl label service "$svc" istio.io/use-waypoint="$waypoint" --overwrite
          echo "Labeled service [$svc] to use waypoint [$waypoint]"
      done
  done

  sleep 5
}



bind_each_node() {
  nodes=($(kubectl get nodes --no-headers | awk '!/control-plane/ {print $1}'))
  waypoints=("waypoint1" "waypoint2" "waypoint3" "waypoint4")

  node1_services=("service0")
  node2_services=("service1")
  node3_services=("service2")
  node4_services=("service3")

  for i in "${!nodes[@]}"; do
      waypoint="${waypoints[$i]}"
      services_var="node$((i+1))_services[@]"
      for svc in "${!services_var}"; do
          kubectl label service "$svc" istio.io/use-waypoint="$waypoint" --overwrite
          echo "Labeled service [$svc] to use waypoint [$waypoint]"
      done
  done

  sleep 5
}

bind_each_node_remote() {
  nodes=($(kubectl get nodes --no-headers | awk '!/control-plane/ {print $1}'))
  waypoints=("waypoint1" "waypoint2" "waypoint3" "waypoint4")

  node1_services=("service0")
  node2_services=("service1")
  node3_services=("service2")
  node4_services=("service3")

  num_nodes=${#nodes[@]}

  for i in "${!nodes[@]}"; do
      wp_index=$(( (i + 2) % num_nodes ))
      waypoint="${waypoints[$wp_index]}"

      services_var="node$((i+1))_services[@]"
      for svc in "${!services_var}"; do
          kubectl label service "$svc"  istio.io/use-waypoint="$waypoint" --overwrite
          echo "Labeled service [$svc] on node$((i+2)) to use waypoint [$waypoint]"
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
elif [ "$1" == "bind_each_node_remote" ]; then
  bind_each_node_remote
elif [ "$1" == "bind_to_single_node" ]; then
  bind_to_single_node
else
  echo "Usage"
  exit 1
fi
