import subprocess
import os
import math
import time
import argparse

from exper.shell_helper import ShellHelper   

class MeshConfigFinder:
    def __init__(self, rps, namespace, config_file):
        self.rps = rps
        self.mesh_type = "istio"
        self.namespace = namespace

        if namespace == "hotel":
            self.thread = 10
            self.connection = 40

        self.shell_helper = ShellHelper(config_file)
        self.basepath = "~/meshtrek/exper/"
    
    def reset_cluster(self):
        print("[*] Resetting the cluster...")

        if self.mesh_type == "ambient":
            # Reconfigure ambient waypoints
            self.shell_helper.execute_script(
                self.shell_helper.config["nodes"][0],
                self.shell_helper.config["nodes_user"],
                os.path.join(self.basepath, "./metric/script/ambient_config.sh"),
                ["delete"]
            )

        # Delete the cluster
        self.shell_helper.execute_script(
            self.shell_helper.config["nodes"][0],
            self.shell_helper.config["nodes_user"],
            os.path.join(self.basepath, "./metric/script/cluster_operation.sh"),
            [self.namespace, "delete"]
        )

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

        if self.mesh_type == "ambient":
            # Reconfigure ambient waypoints
            output = self.shell_helper.execute_script(
                self.shell_helper.config["nodes"][0],
                self.shell_helper.config["nodes_user"],
                os.path.join(self.basepath, "./metric/script/ambient_config.sh"),
                ["apply_each_service"]
            )

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

    def do_rps_exp(self):
        print("[*] Cleaning up environment...")

        # 重启集群
        # self.reset_cluster()

        print(f"[*] Starting RPS experiment with RPS={self.rps}...")

        # 在远端运行rps_inc脚本
        output = self.shell_helper.execute_script(
                self.shell_helper.config["nodes"][0],
                self.shell_helper.config["nodes_user"],
                os.path.join(self.basepath, "./rps_inc/rps_inc.sh"),
                [str(self.rps)]
        )
        print("[*]", output)

        # scp拷贝结果到本地
        target_dir = f"../../{self.rps}_trace_results"
        local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), target_dir)
        if not os.path.exists(local_path):
            os.makedirs(local_path)
        self.shell_helper.scp_from_remote(
            "trace_res",
            target_dir,
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
    parser = argparse.ArgumentParser(description="Find the best Mesh configuration")
    parser.add_argument("--rps", type=int, required=True, help="Type of service mesh")
    parser.add_argument("--namespace", type=str, required=True, help="Mesh namespace to use")
    args = parser.parse_args()

    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../config.json")
    config_finder = MeshConfigFinder(args.rps, args.namespace, config_path)
    config_finder.do_rps_exp()