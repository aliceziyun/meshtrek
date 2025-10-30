## Determine the best configuration of Service Mesh

**Experiment goal:** Determine the best configuration and related data of the service mesh for a specific application.

|                   | Istio | Cilium | Ambient | Canal |
| ----------------- | ----- | ------ | ------- | ----- |
| Hotel-Reservation |       |        |         |       |
| Train-Ticket      |       |        |         |       |
| Social-Network    |       |        |         |       |

Note: Directly limiting the application's CPU may cause bugs, so during the experiment we give the application unlimited CPU and only limit the service mesh resources.



### Step1

Purpose: Identify the application's optimal RPS and resource allocation so that we can move its pods to fixed nodes and use this RPS as the baseline for future experiments.

#### Hotel-Reservation

**Deloy hotel-reservation**: 

Run `./meshtrek/setup/benchmark/HotelResere/launch_hotel.sh`. This will automatically setup the application under namespace `hotel`.

**Determine the best <thread, connection, RPS> for load test**

Run `python3 -u ~/meshtrek/exper/metric/config_finder.py > ~/meshtrek/exper/config_hotel.log`

The log file will be redirected to `~/meshtrek/exper/config_hotel.log`.



#### Possible Errors During Script Execution

1. `[!] Error responses detected during the benchmark. Please check the service health:` Restart all pods by running

   ```bash
   kubectl delete pod -n hotel --all
   ```

   Wait until all pods are in the **Running** state.

2. `[!] The base p50 latency is too high`: Check the initialization configuration. This issue usually isn’t caused by RPS settings. Verify the values of **threads** and **connections** — `wrk` has a bug: if the number of threads is greater than the RPS (e.g., `threads = 11`, `RPS = 10`), this problem can occur.
   If the issue persists, please contact me.

1. `[!] The experiment enviroment may be corrupted. Please reset the environment.`: Redeploy the CloudLab cluster. Before redeployment, save all output files from the previous experiment locally.
