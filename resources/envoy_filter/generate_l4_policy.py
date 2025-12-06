import re
import yaml
import os
from pathlib import Path

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ===========================================
# Service List
# ===========================================
# services = ["frontend", "rate", "profile", "geo", "recommendation", "reservation", "search", "user"]
services = ["service0","service1"]

# ===========================================
# Input directory: listeners output files
# ===========================================
LISTENER_DIR = Path("listeners")

# Output directory
OUTPUT_DIR = Path("generated_envoyfilters")
OUTPUT_DIR.mkdir(exist_ok=True)

# ===========================================
# Regex match outbound listener lines
# ===========================================
OUTBOUND_RE = re.compile(
    r"(?P<address>\d+\.\d+\.\d+\.\d+)\s+"
    r"(?P<port>\d+)\s+.*?"
    r"Cluster:\s+outbound\|(?P<svcport>\d+)\|\|(?P<host>[a-zA-Z0-9\-]+)\.hotel.*"
)

INBOUND_RE = re.compile(
    r"^0\.0\.0\.0\s+\d+\s+Trans:.*?Addr:\s+\*:(?P<addrport>\d+).*?Cluster:\s+inbound\|(?P<svcport>\d+)\|\|"
)

# ===========================================
# Generate EnvoyFilter templates
# ===========================================
def make_envoyfilter(service, patches):
    unique_name = f"ef-tcp-{service}"

    return {
        "apiVersion": "networking.istio.io/v1alpha3",
        "kind": "EnvoyFilter",
        "metadata": {
            "name": unique_name,
            "namespace": "default"
        },
        "spec": {
            "workloadSelector": {
                "labels": {
                    "app": "hotel",
                }
            },
            "configPatches": patches
        }
    }


# ===========================================
# Parse listeners.txt
# Returns: service → list of (listener_name, cluster)
# ===========================================
def parse_listeners_from_file(pod, file_path: Path):
    inBoundFound = False

    if pod == None or pod not in services:
        return {}

    if not file_path.exists() or not file_path.is_file():
        print(f"[WARN] Listener file '{file_path}' not found for pod '{pod}'. Skipping.")
        return {}

    with open(file_path, "r") as f:
        lines = f.readlines()

    results = {svc: [] for svc in services}

    for line in lines:
        listener_name = None
        cluster = None

        m = OUTBOUND_RE.search(line)
        if not m:
            m = INBOUND_RE.search(line)
            if not m or inBoundFound:
                continue
            else:
                inBoundFound = True
                listener_name = "virtualInbound"
                cluster = f"inbound|{m.group('svcport')}||"
        else:
            address = m.group("address") 
            port = m.group("port") 
            host = m.group("host")
            cluster = f"outbound|{m.group('svcport')}||{host}.hotel.svc.cluster.local"
            listener_name = f"{address}_{port}"

            if host not in services:
                continue

        results[pod].append((listener_name, cluster))

    return results


# ===========================================
# one EnvoyFilter YAML per service
# ===========================================
def main():
    # Ensure input directory exists
    if not LISTENER_DIR.exists() or not LISTENER_DIR.is_dir():
        print(f"[WARN] listeners directory '{LISTENER_DIR}' not found. Nothing to process.")
        return

    # Iterate over each listener file and use filename (stem) as pod name
    processed = 0
    for file_path in sorted(LISTENER_DIR.glob("*")):
        if not file_path.is_file():
            continue

        pod = file_path.stem

        svc_data = parse_listeners_from_file(pod, file_path)

        for svc, items in svc_data.items():
            if not items:
                continue

            patches = []

            for (listener_name, cluster_name) in items:
                stat_prefix = f"tcp_{svc}_{cluster_name.split('|')[1]}"

                patch = {
                    "applyTo": "NETWORK_FILTER",
                    "match": {
                        "listener": {
                            "name": listener_name,
                            "filterChain": {
                                "filter": {
                                    "name": "envoy.filters.network.http_connection_manager"
                                }
                            }
                        }
                    },
                    "patch": {
                        "operation": "REPLACE",
                        "value": {
                            "name": "envoy.filters.network.tcp_proxy",
                            "typed_config": {
                                "@type": "type.googleapis.com/envoy.extensions.filters.network.tcp_proxy.v3.TcpProxy",
                                "stat_prefix": stat_prefix,
                                "cluster": cluster_name
                            }
                        }
                    }
                }

                patches.append(patch)

            envoyfilter_obj = make_envoyfilter(svc, patches)

            out_file = OUTPUT_DIR / f"envoyfilter-{svc}.yaml"
            with open(out_file, "w") as f:
                yaml.dump(envoyfilter_obj, f, sort_keys=False)

            print(f"[OK] {pod}: Generated file: {out_file} (contains {len(patches)} policies)")
            processed += 1

    if processed == 0:
        print("[WARN] No listener files produced any policies.")
    else:
        # After processing all files, write the special outbound filter once
        outbound_filter = {
            "apiVersion": "networking.istio.io/v1alpha3",
            "kind": "EnvoyFilter",
            "metadata": {
                "name": "replace-hcm-outbound",
                "namespace": "default"
            },
            "spec": {
                "workloadSelector": {
                    "labels": {
                        "app": "hotel"
                    }
                },
                "configPatches": [
                    {
                        "applyTo": "NETWORK_FILTER",
                        "match": {
                            "listener": {
                                "name": "virtualOutbound",
                                "filterChain": {
                                    "filter": {
                                        "name": "envoy.filters.network.http_connection_manager"
                                    }
                                }
                            }
                        },
                        "patch": {
                            "operation": "REPLACE",
                            "value": {
                                "name": "envoy.filters.network.tcp_proxy",
                                "typed_config": {
                                    "@type": "type.googleapis.com/envoy.extensions.filters.network.tcp_proxy.v3.TcpProxy",
                                    "stat_prefix": "l4_outbound",
                                    "cluster": "PassthroughCluster"
                                }
                            }
                        }
                    }
                ]
            }
        }
        special_out_file = OUTPUT_DIR / "envoyfilter-outbound.yaml"
        with open(special_out_file, "w") as sf:
            yaml.dump(outbound_filter, sf, sort_keys=False)
        print(f"[DONE] Processed {processed} files from '{LISTENER_DIR}'. Wrote special outbound filter to {special_out_file}.")

if __name__ == "__main__":
    main()