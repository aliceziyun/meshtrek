cd $(dirname $0)

mkdir -p results

# Pick two Ready worker nodes
mapfile -t NODES < <(
  kubectl get nodes --no-headers \
  | grep -v ' control' \
  | awk '$2=="Ready"{print $1}'
)
if [ "${#NODES[@]}" -lt 1 ]; then
  echo "ERROR: No Ready nodes found" >&2
  exit 1
fi
NODE1="${NODES[0]}"
NODE2="${NODES[1]:-${NODES[0]}}"   # fallback to NODE1 if only one nod
export WORKER_NODE_SERVICE0="$NODE2"
export WORKER_NODE_SERVICE1="$NODE2"
export WORKER_NODE_SERVICE1_BUSY="$NODE1"
export PROCESSING_TIME_SERVICE0=0.0100
export PROCESSING_TIME_SERVICE1=0.0100
export PROCESSING_TIME_SERVICE1_BUSY=0.1000

install() {
    for file in $(ls yamls/*.yaml); do
        envsubst < $file | kubectl apply -f - 
    done
}

uninstall() {
    for file in $(ls yamls/*.yaml); do
        envsubst < $file | kubectl delete -f - 
    done
}

run() {
    log_file=$1
    uninstall
    sleep 10
    install
    sleep 10
    kubectl get pods >results/$log_file
    service0_ip=$(kubectl get svc service0 -o jsonpath='{.spec.clusterIP}')
    ~/istio-1.26.0/wrk2/wrk -t4 -c16 -R 50 -d 30 -L http://$service0_ip/endpoint1 >>results/$log_file
    for pod in $(kubectl get pods -o jsonpath='{.items[*].metadata.name}'); do
        echo "Check lines for pod $pod" >>results/$log_file
        kubectl logs $pod | grep called | wc -l >>results/$log_file 2>&1
    done
}

# Without Istio
kubectl label namespace default istio-injection-
run noistio.txt

# With Istio
kubectl label namespace default istio-injection=enabled
run istio.txt

# With Istio but round-robin
kubectl apply -f l4.yaml
run istio-l4-only.txt
kubectl delete -f l4.yaml

# With Istio and locality
kubectl label node $NODE1 topology.kubernetes.io/region=node-1 
kubectl label node $NODE2 topology.kubernetes.io/region=node-2 
kubectl apply -f locality.yaml
run istio-locality.txt
kubectl delete -f locality.yaml
# Clean up labels
kubectl label node $NODE1 topology.kubernetes.io/region- --overwrite
kubectl label node $NODE2 topology.kubernetes.io/region- --overwrite