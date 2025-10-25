import re
import json
from shell_helper import ShellHelper

class KubeSetUp:
    def __init__(self, config_path):
        self.shell_helper = ShellHelper(config_path)

    def environment_setup(self):
        print("[*] Setting up Kubernetes environment on all nodes...")
        self.shell_helper.execute_parallel("./kube/kube.sh", mode=0)

    def init_kubernetes_on_main(self):
        print("[*] Initializing Kubernetes on main node...")
        config = self.shell_helper.config
        self.shell_helper.copy_files_to_nodes("./kube/init_kube.sh", mode=2)
        result = self.shell_helper.execute_script(0, config["nodes"][0], config["nodes_home"], config["nodes_user"], "./kube/init_kube.sh")
        match = re.search(r"(kubeadm join\s[\s\S]+?)(?:\n\n|\Z)", str(result))
        join_command = ""
        if match:
            join_command = match.group(1)
        else:
            print("[!] Failed to extract join command from kubeadm output.")
            exit(1)
        print(join_command)
        return join_command

    def join_workers_to_cluster(self, join_command):
        print("[*] Joining worker nodes to the Kubernetes cluster...")
        # write join command to file
        with open("./kube/join_kube.sh", "w") as f:
            f.write(f"sudo {join_command}")

        self.shell_helper.execute_parallel("./kube/join_kube.sh", mode=1)
        self.shell_helper.execute_parallel("./kube/after_join.sh", mode=2)

    def kube_cluster_setup(self):
        self.environment_setup()
        join_command = self.init_kubernetes_on_main()
        self.join_workers_to_cluster(join_command)

if __name__ == "__main__":
    kube_setup = KubeSetUp("./config.json")
    kube_setup.kube_cluster_setup()