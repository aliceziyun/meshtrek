#!/bin/bash

# directory of this script
dir=$(dirname "$0")

services=("service0" "service1")
# services=$(kubectl get services -o jsonpath='{.items[*].metadata.name}' | tr " " "\n" | grep -v 'kubernetes')

pods=$(kubectl get pods -o jsonpath='{.items[*].metadata.name}')

cd ~/istio-1.26.0
export PATH=$PWD/bin:$PATH

cd "$dir"
mkdir -p listeners

echo "Fetching listeners for services: ${services[*]}"
echo "Pods found: $pods"

for pod in $pods; do
    # pod name must be start with service name
    for service in "${services[@]}"; do
        if [[ $pod == $service* ]]; then
            echo "Saving listeners for service: $service"
            istioctl proxy-config listeners "$pod" > listeners/"$service".txt
            break
        fi
    done
done