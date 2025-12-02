#!/bin/bash

# directory of this script
dir=$(dirname "$0")

services=("frontend" "geo" "profile" "rate" "recommendation" "reservation" "search" "user")

pods=$(kubectl get pods -n hotel -o jsonpath='{.items[*].metadata.name}')

cd ~/istio-1.26.0
export PATH=$PWD/bin:$PATH

cd "$dir"
mkdir -p listeners

for pod in $pods; do
    # pod name must be start with service name
    for service in "${services[@]}"; do
        if [[ $pod == $service* ]]; then
            echo "Saving listeners for service: $service"
            istioctl proxy-config listeners "$pod" -n hotel > listeners/"$service".txt
            break
        fi
    done
done