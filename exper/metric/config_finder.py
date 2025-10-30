import subprocess
import os
import math
import time
import argparse

def execute_script(script_path: str, args: list = []):
    result = subprocess.run([script_path] + list(map(str, args)), capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Script {script_path} failed with error: {result.stderr}")
    return result.stdout

def get_achieved_RPS(output):
    for line in output.splitlines():
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
    def __init__(self, core, namespace):
        self.thread = math.floor(core * 0.8)
        self.connection = self.thread
        self.rps_base = 10
        self.namespace = namespace
        self.duration = 30

        self.rps_start = 100
        self.rps_step = 100
        
        self.base_p50 = 0
        self.count = 0

        self.batch = 1

    def check_p50(self, p50):
        self.count += 1
        if self.base_p50 == 0:
            self.base_p50 = p50
        else:
            if p50 > self.base_p50 * 2:
                print(f"[!] The experiment enviroment may be corrupted. Please reset the environment.")
                exit(1)
            else:
                self.base_p50 = (self.base_p50 * (self.count - 1) + p50) / self.count
    
    def execute_batch(self):
        avg_p50, avg_rps = 0, 0
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        script_path = os.path.join(base_dir, "./overhead/benchmark.sh")
        for _ in range(self.batch):
            output = execute_script(script_path, [self.namespace, str(self.thread), str(self.connection), str(self.rps_base), str(self.duration)])
            avg_p50 += get_p50(output)
            avg_rps += get_achieved_RPS(output)
            time.sleep(10)
        
        return avg_p50 / self.batch, avg_rps / self.batch

    def find_best_RPS(self):
        print("[*] Testing best RPS without CPU limits...")

        # First get the base p50 with low RPS
        base_p50, _ = self.execute_batch()

        print(f"[*] Base p50 latency at {self.rps_base} RPS: {base_p50} ms")
        self.check_p50(base_p50)
        print("--------------------------------------------------")

        current_rps = self.rps_start
        while True:
            p50, achieved_RPS = self.execute_batch()

            print(f"[*] Target RPS: {current_rps}, Achieved RPS: {achieved_RPS}, p50 latency: {p50} ms")

            if achieved_RPS == 0:
                print("[*] Achieved RPS is 0, stopping test.")
                break

            if p50 > base_p50 * 10:
                print(f"[*] p50 latency {p50} ms exceeded base p50 latency threshold, stopping test.")
                break
            
            current_rps += self.rps_step
            time.sleep(30)
        
        best_rps = math.floor(achieved_RPS/10) * 10
        print("[*] Finished testing best RPS, result is {} RPS".format(best_rps))
        return best_rps

    def find_best_config(self):
        # Find best RPS in coarse-grained
        print("[*] Finding best RPS in coarse-grained...")
        best_rps = self.find_best_RPS()

        # Find best RPS in fine-grained
        print("[*] Finding best RPS in fine-grained...")
        self.rps_base = best_rps - self.rps_step
        self.rps_step = 10
        best_rps = self.find_best_RPS()

        # Find best thread
        self.duration = 60
        print("[*] Finding best thread...")
        self.rps_base = best_rps
        best_thread = self.thread
        best_connection = self.connection
        while True:
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find the best Kubernetes configuration")
    parser.add_argument("--core", type=int, required=True, help="Number of CPU cores available")
    parser.add_argument("--namespace", type=str, required=True, help="Kubernetes namespace to use")
    args = parser.parse_args()

    config_finder = KubeConfigFinder(args.core, args.namespace)
    config_finder.find_best_config()