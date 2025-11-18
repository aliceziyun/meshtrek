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
            exit(1)
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

class KubeConfigFinder:
    def __init__(self, core, namespace, config_file):
        self.core = core
        self.thread = math.floor(core * 0.8)
        self.connection = self.thread
        self.rps_base = 20
        self.namespace = namespace
        self.duration = 30

        self.rps_start = 100
        self.rps_step = 100
        self.end_rps = 700
        
        self.base_p50 = 0
        self.count = 0

        self.batch = 1

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
    
    def execute_batch(self, rps):
        avg_p50, avg_rps = 0, 0
        script_path = os.path.join(self.basepath, "./overhead/benchmark.sh")
        for _ in range(self.batch):
            output = self.shell_helper.execute_script(
                self.shell_helper.config["nodes"][0],
                self.shell_helper.config["nodes_user"],
                script_path,
                [str(self.namespace), str(self.thread), str(self.connection), str(rps), str(self.duration)]
            )
            avg_p50 += get_p50(output)
            avg_rps += get_achieved_RPS(output)
            self.reset_cluster()
        
        return avg_p50 / self.batch, avg_rps / self.batch
    
    def reset_cluster(self):
        print("[*] Resetting the cluster...")

        # Delete the cluster
        self.shell_helper.execute_script(
            self.shell_helper.config["nodes"][0],
            self.shell_helper.config["nodes_user"],
            os.path.join(self.basepath, "./metric/script/cluster_operation.sh"),
            [self.namespace, "delete"]
        )

        # Reset the database
        self.shell_helper.execute_parallel(
            os.path.join(self.basepath, "./metric/script/reset_database_for_hotel.sh"), mode=1
        )

        # Restart the cluster
        self.shell_helper.execute_script(
            self.shell_helper.config["nodes"][0],
            self.shell_helper.config["nodes_user"],
            os.path.join(self.basepath, "./metric/script/cluster_operation.sh"),
            [self.namespace, "launch"]
        )
        time.sleep(30)

    def find_best_RPS(self):
        print("[*] Testing best RPS without CPU limits...")

        # First get the base p50 with low RPS
        base_p50, _ = self.execute_batch(self.rps_base)

        print(f"[*] Base p50 latency at {self.rps_base} RPS: {base_p50} ms")
        self.check_p50(base_p50)
        print("--------------------------------------------------")

        current_rps = self.rps_start
        while True:
            p50, achieved_RPS = self.execute_batch(current_rps)

            print(f"[*] Target RPS: {current_rps}, Achieved RPS: {achieved_RPS}, p50 latency: {p50} ms")

            if achieved_RPS == 0:
                print("[*] Achieved RPS is 0, stopping test.")
                break

            if p50 > self.base_p50 * 1.5:
                print(f"[*] p50 latency {p50} ms exceeded base p50 latency threshold, stopping test.")
                break
            
            current_rps += self.rps_step
        
        best_rps = math.floor(achieved_RPS/10) * 10
        print("[*] Finished testing best RPS, result is {} RPS".format(best_rps))
        return best_rps

    def find_best_config(self):
        # clean up the environment first
        print("[*] Cleaning up the environment...")
        self.reset_cluster()

        # Find best RPS in coarse-grained
        print("[*] Finding best RPS in coarse-grained...")
        best_rps = self.find_best_RPS()

        # Find best RPS in fine-grained
        print("[*] Finding best RPS in fine-grained...")
        self.batch = 3
        self.duration = 60
        self.rps_start = best_rps - 100
        self.rps_step = 10
        best_rps = self.find_best_RPS()

        # Find best thread
        print("[*] Finding best thread...")
        best_thread = self.thread
        best_connection = self.connection
        while True:
            self.rps_start = best_rps
            self.thread += 1
            self.connection = self.thread
            print(f"[*] Testing with thread={self.thread}, connection={self.connection}")
            achieved_RPS = self.find_best_RPS()
            if achieved_RPS > best_rps:
                best_rps = achieved_RPS
                best_thread = self.thread
                best_connection = self.connection
            else:
                break
        self.thread = best_thread
        self.connection = best_connection

        # Find best connection
        print("[*] Finding best connection...")
        while True:
            self.rps_start = best_rps
            self.connection += 2
            print(f"[*] Testing with thread={self.thread}, connection={self.connection}")
            achieved_RPS = self.find_best_RPS()
            if achieved_RPS > best_rps:
                best_rps = achieved_RPS
                best_connection = self.connection
            else:
                break
        self.connection = best_connection

        print(f"[*] Best configuration found: thread={self.thread}, connection={self.connection}, best RPS={best_rps}")

    # def do_repeat_measurement(self):
    #     print("[*] Starting repeat measurements...")
    #     print("[*] Cleaning up the environment...")
    #     self.reset_cluster()

    #     self.batch = 3
    #     self.rps_step = 10
    #     _ = self.find_best_RPS()

    #     print("--------------------------------------------------")

    #     while self.thread < 20:
    #         self.thread += 1
    #         self.connection = self.thread
    #         print(f"[*] Testing with thread={self.thread}, connection={self.connection}")
    #         _ = self.find_best_RPS()

    #     print("--------------------------------------------------")

    #     self.connection = 12
    #     self.thread = 12
    #     while self.connection < 30:
    #         self.connection += 2
    #         print(f"[*] Testing with thread={self.thread}, connection={self.connection}")
    #         _ = self.find_best_RPS()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find the best Kubernetes configuration")
    parser.add_argument("--core", type=int, required=True, help="Number of CPU cores available")
    parser.add_argument("--namespace", type=str, required=True, help="Kubernetes namespace to use")
    args = parser.parse_args()

    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../config.json")
    config_finder = KubeConfigFinder(args.core, args.namespace, config_path)
    # config_finder.do_repeat_measurement()
    # config_finder.find_best_config