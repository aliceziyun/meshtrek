import subprocess
import os
import math
import time
import argparse

from exper.shell_helper import ShellHelper

def get_achieved_RPS(output):
    for line in output.splitlines():
        if "Non-2xx or 3xx responses:" in line:
            print("[!] Error responses detected during the benchmark. Please check the service health.")
            print("[!] Error line:", line)
        #     exit(1)
        if "Requests/sec:" in line:
            parts = line.split("Requests/sec:")
            if len(parts) > 1:
                rps_value = parts[1].strip().split()[0]
                return float(rps_value)
    return 0.0

def get_p50(output):
    for line in output.splitlines():
        if "50.000%" in line:
            parts = line.split("50.000%")
            if len(parts) > 1:
                p50_value = parts[1].strip().split()[0]
                if p50_value.endswith("ms"):
                    p50_value = p50_value[:-2]
                elif p50_value.endswith("s"):
                    p50_value = float(p50_value[:-1]) * 1000
                return float(p50_value)
    return math.inf

def get_p99(output):
    for line in output.splitlines():
        if "99.000%" in line:
            parts = line.split("99.000%")
            if len(parts) > 1:
                p99_value = parts[1].strip().split()[0]
                if p99_value.endswith("ms"):
                    p99_value = p99_value[:-2]
                elif p99_value.endswith("s"):
                    p99_value = float(p99_value[:-1]) * 1000
                return float(p99_value)
    return math.inf

class MeshConfigFinder:
    def __init__(self, filter, config_file):
        self.mesh_type = "istio"
        self.namespace = "hotel"

        self.thread = 20
        self.connection = 80
        self.rps_start = 100

        self.duration = 30
        self.rps_step = 100
        self.rps_base = 20
        
        self.base_p50 = 0
        self.count = 0

        self.batch = 1

        self.filter = filter

        self.shell_helper = ShellHelper(config_file)
        self.basepath = "~/meshtrek/exper/"

    def check_p50(self, p50):
        self.count += 1
        if self.base_p50 == 0:
            self.base_p50 = p50
        if self.base_p50 > 1000:
            print(f"[!] The base p50 latency is too high ({self.base_p50} ms). Please check the environment.")
            exit(1)
        else:
            if p50 > self.base_p50 * 2:
                print(f"[!] The experiment enviroment may be corrupted. Please reset the environment.")
                exit(1)
            else:
                self.base_p50 = (self.base_p50 * (self.count - 1) + p50) / self.count
    
    def execute_batch(self, rps, thread = 0, connection = 0):
        if thread == 0:
            thread = self.thread
        if connection == 0:
            connection = self.connection
        avg_p50, avg_p99, avg_rps = 0, 0, 0
        script_path = os.path.join(self.basepath, "./overhead/benchmark.sh")
        for _ in range(self.batch):
            output = self.shell_helper.execute_script(
                self.shell_helper.config["nodes"][0],
                self.shell_helper.config["nodes_user"],
                script_path,
                [str(self.namespace), str(thread), str(connection), str(rps), str(self.duration)]
            )
            # print("Benchmark output:\n", output)
            p50 = get_p50(output)
            p99 = get_p99(output)
            res_rps = get_achieved_RPS(output)
            avg_p50 += p50
            avg_p99 += p99
            avg_rps += res_rps
            print("[* Result] Achieved RPS:", res_rps, "p50 latency:", p50, "p99 latency:", p99)
            self.reset_cluster()
        
        return avg_p50 / self.batch, avg_rps / self.batch
    
    def reset_cluster(self):
        print("[*] Resetting the cluster...")

        if self.filter == "opa" or self.filter == "all":
            # Delete the cluster
            self.shell_helper.execute_script(
                self.shell_helper.config["nodes"][0],
                self.shell_helper.config["nodes_user"],
                os.path.join(self.basepath, "./metric/script/cluster_operation.sh"),
                [self.namespace, "delete_opa"]
            )
        else:
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
        if self.filter == "opa" or self.filter == "all":
            self.shell_helper.execute_script(
                self.shell_helper.config["nodes"][0],
                self.shell_helper.config["nodes_user"],
                os.path.join(self.basepath, "./metric/script/cluster_operation.sh"),
                [self.namespace, "launch_opa"]
            )
        else:
            self.shell_helper.execute_script(
                self.shell_helper.config["nodes"][0],
                self.shell_helper.config["nodes_user"],
                os.path.join(self.basepath, "./metric/script/cluster_operation.sh"),
                [self.namespace, "launch"]
            )

        time.sleep(10)

    def apply_filter(self):
        # filter type can be: tap, opa(+header), rate limit, header
        # reset original filters
        print("[*] Resetting existing filters...")
        self.shell_helper.execute_script(
            self.shell_helper.config["nodes"][0],
            self.shell_helper.config["nodes_user"],
            os.path.join(self.basepath, "./metric/filter_script/filter_operation.sh"),
            [self.namespace, "delete"]
        )

        if self.filter == "tap":
            print("[*] Applying TAP filter...")
            self.shell_helper.execute_script(
                self.shell_helper.config["nodes"][0],
                self.shell_helper.config["nodes_user"],
                os.path.join(self.basepath, "./metric/filter_script/filter_operation.sh"),
                [self.namespace, "tap"]
            )
        elif self.filter == "opa":
            print("[*] Applying OPA filter...")
            self.shell_helper.execute_script(
                self.shell_helper.config["nodes"][0],
                self.shell_helper.config["nodes_user"],
                os.path.join(self.basepath, "./metric/filter_script/filter_operation.sh"),
                [self.namespace, "opa"]
            )
        elif self.filter == "header":
            print("[*] Applying Adding Custom Header filter...")
            self.shell_helper.execute_script(
                self.shell_helper.config["nodes"][0],
                self.shell_helper.config["nodes_user"],
                os.path.join(self.basepath, "./metric/filter_script/filter_operation.sh"),
                [self.namespace, "header"]
            )
        elif self.filter == "rate_limit":
            print("[*] Applying Rate Limiting filter...")
            self.shell_helper.execute_script(
                self.shell_helper.config["nodes"][0],
                self.shell_helper.config["nodes_user"],
                os.path.join(self.basepath, "./metric/filter_script/filter_operation.sh"),
                [self.namespace, "rate_limit"]
            )
        elif self.filter == "all":
            print("[*] Applying All filters (TAP + OPA + Header + Rate Limiting)...")
            self.shell_helper.execute_script(
                self.shell_helper.config["nodes"][0],
                self.shell_helper.config["nodes_user"],
                os.path.join(self.basepath, "./metric/filter_script/filter_operation.sh"),
                [self.namespace, "all"]
            )
        else:
            print(f"[!] Unknown filter type: {self.filter}. No filter will be applied.")
            exit(1)

    def end_to_end_exp(self):
        # clean up the environment first
        print("[*] Cleaning up the environment...")
        self.apply_filter()
        self.reset_cluster()

        # Directly do test 
        print("[*] Do end to end experiment on filter:", self.filter)
        self.batch = 3
        self.duration = 30
        self.rps_start = 100
        rps_end = 500
        self.rps_step = 100
        
        for current_rps in range(self.rps_start, rps_end + 1, self.rps_step):
            p50, achieved_RPS = self.execute_batch(current_rps)
            print(f"[*] Target RPS: {current_rps}, Achieved RPS: {achieved_RPS}, p50 latency: {p50} ms")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find the best Mesh configuration")
    parser.add_argument("--f", type=str, required=True, help="Filter type")
    args = parser.parse_args()

    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../config.json")
    config_finder = MeshConfigFinder(args.f, config_path)
    config_finder.end_to_end_exp()