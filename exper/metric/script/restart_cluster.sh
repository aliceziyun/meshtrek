#!/bin/bash

NAMESPACE=$1

if [ "$NAMESPACE" == "hotel" ]; then
    echo "Restarting Hotel Reservation Service cluster in namespace: $NAMESPACE"
    kubectl delete -Rf ~/meshtrek/setup/benchmark/HotelReserve/kubernetes -n hotel
    sleep 5
    kubectl apply -Rf ~/meshtrek/setup/benchmark/HotelReserve/kubernetes -n hotel

    echo "Waiting for pods to be ready..."
    for i in {1..60}; do
        not_ready=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | grep -v 'Running' | wc -l)
        if [ "$not_ready" -eq 0 ]; then
            echo "All pods ready."
            exit 0
        fi
        sleep 5
    done
    echo "Timeout: Some pods not ready."
    exit 1
else
    echo "Unsupported namespace: $NAMESPACE"
    exit 1
fi