#!/bin/bash

NAMESPACE=$1
OPERATION=$2

launch() {
    if [ "$NAMESPACE" == "hotel" ]; then
        echo "Restarting Hotel Reservation Service cluster in namespace: $NAMESPACE"
        sleep 5
        kubectl apply -Rf ~/meshtrek/resources/benchmark/HotelReserve/kubernetes -n hotel
    elif [ "$NAMESPACE" == "social" ]; then
        echo "Restarting Social Network Service cluster in namespace: $NAMESPACE"
        sleep 5
        helm install socialnetwork ~/meshtrek/resources/benchmark/SocialNetwork/helm-chart/socialnetwork/ --namespace social
    else
        echo "Unsupported namespace: $NAMESPACE"
        exit 1
    fi

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
}

delete() {
    # get pod, if no pod, skip
    local pods=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | awk '{print $1}')
    if [ -z "$pods" ]; then
        echo "No pods found in namespace: $NAMESPACE"
        return
    fi

    if [ "$NAMESPACE" == "hotel" ]; then
        echo "Deleting Hotel Reservation Service cluster in namespace: $NAMESPACE"
        kubectl delete -Rf ~/meshtrek/resources/benchmark/HotelReserve/kubernetes -n hotel
    elif [ "$NAMESPACE" == "social" ]; then
        echo "Deleting Social Network Service cluster in namespace: $NAMESPACE"
        helm uninstall socialnetwork -n social
    else
        echo "Unsupported namespace: $NAMESPACE"
        exit 1
    fi

    sleep 5
}

if [ "$OPERATION" == "launch" ]; then
    launch
elif [ "$OPERATION" == "delete" ]; then
    delete
else
    echo "Unsupported operation: $OPERATION"
    exit 1
fi