import subprocess
import os

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
                print(f"Achieved RPS: {rps_value}")
                return float(rps_value)


stages = ["INIT", "THREAD", "CONNECTION", "CPU", "END"]

class KubeConfigFinder:
    def __init__(self):
        self.config = {
            "target_RPS": 300,
            "thread": 4,
            "connection": 4,
            "cpu_for_each_pod": "500m"
        }

        self.namespace = "hotel"
        self.duration = 60
        self.current_stage = stages[0]
    
    def run_benchmark(self):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        script_path = os.path.join(base_dir, "./overhead/benchmark.sh")
        # Run benchmark three times
        for _ in range(3):
            execute_script(script_path, [self.namespace, str(self.config["thread"]), str(self.config["connection"]), str(self.config["target_RPS"]), str(self.duration)])

    def init_cluster(self):
        script_path = os.path.join(os.path.dirname(__file__), "script/confine_cpu.sh")
        execute_script(script_path, [self.config["cpu_for_each_pod"], self.namespace])
        self.current_stage = stages[1]

    def find_best_RPS(self):
        run_benchmark()