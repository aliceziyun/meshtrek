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

apply_frontend() {
  local num="$1"

  istioctl waypoint apply -n hotel --name waypoint-frontend

  sleep 2

  # bind this waypoint to node frontend is on (4th node)
  nodes=($(kubectl get nodes --no-headers | awk '!/control-plane/ {print $1}'))
  local node
  if [[ "$num" -eq 3 ]]; then
    node="${nodes[0]}"
  else
    node="${nodes[3]}"
  fi
  kubectl patch deploy waypoint-frontend -n hotel --type=json \
  -p='[
    {
      "op": "add",
      "path": "/spec/template/spec/nodeSelector",
      "value": { "kubernetes.io/hostname": "'"$node"'" }
    }
  ]'
  echo "Patched waypoint [waypoint-frontend] to node [$node]"
}

bind_frontend() {
  kubectl label service frontend -n hotel istio.io/use-waypoint=waypoint-frontend --overwrite
}

apply_single() {
  # Apply a single waypoint for the entire namespace
  istioctl waypoint apply -n hotel --name waypoint

  apply_frontend 1
}

apply_three_node() {
  nodes=($(kubectl get nodes --no-headers | awk '!/control-plane/ {print $1}'))
  waypoints=("waypoint1" "waypoint2" "waypoint3")

  for waypoint in "${waypoints[@]}"; do
    istioctl waypoint apply -n hotel --name "$waypoint"
  done

  for i in "${!nodes[@]}"; do
    # skip the last node
    if [ $i -ge 3 ]; then
      break
    fi
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

  apply_frontend 3
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

  apply_frontend 4
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

      istioctl waypoint apply -n hotel --name "$waypoint"

      sleep 1

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
  done

  sleep 5
}

bind_single() {
  node1_services=("search")
  node2_services=("profile" "rate" "memcached-profile" "memcached-rate" "mongodb-profile" "mongodb-rate" "user" "mongodb-user")
  node3_services=("geo" "mongodb-geo" "reservation" "memcached-reserve" "mongodb-reservation")
  node4_services=("recommendation" "mongodb-recommendation")

  for i in {1..4}; do
    services_arr="node${i}_services[@]"

    for svc in "${!services_arr}"; do
      kubectl label service "$svc" -n hotel istio.io/use-waypoint=waypoint --overwrite
      echo "Labeled service [$svc] to use waypoint [waypoint]"
    done
  done

  bind_frontend

  sleep 5
}

bind_each_node() {
  nodes=($(kubectl get nodes --no-headers | awk '!/control-plane/ {print $1}'))
  waypoints=("waypoint1" "waypoint2" "waypoint3" "waypoint4")

  node1_services=("search")
  node2_services=("profile" "rate" "user")
  node3_services=("geo" "reservation")
  node4_services=("recommendation")

  for i in "${!nodes[@]}"; do
      waypoint="${waypoints[$i]}"
      services_var="node$((i+1))_services[@]"
      for svc in "${!services_var}"; do
          kubectl label service "$svc" -n hotel istio.io/use-waypoint="$waypoint" --overwrite
          echo "Labeled service [$svc] to use waypoint [$waypoint]"
      done
  done

  bind_frontend

  sleep 5
}

bind_three_node() {
  nodes=($(kubectl get nodes --no-headers | awk '!/control-plane/ {print $1}'))
  waypoints=("waypoint1" "waypoint2" "waypoint3")

  node1_services=("search" "recommendation" "mongodb-recommendation")
  node2_services=("profile" "rate" "memcached-profile" "memcached-rate" "mongodb-profile" "mongodb-rate" "user" "mongodb-user")
  node3_services=("geo" "mongodb-geo" "reservation" "memcached-reserve" "mongodb-reservation")

  for i in {1..3}; do
      waypoint="${waypoints[$((i-1))]}"
      services_var="node${i}_services[@]"
      for svc in "${!services_var}"; do
          kubectl label service "$svc" -n hotel istio.io/use-waypoint="$waypoint" --overwrite
          echo "Labeled service [$svc] to use waypoint [$waypoint]"
      done
  done

  bind_frontend

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
      kubectl label service "$svc" -n hotel istio.io/use-waypoint="$waypoint" --overwrite
      echo "Labeled service [$svc] to use waypoint [$waypoint]"
    done
  done

  bind_frontend

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
elif [ "$1" == "apply_single" ]; then
  apply_single
elif [ "$1" == "bind_single" ]; then
  bind_single
else
  echo "Usage"
  exit 1
fi