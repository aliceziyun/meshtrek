## Monitor Control Plane Overhead in Runtime

**Purpose of the Experiment: **In the upcoming experiments on adjusting pod resource allocation, we must not overlook the overhead of Kubernetes system pods and the Istio control plane. Therefore, for each run, we need to reserve a portion of resources for these system pods based on real runtime data.



**Current Cluster Setup**

1. Helm is installed.
2. A *bookinfo* application is deployed in the *`bookinfo`* namespace, without Istio sidecar injection.



## Install Prometheus

Prometheus is a timely and fine-grained tool for monitoring container CPU and memory usage. As a tool in Kubernetes, Prometheus also runs in the cluster as a pod and collects pod resource usage at regular intervals.

**TODO:**

Install Prometheus, and use `kubectl patch...` or `kubectl port-forward...` to expose the Prometheus port to the outside machine, so that we can access the dashboard from our local machine.



## Monitoring Pod Resource Usage Under a Fixed Load

Use a script to send high-load requests to the application and record the peak CPU and memory usage of each pod during this process.

**Script usage**:

```shell
cd ~meshtrek
./exper/benchmark_trace.sh <mesh_type> <micro_serivce> <RPS> <Duration>
```

- mesh_type: istio / cilium
- micro_service: bookinfo / hotel
- RPS: offered request per seconds
- Duration: how long the experiment should run, e.g 30s, 1m

### No Service-Mesh

**TODO**:

Run the script with: `./exper/benchmark_trace.sh none bookinfo 300 30m  `, and try to record the peak CPU and memory usage within 30 minutes for the following pods:

- All pods under `bookinfo` namespace
- All pods under `kube-flannel` namespace
- All pods under `kube-system` namespace

Suggestions:

- You can record the data in any format, graph or csv, but in some human-readable format.

- Before starting the formal experiment, you can first set the Duration to 30s to quickly verify how and whether data collection works.

- How to keep the experiment thread running in the background:

  ```shell
  tmux new -s <name>  # new tmux session
  # in tmux shell
  ./run_exper ...
  # CTRL+B +D to detach
  
  tmux attach -t <name>  # attach to the session
  ```

### With Service-Mesh

First, clean up the previous experiment and inject Istio into the `bookinfo` namespace.

```shell
kubectl delete -f ~/istio-1.26.0/samples/bookinfo/platform/kube/bookinfo.yaml -n bookinfo
kubectl label namespace bookinfo istio-injection=enabled
kubectl apply -f ~/istio-1.26.0/samples/bookinfo/platform/kube/bookinfo.yaml -n bookinfo
```

**TODO**:

Run the script with: `./exper/benchmark_trace.sh none bookinfo 300 30m  `(in this experiment the `mesh_type` parameter is not required), and record the peak CPU and memory usage of the following pods within 30 minutes.

- All pods under `bookinfo` namespace
- All pods under `kube-flannel` namespace
- All pods under `kube-system` namespace
- Istio control plane pod, in namespace `istio-system`



## Next Step

After collecting these data, we will use the measured resource consumption to:

1. Reserve sufficient CPU and memory for system pods.
2. Fix the pod scheduling strategy — for example, we will try to schedule resource-intensive application pods onto different nodes.
3. Allocate resources to application pods in proportion to their peak CPU usage.
4. Since `bookinfo` is just a toy example, we will later repeat this method on `hotel-reservation` and use that as the real reference. However, `bookinfo` is well-suited for getting started and establishing the methodology.
