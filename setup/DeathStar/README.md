# Run DeathStar Bench

### 1. Setting up Cluster

**The kernel version should be higher than 6.1**

clone the repository:

```shell
git clone https://github.com/aliceziyun/meshtrek.git
```

Then run setup script **locally** to set up Kubernetes cluster

1. Fill in the configuration file `./setup/config.json` on your local machine:

   - `nodes_user`: username
   - `nodes_number`: number of nodes
   - `nodes`: IP addresses or hostnames of all nodes (**make sure the main node is listed first**)
   - `nodes_home`: home directory for all nodes

2. Run the setup script to create a runnable cluster.

   ```shell
   # under /meshtrek/setup directory
   python3 setup.py -f ./kube.sh -m 0
   ```

   After setting up the environment, login into main node and run the following commands manually on your main node:

   ```shell
   # do these manually on main node
   sudo kubeadm init --pod-network-cidr=10.244.0.0/16 --upload-certs
   mkdir -p $HOME/.kube
   sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
   sudo chown $(id -u):$(id -g) $HOME/.kube/config
   
   # network plugin
   kubectl apply -f https://raw.githubusercontent.com/coreos/flannel/master/Documentation/kube-flannel.yml
   
   # enable auto completion
   echo 'source <(kubectl completion bash)' >> ~/.bashrc
   source ~/.bashrc
   ```

   After the environment is set up, log in to the main node and run the following commands manually on the main node.

   Once the `kubeadm` command finishes, you will see a message similar to:

   > **"Run `kubeadm join` on other nodes..."**

   Copy this command into a temporary file, add `sudo` at the beginning, and place the file in the `meshtrek/setup` directory. Then run it locally:

   ```shell
   # under /meshtrek/setup directory
   python3 setup.py -f ./tmp.sh -m 1
   ```

   This will execute the temporary file on all worker nodes to join them to the cluster.

   After completing these steps, run the following command to verify that everything is working:

   ```shell
   kubectl get pods --all-namespaces
   ```

   If you see all the pods in ***\*RUNNING\**** status, your cluster is working correctly.

3. Setup Istio

   While logged in to the main node, run this on main node:

   ```shell
   ./meshtrek/setup/istio/istio.sh
   ```

   This will download and install Istio, and create a namespace called *test* for injecting sidecar containers.

### 2. Install DeathStar Bench

On the main node, run the following command:

```shell
sudo chmod +x ./meshtrek/setup/DeathStar/launch_death_star_bench.sh
./meshtrek/setup/DeathStar/launch_death_star_bench.sh
kubectl apply -Rf ./meshtrek/setup/HotelReserve -n test
```

After the installation completes, run: `kubectl get pod -n test`. If all pods show the **RUNNING** status, the installation was successful.

### 3. Test

1. Enable the logging option in Istio.

   ```shell
   sudo chmod +x ./meshtrek/exper/istio/log_all.sh
   ./meshtrek/exper/istio/log_all.sh > /dev/null
   # you'll see some error, but it can be ignored
   
   # get the log
   kubectl logs -n test [pod_name] -c istio-proxy
   ```

2. Run a single test:

   ```shell
   kubectl get svc frontend -n test
   curl "[frontend_ip_address]:5000/hotels?inDate=2015-04-19&outDate=2015-04-24&lat=38.187&lon=-122.175"
   ```

3. TCPDUMP in pod

   Suggest to use frontend and search, these two pods have root privileges.

   ```shell
   kubectl exec -it -n test [pod_name] -- /bin/bash
   
   # in pod
   apt update
   apt install tcpdump
   tcpdump -i any ...
   ```

4. **Run Trace**

   1. Run `trace_all.sh`：open `/meshtrek/exper/envoy/trace_all.sh`, change the variable `TRACE_SCRIPT` to the path of trace script. (**in this example, it should be the path of `./meshtrek/exper/envoy/uprobe_script`**).

      Then run this script. The script will fail on jaeger and consul pod. But all other pod should be fine.

   2. Run `./benchmark_trace.sh`: 

      ~~First, search `local function get_user()` to open file `./wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua`. Change the variable `local url =` to `"http://[frontend_address]:5000"`~~(Ignore this)

      Change to directory `~/meshtrek/DeathStar/DeathStarBench/hotelReservation`, then run `~/meshtrek/DeathStar/exper/envoy/benchmark_trace.sh` here.

   3. Analysis the result

      The result is in `~/trace_res/`. To generate the timeline graph, select a uber id in your log file, then open `~/meshtrek/exper/timeline/timeline_generator_grpc.py`, change the value of `target_x_request_id` to the uber id. Then run following command:

      ```shell
      python3 ~/meshtrek/exper/timeline/timeline_generator_grpc.py -d [path_of_trace_result_directory]
      ```

      It should generator the timeline of the request.

### 4. Analysis Log

For a request, its lifecycle will look like this in envoy log:

| Stage                           | Description                                                  | Log                                                          |
| ------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| Connection Established          | Envoy will allocate a new connection id to the request       | "raising connection event ..."                               |
| Http Parsing                    | Parsing raw bytes to http headers                            | "parsing xx bytes" -> "message complete"                     |
| Stream Created                  | Envoy will create a new stream for current request           | "request headers complete"                                   |
| Request Filters Chains          | Go series of filters chains                                  | "request headers complete" -> "router decoding headers"      |
| Upstream Connection Established | Write and read data with new upstream connection. Reponse's parsing happens in upstream connection. |                                                              |
| Response Filter Chains          | The response will be handled in previous [ConnectionId, StreamId], goes to another series of filter chains | "upstream response headers:" -> Codec completed encoding stream. |

