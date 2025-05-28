## Deploy Kubernetes Cluster

This is an instruction about how to deploy a kubernetes cluster.

You can use one or more CloudLab node or local machines. But ensure these nodes can ping each other.

Fill `config.json` with required information (note that you need to make sure the first node in `node` field is main node. Then run `python3 setup.py -f ./init_kube_env.sh -m 0` to copy the script to node, and run the script to set up the environment.

**how to use `setup.py`**：

```shell
# mode: 
# 0 - execute on all nodes
# 1 - execute on worker nodes
# 2 - execute on main nodes
python3 setup.py -f [filepath] -m [mode=0|1|2]
```

After setting up the environment, run the following commands manually on your main node:

```shell
# main node
sudo kubeadm init --pod-network-cidr=10.244.0.0/16 --upload-certs
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config
```

Once the `kubeadm` command is completed, you will see a message at the end, such as:
 *"Run `kubeadm join` on other nodes..."* Copy this command and execute it on the other machines to add the worker nodes to the cluster.

(You can skip this step if you are using only one machine.)

```shell
# sudo kubeadm join ...
```

Additionally, you must apply a network plugin on the main node to ensure the CNI functions properly.

```shell
# run this only on main node
kubectl apply -f https://raw.githubusercontent.com/coreos/flannel/master/Documentation/kube-flannel.yml

# enable auto completion
echo 'source <(kubectl completion bash)' >> ~/.bashrc
source ~/.bashrc
```

After completing these steps, run the following command to verify everything is working correctly:

```shell
kubectl get pods --all-namespaces
```

If you see all the pods in **RUNNING** status, it means your cluster is working correctly! :sunny:

## Deploy Bookinfo with Jaeger

https://istio.io/latest/docs/examples/bookinfo/

https://istio.io/latest/docs/tasks/observability/distributed-tracing/jaeger/

```shell
python3 setup.py -f istio -m 2
```

After the istio and jaeger is downloaded on main node, run:

```shell
kubectl create namespace bookinfo
kubectl apply -f samples/bookinfo/platform/kube/bookinfo.yaml -n bookinfo
PRODUCTPAGE_IP=$(kubectl get service productpage -n bookinfo -o jsonpath='{.spec.clusterIP}')
PRODUCTPAGE_PORT=$(kubectl get service productpage -n bookinfo -o jsonpath='{.spec.ports[0].port}')
REQUEST_URL="${PRODUCTPAGE_IP}:${PRODUCTPAGE_PORT}"
```

You should see bookinfo pods are all in **RUNNING** status.

### Tracing the application with Jaeger

Send requests on main node to activate Jaeger (recommend to execute this request twice in order to get enough data):

```shell
for i in $(seq 1 100); do curl -s -o /dev/null "http://$REQUEST_URL/productpage"; done
```

Visit the Jaeger dashboard by running: `kubectl get service --all-namespaces`, find service tracing and its PORT, The external port is the one that maps to port 80.

### Measure application performance

```shell
./wrk2/wrk -t 16 -c 20 -d 60 -L http://$REQUEST_URL/productpage -R 100
```

