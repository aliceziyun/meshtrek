import subprocess
import os
import math
import time
import argparse

from exper.shell_helper import ShellHelper   

class MeshConfigFinder:
    def __init__(self, rps, namespace, config_file):
        self.rps = rps
        self.mesh_type = "ambient"
        self.namespace = namespace

        if namespace == "hotel":
            self.thread = 10
            self.connection = 40

        self.shell_helper = ShellHelper(config_file)
        self.basepath = "~/meshtrek/exper/"
    
    def reset_cluster(self):
        print("[*] Resetting the cluster...")

        print("[*] Deleting ambient waypoints if any...")
        if self.mesh_type == "ambient":
            # Reconfigure ambient waypoints
            self.shell_helper.execute_script(
                self.shell_helper.config["nodes"][0],
                self.shell_helper.config["nodes_user"],
                os.path.join(self.basepath, "./metric/script/ambient_config.sh"),
                ["delete"]
            )

        print("[*] Deleting and restarting the cluster...")

        # Delete the cluster
        self.shell_helper.execute_script(
            self.shell_helper.config["nodes"][0],
            self.shell_helper.config["nodes_user"],
            os.path.join(self.basepath, "./metric/script/cluster_operation.sh"),
            [self.namespace, "delete"]
        )

        print("[*] Resetting databases if any...")

        # Reset the database for hotel
        if self.namespace == "hotel":
            self.shell_helper.execute_parallel(
                os.path.join(self.basepath, "./metric/script/reset_database_for_hotel.sh"), mode=1
            )

            time.sleep(5)

        # Restart the cluster
        self.shell_helper.execute_script(
            self.shell_helper.config["nodes"][0],
            self.shell_helper.config["nodes_user"],
            os.path.join(self.basepath, "./metric/script/cluster_operation.sh"),
            [self.namespace, "launch"]
        )

        print("[*] Reconfiguring the mesh...")

        if self.mesh_type == "ambient":
            # Reconfigure ambient waypoints
            output = self.shell_helper.execute_script(
                self.shell_helper.config["nodes"][0],
                self.shell_helper.config["nodes_user"],
                os.path.join(self.basepath, "./metric/script/ambient_config.sh"),
                ["apply_each_service"]
            )

            time.sleep(5)

            output = self.shell_helper.execute_script(
                self.shell_helper.config["nodes"][0],
                self.shell_helper.config["nodes_user"],
                os.path.join(self.basepath, "./metric/script/inject_shadow_ambient.sh"),
            )

            time.sleep(5)

            output = self.shell_helper.execute_script(
                self.shell_helper.config["nodes"][0],
                self.shell_helper.config["nodes_user"],
                os.path.join(self.basepath, "./metric/script/ambient_config.sh"),
                ["bind_each_service"]
            )

        # elif self.mesh_type == "istio":
        #     # L4 only policy
        #     output = self.shell_helper.execute_script(
        #         self.shell_helper.config["nodes"][0],
        #         self.shell_helper.config["nodes_user"],
        #         os.path.join(self.basepath, "./metric/script/l4_only_istio.sh"),
        #     )

        time.sleep(10)

    def do_synthetic_exp(self):
        print("[*] Cleaning up environment...")

        # 重启集群
        self.reset_cluster()

        print(f"[*] Starting RPS experiment with RPS={self.rps}...")

        # 在远端运行rps_inc脚本
        output = self.shell_helper.execute_script(
                self.shell_helper.config["nodes"][0],
                self.shell_helper.config["nodes_user"],
                os.path.join(self.basepath, "./rps_inc/rps_inc.sh"),
                [str(self.rps), self.mesh_type]
        )
        
        with open("rps_exp_log_ambient_np.txt", "a") as f:
            f.write(f"RPS={self.rps} Experiment Output:\n")
            f.write(output + "\n\n")

        print(f"[*] RPS experiment with RPS={self.rps} completed.")

        # scp拷贝结果到本地
        target_dir = f"../../{self.rps}_trace_results"
        local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), target_dir)
        self.shell_helper.scp_from_remote(
            "trace_res",
            local_path,
            self.shell_helper.config["nodes"][0],
            self.shell_helper.config["nodes_user"],
            self.shell_helper.config["nodes_home"]
        )

        print(f"[*] Results copied to local path: {local_path}")

        # 在远端删除结果文件
        self.shell_helper.execute_script(
                self.shell_helper.config["nodes"][0],
                self.shell_helper.config["nodes_user"],
                os.path.join(self.basepath, "./rps_inc/rps_delete_res.sh"),
        )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Do trace of experiment")
    parser.add_argument("--rps", type=int, required=True, help="RPS value for the synthetic experiment")
    parser.add_argument("--namespace", type=str, required=True, help="Mesh namespace to use")
    args = parser.parse_args()

    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../config.json")
    config_finder = MeshConfigFinder(args.rps, args.namespace, config_path)
    config_finder.do_synthetic_exp()