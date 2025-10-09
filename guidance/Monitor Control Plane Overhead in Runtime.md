## Monitor Control Plane Overhead in Runtime

本实验的目的：在后续的调整pod资源分配的实验中，我们不能忽视Kubernetes系统pod和Istio控制平面的开销。因此我们每次需要根据真实运行情况的数据，预留一部分的资源给这些系统pod。



目前集群中已有的内容：

1. helm已安装
2. 无istio注入的bookinfo application在namespace *bookinfo*下



## Install Prometheus

普罗米修斯是一个及时且fine-grained的检测容器cpu和memory使用量的工具。作为Kubernetes中的工具，普罗米修斯也是以pod的形式运行在集群中，并以一定的时间间隔采集当前集群中pod资源用量。

TODO：

Install Prometheus, and use `kubectl patch...` or `kubectl port-forward...` to expose Prometheus port to outside machine, so we can access the dashboard from our local machine.



## 监控一定负载下pod的资源用量

使用脚本向application发起较高负载的请求，并记录该过程中各pod的峰值cpu和memory用量。

脚本使用方法：

