#!/bin/bash
set -e

nodes=($(kubectl get nodes --no-headers | awk '!/control-plane/ {print $1}'))
if [ ${#nodes[@]} -eq 0 ]; then
  echo "No worker nodes found."
  exit 1
fi

base_dir="$HOME/meshtrek/resources/benchmark/SocialNetwork/helm-chart/socialnetwork/charts"

# group_one=("compose-post-service" "home-timeline-service" "home-timeline-redis" "media-frontend" \
#            "media-memcached" "media-mongodb" "media-service" "jaeger")
# group_two=("nginx-thrift" "post-storage-memcached" "post-storage-mongodb" "post-storage-service" \
#            "social-graph-mongodb" "social-graph-redis" "social-graph-service")
# group_three=("text-service" "unique-id-service" "url-shorten-memcached" "url-shorten-mongodb" \
#              "url-shorten-service" "user-memcached" "user-mongodb" "user-mention-service" "user-service" \
#              "user-timeline-mongodb" "user-timeline-redis" "user-timeline-service")

group_one=("home-timeline-service" "home-timeline-redis" "media-frontend" \
           "media-memcached" "media-mongodb" "media-service" "jaeger")
group_two=("post-storage-memcached" "post-storage-mongodb" "post-storage-service" \
           "social-graph-mongodb" "social-graph-redis" "social-graph-service")
group_three=("text-service" "unique-id-service" "url-shorten-memcached" "url-shorten-mongodb" \
             "user-timeline-mongodb" "user-timeline-redis" "user-timeline-service")
group_four=("url-shorten-service" "user-memcached" "user-mongodb" "user-mention-service" "user-service" \
            "jaeger" "compose-post-service" "nginx-thrift")

patch_group() {
  local group_name="$1"
  local node="$2"
  shift 2
  local services=("$@")

  echo "Binding group [$group_name] → node [$node]"

  for svc in "${services[@]}"; do
    local yaml="${base_dir}/${svc}/values.yaml"
    if [ ! -f "$yaml" ]; then
      echo "Skip: $yaml not found"
      continue
    fi

    echo "Patching $yaml"
    yq eval "
      (.nodeSelector |=
       (. // {}) * {\"kubernetes.io/hostname\": \"$node\"})
    " -i "$yaml"
  done
}

patch_group "group_one"   "${nodes[0]}" "${group_one[@]}"
patch_group "group_two"   "${nodes[1]}" "${group_two[@]}"
patch_group "group_three" "${nodes[2]}" "${group_three[@]}"
patch_group "group_four"  "${nodes[3]}" "${group_four[@]}"

echo "Scheduling completed. Please check your values.yaml files."
