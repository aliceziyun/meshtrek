#!/bin/bash
# Use perf to collect performance data of envoy

cd $(dirname $0)

PERF_EXECUTE_SCRIPT=""
PERF_TRAVERSE_SCRIPT="perf_traverse.sh"
NAMESPACE=$2

env_install() {
    # install linux-tools for perf in cilium-envoy container
    PODS=$(kubectl get pods -n kube-system | grep cilium-envoy | awk '{print $1}')

    for POD in $PODS; do
        echo "Installing linux-tools in pod: $POD"
        kubectl exec -n kube-system $POD -- apt-get install -y linux-tools-6.8.0-71-generic &
    done

    wait
}

perf_cilium() {
    # get all the pod of cilium-envoy
    PODS=$(kubectl get pods -n kube-system | grep cilium-envoy | awk '{print $1}')

    # copy script to each pod and execute it
    for POD in $PODS; do
        echo "Processing pod: $POD"
        kubectl cp $PERF_EXECUTE_SCRIPT $POD:/tmp/perf_cilium.sh -n kube-system
        kubectl exec -n kube-system $POD -- chmod +x /tmp/perf_cilium.sh
        kubectl exec -n kube-system $POD -- /tmp/perf_cilium.sh &
    done

    wait

    # when the script is done, traverse perf.data to perf.script, then copy all perf results back
    for POD in $PODS; do
        mkdir -p perf_results/$POD
        kubectl cp $PERF_TRAVERSE_SCRIPT $POD:/tmp/perf_traverse.sh -n kube-system
        kubectl exec -n kube-system $POD -- chmod +x /tmp/perf_traverse.sh
        kubectl exec -n kube-system $POD -- /tmp/perf_traverse.sh
        kubectl cp $POD:/tmp/perf_results ./perf_results/$POD -n kube-system
    done
}

perf_istio() {
    # get all pod in test namespace
    PODS=$(kubectl get pods -n $NAMESPACE -o jsonpath='{.items[*].metadata.name}')

    # copy script to each sidecar pod and execute it
    for POD in $PODS; do
        echo "Processing pod: $POD"
        kubectl cp $PERF_EXECUTE_SCRIPT $POD:/tmp/perf_istio.sh -n $NAMESPACE -c istio-proxy
        kubectl exec -n $NAMESPACE $POD -c istio-proxy -- chmod +x /tmp/perf_istio.sh
        kubectl exec -n $NAMESPACE $POD -c istio-proxy -- /tmp/perf_istio.sh
    done

    # when the script is done, copy all perf results back
    for POD in $PODS; do
        mkdir -p perf_results/$POD

        # no permission in /tmp/perf_results, change the permission first
        kubectl exec -n $NAMESPACE $POD -c istio-proxy -- sudo chmod -R 777 /tmp/perf_results

        kubectl cp $PERF_TRAVERSE_SCRIPT $POD:/tmp/perf_traverse.sh -n $NAMESPACE -c istio-proxy
        kubectl exec -n $NAMESPACE -c istio-proxy $POD -- chmod +x /tmp/perf_traverse.sh
        kubectl exec -n $NAMESPACE -c istio-proxy $POD -- /tmp/perf_traverse.sh

        kubectl cp $POD:/tmp/perf_results ./perf_results/$POD -n $NAMESPACE -c istio-proxy
    done
}

MESH_TYPE=$1
if [ -z "$MESH_TYPE" ]; then
    echo "Usage: $0 <mesh_type>"
    exit 1
fi

if [ "$MESH_TYPE" == "cilium" ]; then
    echo "Running perf for Cilium"
    PERF_EXECUTE_SCRIPT="perf_cilium.sh"

    env_install

    # Run benchmark script
    ../overhead/benchmark_simple.sh &
    # Give some time for the benchmark to start
    sleep 10

    perf_cilium
else if [ "$MESH_TYPE" == "istio" ]; then
    echo "Running perf for Istio"
    PERF_EXECUTE_SCRIPT="perf_istio.sh"
    
    # Run benchmark script
    ../overhead/benchmark_simple.sh &
    # Give some time for the benchmark to start
    sleep 10

    perf_istio
else
    echo "Unsupported mesh type: $MESH_TYPE"
    exit 1
fi
fi