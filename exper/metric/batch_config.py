import subprocess
import os
import math
import time

NAMESPACE="hotel"

RPS_LOW = 20
RPS_START = 1020
RPS_STEP = 10

THREAD = 12
CONNECTION = 12
DURATION=60

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

def test_best_RPS():
    print("[*] Testing best RPS without CPU limits...")

    # First get the base p50 with low RPS
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    script_path = os.path.join(base_dir, "./overhead/benchmark.sh")
    output = execute_script(script_path, [NAMESPACE, str(THREAD), str(CONNECTION), str(RPS_LOW), str(DURATION)])

    base_p50 = get_p50(output)
    print(f"[*] Base p50 latency at {RPS_LOW} RPS: {base_p50} ms")
    print("--------------------------------------------------")

    current_rps = RPS_START
    while True:
        output = execute_script(script_path, [NAMESPACE, str(THREAD), str(CONNECTION), str(current_rps), str(DURATION)])
        achieved_RPS = get_achieved_RPS(output)
        p50_latency = get_p50(output)

        print(f"[*] Target RPS: {current_rps}, Achieved RPS: {achieved_RPS}, p50 latency: {p50_latency} ms")

        if achieved_RPS == 0:
            print("[*] Achieved RPS is 0, stopping test.")
            break

        if p50_latency > base_p50 * 10:
            print(f"[*] p50 latency {p50_latency} ms exceeded base p50 latency threshold, stopping test.")
            break
        
        current_rps += RPS_STEP
        time.sleep(30)
    
    best_rps = math.floor(achieved_RPS/10) * 10
    print("[*] Finished testing best RPS, result is {} RPS".format(best_rps))


if __name__ == "__main__":
    test_best_RPS()