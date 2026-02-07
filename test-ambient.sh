#!/usr/bin/env bash
set -e

mkdir -p results

range="100 200 300 400 500"

kubectl label ns default istio.io/dataplane-mode-
~/istio-1.26.0/bin/istioctl waypoint delete --all
kubectl delete -f resources/benchmark/synthetic/ambient-expr/yamls
kubectl apply  -f resources/benchmark/synthetic/ambient-expr/yamls

sleep 60

for input in $range; do
  kubectl get pods > "results/local-4-16-${input}-30-bind-node.log"
  ./exper/envoy/benchmark_trace.sh none synthetic 10 40 "$input" 30 \
    > "results/nomesh-4-16-${input}-30-bind-node.log"
done


kubectl label ns default istio.io/dataplane-mode=ambient
# -------------------------------
# bind to waypoint on each node
# -------------------------------
~/istio-1.26.0/bin/istioctl waypoint delete --all
kubectl delete -f resources/benchmark/synthetic/ambient-expr/yamls
kubectl apply  -f resources/benchmark/synthetic/ambient-expr/yamls

sleep 10

./exper/metric/script/ambient_config_synthetic.sh apply_each_node
./exper/metric/script/ambient_config_synthetic.sh bind_each_node

sleep 60

for input in $range; do
  kubectl get pods > "results/local-4-16-${input}-30-bind-node.log"
  ./exper/envoy/benchmark_trace.sh none synthetic 10 40 "$input" 30 \
    > "results/local-4-16-${input}-30-bind-node.log"
done

# --------------------------------
# bind to remote waypoint per node
# --------------------------------
~/istio-1.26.0/bin/istioctl waypoint delete --all
kubectl delete -f resources/benchmark/synthetic/ambient-expr/yamls
kubectl apply  -f resources/benchmark/synthetic/ambient-expr/yamls

sleep 10

./exper/metric/script/ambient_config_synthetic.sh apply_each_node
./exper/metric/script/ambient_config_synthetic.sh bind_each_node_remote

sleep 60


for input in $range; do
  kubectl get pods > "results/remote-4-16-${input}-30-bind-node.log"
  ./exper/envoy/benchmark_trace.sh none synthetic 10 40 "$input" 30 \
    >> "results/remote-4-16-${input}-30-bind-node.log"
done

# --------------------------------
# bind to single waypoint
# --------------------------------
~/istio-1.26.0/bin/istioctl waypoint delete --all
kubectl delete -f resources/benchmark/synthetic/ambient-expr/yamls
kubectl apply  -f resources/benchmark/synthetic/ambient-expr/yamls

sleep 10

./exper/metric/script/ambient_config_synthetic.sh apply_each_node
./exper/metric/script/ambient_config_synthetic.sh bind_to_single_node

sleep 60


for input in $range; do
  kubectl get pods > "results/single-4-16-${input}-30-bind-node.log"
  ./exper/envoy/benchmark_trace.sh none synthetic 10 40 "$input" 30 \
    >> "results/single-4-16-${input}-30-bind-node.log"
done
