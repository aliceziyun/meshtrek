#!/bin/bash

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