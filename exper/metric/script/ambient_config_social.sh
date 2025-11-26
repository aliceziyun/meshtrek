#!/bin/bash

# For now, this script only supports Hotel-Reservation
cd ~/istio-1.26.0
export PATH=$PWD/bin:$PATH

delete() {
  istioctl waypoint delete --all -n social
  sleep 10
}

apply_three_node() {
  nodes=($(kubectl get nodes --no-headers | awk '!/control-plane/ {print $1}'))
  waypoints=("waypoint1" "waypoint2" "waypoint3")

  for waypoint in "${waypoints[@]}"; do
    istioctl waypoint apply -n social --name "$waypoint"
  done

  for i in "${!nodes[@]}"; do
    # skip the last node
    if [ $i -ge 3 ]; then
      break
    fi
    node="${nodes[$i]}"
    waypoint="${waypoints[$((i % 3))]}"

    kubectl patch deploy "$waypoint" -n social --type=json \
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
    istioctl waypoint apply -n social --name "$waypoint"
  done

  for i in "${!nodes[@]}"; do
    node="${nodes[$i]}"
    waypoint="${waypoints[$i]}"

    kubectl patch deploy "$waypoint" -n social --type=json \
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
  node1_services=("home-timeline-service" "home-timeline-redis" "media-frontend" \
           "media-memcached" "media-mongodb" "media-service" "jaeger")
  node2_services=("post-storage-memcached" "post-storage-mongodb" "post-storage-service" \
           "social-graph-mongodb" "social-graph-redis" "social-graph-service")
  node3_services=("text-service" "unique-id-service" "url-shorten-memcached" "url-shorten-mongodb" \
             "user-timeline-mongodb" "user-timeline-redis" "user-timeline-service")
  node4_services=("url-shorten-service" "user-memcached" "user-mongodb" "user-mention-service" "user-service" \
            "compose-post-service" "nginx-thrift")

  nodes=($(kubectl get nodes --no-headers | awk '!/control-plane/ {print $1}'))

  for i in {1..4}; do
    node="${nodes[$((i-1))]}"
    services_arr="node${i}_services[@]"

    for svc in "${!services_arr}"; do
      waypoint="waypoint-${svc}"

      echo "Applying waypoint [$waypoint] for service [$svc] on node [$node]"

      istioctl waypoint apply -n social --name "$waypoint"

      sleep 1

      kubectl patch deploy "$waypoint" -n social --type=json \
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

  node1_services=("home-timeline-service" "home-timeline-redis" "media-frontend" \
           "media-memcached" "media-mongodb" "media-service" "jaeger")
  node2_services=("post-storage-memcached" "post-storage-mongodb" "post-storage-service" \
           "social-graph-mongodb" "social-graph-redis" "social-graph-service")
  node3_services=("text-service" "unique-id-service" "url-shorten-memcached" "url-shorten-mongodb" \
             "user-timeline-mongodb" "user-timeline-redis" "user-timeline-service")
  node4_services=("url-shorten-service" "user-memcached" "user-mongodb" "user-mention-service" "user-service" \
            "compose-post-service" "nginx-thrift")
  for i in "${!nodes[@]}"; do
      waypoint="${waypoints[$i]}"
      services_var="node$((i+1))_services[@]"
      for svc in "${!services_var}"; do
          kubectl label service "$svc" -n social istio.io/use-waypoint="$waypoint"
          echo "Labeled service [$svc] to use waypoint [$waypoint]"
      done
  done

  sleep 5
}

bind_three_node() {
  nodes=($(kubectl get nodes --no-headers | awk '!/control-plane/ {print $1}'))
  waypoints=("waypoint1" "waypoint2" "waypoint3")

  node1_services=("home-timeline-service" "home-timeline-redis" "media-frontend" \
           "media-memcached" "media-mongodb" "media-service" "jaeger" "user-mention-service" "user-service")
  node2_services=("post-storage-memcached" "post-storage-mongodb" "post-storage-service" \
           "social-graph-mongodb" "social-graph-redis" "social-graph-service" "url-shorten-service" "user-memcached" "user-mongodb")
  node3_services=("text-service" "unique-id-service" "url-shorten-memcached" "url-shorten-mongodb" \
             "user-timeline-mongodb" "user-timeline-redis" "user-timeline-service" "compose-post-service" "nginx-thrift")

  for i in {1..3}; do
      waypoint="${waypoints[$((i-1))]}"
      services_var="node${i}_services[@]"
      for svc in "${!services_var}"; do
          kubectl label service "$svc" -n social istio.io/use-waypoint="$waypoint"
          echo "Labeled service [$svc] to use waypoint [$waypoint]"
      done
  done

  sleep 5
}

bind_each_service() {
  node1_services=("home-timeline-service" "home-timeline-redis" "media-frontend" \
           "media-memcached" "media-mongodb" "media-service" "jaeger")
  node2_services=("post-storage-memcached" "post-storage-mongodb" "post-storage-service" \
           "social-graph-mongodb" "social-graph-redis" "social-graph-service")
  node3_services=("text-service" "unique-id-service" "url-shorten-memcached" "url-shorten-mongodb" \
             "user-timeline-mongodb" "user-timeline-redis" "user-timeline-service")
  node4_services=("url-shorten-service" "user-memcached" "user-mongodb" "user-mention-service" "user-service" \
            "compose-post-service" "nginx-thrift")

  for i in {1..4}; do
    services_arr="node${i}_services[@]"

    for svc in "${!services_arr}"; do
      waypoint="waypoint-${svc}"
      kubectl label service "$svc" -n social istio.io/use-waypoint="$waypoint"
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