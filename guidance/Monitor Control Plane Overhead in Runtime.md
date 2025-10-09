## Monitor Control Plane Overhead in Runtime

本实验的目的：在后续的调整pod资源分配的实验中，我们不能忽视Kubernetes系统pod和Istio控制平面的开销。因此我们每次需要根据真实运行情况的数据，预留一部分的资源给这些系统pod。



目前集群中已有的内容：

1. helm已安装
2. 无istio注入的bookinfo application，在namespace *bookinfo*下



## Install Prometheus

普罗米修斯是一个及时且fine-grained的检测容器cpu和memory使用量的工具。作为Kubernetes中的工具，普罗米修斯也是以pod的形式运行在集群中，并以一定的时间间隔采集当前集群中pod资源用量。

TODO:

Install Prometheus, and use `kubectl patch...` or `kubectl port-forward...` to expose Prometheus port to outside machine, so we can access the dashboard from our local machine.



## 监控一定负载下pod的资源用量

使用脚本向application发起较高负载的请求，并记录该过程中各pod的峰值cpu和memory用量。

脚本使用方法：

```shell
cd ~meshtrek
./exper/benchmark_trace.sh <mesh_type> <micro_serivce> <RPS> <Duration>
```

- mesh_type: istio / cilium
- micro_service: bookinfo / hotel
- RPS: offered request per seconds
- Duration: how long the experiement should run, e.g 30s, 1m

### No Service-Mesh

TODO:

Run the script with: `./exper/benchmark_trace.sh none bookinfo 300 30m  `， 记录30分钟内以下pod的峰值cpu/memory用量

- All pods under `bookinfo` namespace
- All pods under `kube-flannel` namespace
- All pods under `kube-system` namespace

Suggestions:

- 在正式实验开始前，可以先将Duration设置成30s，简单验证一下数据采集是否可行。

- 如何让实验线程保持后台运行状态：

  ```shell
  tmux new -s <name>  # new tmux session
  # in tmux shell
  ./run_exper ...
  # CTRL+B +D to detach
  
  tmux attach -t <name>  # attach to the session
  ```

### With Service-Mesh

首先需要清理原实验，并向bookinfo namespace中注入istio

```shell
kubectl delete -f ~/istio-1.26.0/samples/bookinfo/platform/kube/bookinfo.yaml -n bookinfo
kubectl label namespace bookinfo istio-injection=enabled
kubectl apply -f ~/istio-1.26.0/samples/bookinfo/platform/kube/bookinfo.yaml -n bookinfo
```

TODO:

Run the script with: `./exper/benchmark_trace.sh none bookinfo 300 30m  `（本实验中不需要mesh_type这个参数）， 记录30分钟内以下pod的峰值cpu/memory用量

- All pods under `bookinfo` namespace
- All pods under `kube-flannel` namespace
- All pods under `kube-system` namespace
- Istio control plane pod, in namespace `istio-system`



## Next Step

在获取这些数据后，我们将根据采集到的资源消耗量：

1. 为system pods预留足够的cpu和memory
2. 固定pod调度模式，例如，我们会尽量把application中资源消耗大的pods调度到不同的节点上
3. 为application pod分配和峰值cpu成比例的资源
4. 由于bookinfo只是一个toy example，我们之后会将该方法重复用在hotel-reservation上，并将hotel-reservation作为参考。但bookinfo很适合上手，并固定研究方法。
