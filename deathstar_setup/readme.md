## Setting

Use this folder to deploy the [DeathStar](https://github.com/delimitrou/DeathStarBench) benchmark on a Kubernetes cluster.

### 1. Prepare Node(s)

You can use one or more machines as Kubernetes nodes.

If you are using **Cloudlab**, the `3nodes-profile.xml` configuration is more similar to **MeshInsight**. Alternatively, you may use `2nodes-profile.xml` for a quicker startup, as m550 nodes are generally available.

### 2. Create Kubernetes Cluster

Ensure that both `init_kube_env.sh` and `init_benchmark.sh` scripts are present on your machine.

First, execute `init_kube_env.sh` to download all necessary components for Kubernetes. This script installs the container runtime, Kubernetes packages, and configures the iptables rules.

```shell
sudo chmod +x init_kube_env.sh
./init_kube_env.sh
```

After setting up the environment, run the following commands manually on your main node:

```shell
# main node
sudo kubeadm init --pod-network-cidr=10.244.0.0/16
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

sudo vim /run/flannel/subnet.env

# copy the following contents to this file and save
FLANNEL_NETWORK=10.240.0.0/16
FLANNEL_SUBNET=10.240.0.1/24
FLANNEL_MTU=1450
FLANNEL_IPMASQ=true
```

After completing these steps, run the following command to verify everything is working correctly:

```shell
kubectl get pods --all-namespaces
```

If you see all the pods in **RUNNING** status, it means your cluster is working correctly! :sunny:

### 3. Setup Benchmark

Run `init_benchmark.sh` to setup DeathStar benchmark.

```shell
sudo chmod +x init_benchmark.sh
./init_benchmark.sh
```

Finally, check the cluster status:

```shell
kubectl get pod
```

You should see all the pods have **two containers** (One is the side car), and they all in **RUNNING** status.:sunny: