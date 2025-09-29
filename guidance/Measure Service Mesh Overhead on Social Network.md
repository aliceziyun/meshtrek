## Measure Service Mesh Overhead on Social Network

Before the experiment, make sure every operation is ran under directory `./meshtrek`.

### Istio

1. Create a namespace for running application

   ```shell
   kubectl create namespace social
   kubectl label namespace social istio-injection=enabled
   ```

2. Deploy social network application

   ```shell
   helm install ./setup/SocialNetwork --namespace social
   ```

   *ps: helm is a tool to automatically deploy pods in Kubernetes cluster, this tool is already installed in the machine*

   Then run `kubectl get pod -n social` to check all pods in namespace social is **Running** states. And most pods should have a sidecar container running(2/2).

3. Run scripts to get service mesh time data

   Start two shells. In the first one, run:

   ```shell
   ./exper/trace_all.sh istio social
   ```

   After the first command shows *Pod-xxx is tracing...* and no error log appears, switch to the second shell, run:

   ```shell
   ./exper/benchmark_trace.sh istio social 40
   ```

   After the second script is done, you'll see a direcotry named `trace_res` under home directory.

4. Generate timeline data to check correctness:

   First open the entry file under `trace_res`, which is the frontend, with name `nginx-xxxxxx`. Scroll the file down a bit, ramdomly choose a `x-request-id` value.

   Open file `./exper/graph_gen/timeline_generator_grpc.py`, near line 130 there should be a variable called `target_x_request_id`, change it to the `x-request-id` you choose.

   Then Run:

   ```shell
   python3 ./exper/graph_gen/timeline_generator_grpc.py -d ~/trace_res
   ```

   *ps: the machine may not have required python environment installed, you probably need to install some package if you see anything missing.*

   You'll see a graph is generated under the directory you're running the script now. You can check whehter this graph looks correct.