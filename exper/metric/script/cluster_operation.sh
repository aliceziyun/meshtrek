#!/bin/bash

NAMESPACE=$1
OPERATION=$2

launch() {
    if [ "$NAMESPACE" == "hotel" ]; then
        echo "Restarting Hotel Reservation Service cluster in namespace: $NAMESPACE"
        sleep 5
        kubectl apply -Rf ~/meshtrek/resources/benchmark/HotelReserve/kubernetes -n hotel

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
}

delete() {
    if [ "$NAMESPACE" == "hotel" ]; then
        echo "Deleting Hotel Reservation Service cluster in namespace: $NAMESPACE"
        kubectl delete -Rf ~/meshtrek/resources/benchmark/HotelReserve/kubernetes -n hotel
    else
        echo "Unsupported namespace: $NAMESPACE"
        exit 1
    fi
}

if [ "$OPERATION" == "launch" ]; then
    launch
elif [ "$OPERATION" == "delete" ]; then
    delete
else
    echo "Unsupported operation: $OPERATION"
    exit 1
fi

