## An Instruction to Setup Nodes on Cloudlab
5 nodes m510 cluster，`m510`: 8 cores 2 threads 4GB RAM：[profile](https://www.cloudlab.us/p/browncs2690fa24/5_node_for_start)
Use this pubic profile to create a new experiment. (Next -> Next -> Finish)

## Run Setup Script
First, use your cloudlab information to fill the `config.json` in `./setup/environment`

In the root directory under the project, do the following command:
```sh
cd ./setup/environment
python3 setup_kube.py
```

Ideally, the kubernetes will be setup, run `kubectl get node`, if all nodes are Ready, means the nodes are sucessfully setup.