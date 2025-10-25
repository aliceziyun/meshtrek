import requests
import time
import json
from datetime import datetime

PROMETHEUS_URL = "http://localhost:9090"
NAMESPACES = ["kube-system", "kube-flannel", "monitoring", "hotel", "istio-system"]
INTERVAL = 10   # seconds
RUNNING_TIME = 10 * 60  # seconds
OUTPUT_FILE = "pod_metrics.log"

def query_prometheus(query: str):
    try:
        resp = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
        data = resp.json()
        if data["status"] != "success":
            print("Prometheus query failed:", data)
            return []
        return data["data"]["result"]
    except Exception as e:
        print("Query error:", e)
        return []
    
def fetch_pod_metrics(namespace: str):
    cpu_query = (
        f'sum by (pod) (rate(container_cpu_usage_seconds_total{{namespace="{namespace}",container!="",image!=""}}[5m]))'
    )
    mem_query = (
        f'sum by (pod) (container_memory_usage_bytes{{namespace="{namespace}",container!="",image!=""}})'
    )

    cpu_results = query_prometheus(cpu_query)
    mem_results = query_prometheus(mem_query)

    cpu_dict = {r["metric"]["pod"]: float(r["value"][1]) for r in cpu_results}
    mem_dict = {r["metric"]["pod"]: float(r["value"][1]) for r in mem_results}

    metrics = []
    for pod in set(cpu_dict.keys()) | set(mem_dict.keys()):
        metrics.append({
            "namespace": namespace,
            "pod": pod,
            "cpu_cores": cpu_dict.get(pod, 0.0),
            "memory_bytes": mem_dict.get(pod, 0.0)
        })
    return metrics

if __name__ == "__main__":
    start_time = time.time()
    while time.time() - start_time < RUNNING_TIME:
        all_data = []
        ts = datetime.utcnow().isoformat() + "Z"
        for ns in NAMESPACES:
            ns_data = fetch_pod_metrics(ns)
            for m in ns_data:
                m["timestamp"] = ts
                all_data.append(m)

        with open(OUTPUT_FILE, "a") as f:
            for m in all_data:
                f.write(json.dumps(m) + "\n")

        print(f"[{ts}] Collected {len(all_data)} records.")
        time.sleep(INTERVAL)