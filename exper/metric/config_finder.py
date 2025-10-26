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
    return 0.0

stages = ["INIT", "THREAD", "CONNECTION", "CPU", "END"]

class KubeConfigFinder:
    def __init__(self):
        self.config = {
            "target_RPS": 150,
            "thread": 4,
            "connection": 4,
            "cpu_for_each_pod": 500
        }

        self.namespace = "hotel"
        self.duration = 60
        self.current_stage = stages[0]
    
    def run_benchmark(self):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        script_path = os.path.join(base_dir, "./overhead/benchmark.sh")
        achieved_RPS = 0.0
        # Run benchmark three times
        for _ in range(3):
            output = execute_script(script_path, [self.namespace, str(self.config["thread"]), str(self.config["connection"]), str(self.config["target_RPS"]), str(self.duration)])
            achieved_RPS += get_achieved_RPS(output)
        return achieved_RPS / 3

    def init_cluster(self):
        script_path = os.path.join(os.path.dirname(__file__), "script/confine_cpu.sh")
        execute_script(script_path, [str(self.config["cpu_for_each_pod"]) + "m", self.namespace])
        self.current_stage = stages[1]

    def find_best_RPS(self):
        while True:
            achieved_RPS = self.run_benchmark()
            if self.config["target_RPS"] - achieved_RPS < 20:
                self.config["target_RPS"] += 10
                continue
            else:
                self.config["target_RPS"] -= 10 # step back
                break
    
    def find_best_config(self):
        while True:
            if self.current_stage == "INIT":
                print("[*] Initializing cluster...")
                self.init_cluster()
                self.find_best_RPS()
                self.current_stage = stages[1]
                continue
            elif self.current_stage == "THREAD":
                self.config["thread"] += 1
                old_RPS = self.config["target_RPS"]
                print(f"[*] Testing with thread={self.config['thread']}")
                self.find_best_RPS()
                if self.config["target_RPS"] > old_RPS:
                    continue
                else:
                    self.config["thread"] -= 1
                    self.current_stage = stages[2]
                    continue
            elif self.current_stage == "CONNECTION":
                self.config["connection"] += 2
                old_RPS = self.config["target_RPS"]
                print(f"[*] Testing with connection={self.config['connection']}")
                self.find_best_RPS()
                if self.config["target_RPS"] > old_RPS:
                    continue
                else:
                    self.config["connection"] -= 2
                    self.current_stage = stages[3]
                    continue
            elif self.current_stage == "CPU":
                old_RPS = self.config["target_RPS"]
                self.config["cpu_for_each_pod"] += 500
                script_path = os.path.join(os.path.dirname(__file__), "script/confine_cpu.sh")
                execute_script(script_path, [str(self.config["cpu_for_each_pod"]) + "m", self.namespace])
                print(f"[*] Testing with cpu_for_each_pod={self.config['cpu_for_each_pod']}m")
                self.find_best_RPS()
                if self.config["target_RPS"] > old_RPS:
                    self.current_stage = stages[1]
                    continue
                else:
                    self.config["cpu_for_each_pod"] -= 500
                    self.current_stage = stages[4]
                    continue
            elif self.current_stage == "END":
                print("[*] Script complete.")
                break
        return self.config
    
if __name__ == "__main__":
    finder = KubeConfigFinder()
    best_config = finder.find_best_config()
    print("Best Config Found:")
    print(best_config)