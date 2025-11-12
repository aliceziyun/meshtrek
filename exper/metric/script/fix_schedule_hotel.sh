#!/bin/bash
set -e

nodes=($(kubectl get nodes --no-headers | awk '!/control-plane/ {print $1}'))
if [ ${#nodes[@]} -eq 0 ]; then
  echo "No worker nodes found."
  exit 1
fi

base_dir="$HOME/meshtrek/resources/benchmark/HotelReserve/kubernetes"
# group_one=("frontend" "search" "recommendation" "consul")
# group_two=("rate" "profile" "user")
# group_three=("reservation" "geo" "jaeger")

group_one=("search" "consul")
group_two=("rate" "profile" "user")
group_three=("reservation" "geo" "jaeger")
group_four=("frontend" "recommendation")

patch_group() {
  local group_name="$1"
  local node="$2"
  shift 2
  local services=("$@")

  echo "Binding group [$group_name] → node [$node]"

  for svc in "${services[@]}"; do
    local yaml="${base_dir}/${svc}/${svc}-deployment.yaml"
    if [ ! -f "$yaml" ]; then
      echo "Skip: $yaml not found"
      continue
    fi

    echo "Patching $yaml"
    yq eval "
      (.spec.template.spec.nodeSelector |=
       (. // {}) * {\"kubernetes.io/hostname\": \"$node\"})
    " -i "$yaml"
  done
}

patch_group "group_one"   "${nodes[0]}" "${group_one[@]}"
patch_group "group_two"   "${nodes[1]}" "${group_two[@]}"
patch_group "group_three" "${nodes[2]}" "${group_three[@]}"
patch_group "group_four"  "${nodes[3]}" "${group_four[@]}"

echo "Scheduling completed, please check the directory"