import matplotlib.pyplot as plt

# read rps and p50
# the format is: [* Result] Achieved RPS: 570.17 p50 latency: 58.85
def read_file(file_path):
    rps = []
    p50 = []
    with open(file_path, "r") as f:
        for line in f:
            if "[* Result] Achieved" in line:
                parts = line.split(" ")
                # print(parts)
                rps.append(float(parts[4]))
                p50.append(float(parts[7]))
    return rps, p50

# Plotting scatter points of three different files
def plot_scatter(file1, file2, file3, file4, file5, file6):
    rps1, p50_1 = read_file(file1)
    rps2, p50_2 = read_file(file2)
    rps3, p50_3 = read_file(file3)
    rps4, p50_4 = read_file(file4)
    rps5, p50_5 = read_file(file5)
    rps6, p50_6 = read_file(file6)

    plt.figure(figsize=(10, 6))
    plt.ylim(5, 80)
    plt.scatter(rps1, p50_1, color='blue', label='Ambient', alpha=0.6)
    plt.scatter(rps2, p50_2, color='green', label='Ambient 2C', alpha=0.6)
    plt.scatter(rps3, p50_3, color='red', label='Ambient 4P', alpha=0.6)
    plt.scatter(rps4, p50_4, color='purple', label='Ambient 4P 1C', alpha=0.6)
    plt.scatter(rps5, p50_5, color='orange', label='Ambient 3P', alpha=0.6)
    plt.scatter(rps6, p50_6, color='brown', label='Ambient Each Service', alpha=0.6)

    plt.xlabel('Achieved RPS')
    plt.ylabel('P50 Latency (ms)')
    plt.title('RPS vs P50 Latency')
    plt.legend()
    plt.grid(True)
    plt.savefig('rps_vs_p50.png')
    plt.show()

def histogram_mesh():
    mesh_types = ["No Mesh", "Istio", "Cilium", "Ambient 1 Proxy", "Ambient 3 Proxies", "Ambient 4 Proxies", "Ambient Each Service"]
    p50 = [5.83, 20.01, 14.60, 21.73, 11.8, 10.7, 9.98]
    best_rps = [3600,600,1500,600,2800,1600,2800]

    # Rank by p50 latency
    ranked_mesh = sorted(zip(mesh_types, p50, best_rps), key=lambda x: x[1])
    mesh_types_ranked, p50_ranked, best_rps_ranked = zip(*ranked_mesh)

    # Plot bar chart for p50 latency
    x = range(len(mesh_types_ranked))
    plt.figure(figsize=(12, 6))
    plt.subplot(1, 2, 1)
    plt.bar(x, p50_ranked, color='skyblue')
    plt.xticks(x, mesh_types_ranked, rotation=45, ha='right')
    plt.ylabel('P50 Latency at Low Rate (ms)')
    plt.title('P50 Latency by Service Mesh Type')
    plt.ylim(0, max(p50_ranked) + 5)
    plt.grid(axis='y')

    # Rank by best RPS
    ranked_mesh_rps = sorted(zip(mesh_types, best_rps, p50), key=lambda x: x[1], reverse=True)
    mesh_types_ranked_rps, best_rps_ranked_rps, p50_ranked_rps = zip(*ranked_mesh_rps)

    # Plot bar chart for best RPS
    plt.subplot(1, 2, 2)
    plt.bar(x, best_rps_ranked_rps, color='lightcoral')
    plt.xticks(x, mesh_types_ranked_rps, rotation=45, ha='right')
    plt.ylabel('Best RPS')
    plt.title('Best RPS by Service Mesh Type')
    plt.ylim(0, max(best_rps_ranked_rps) + 500)
    plt.grid(axis='y')

    # Adjust layout and show the plot
    plt.tight_layout()
    plt.savefig('mesh_comparison.png')
    plt.show()

# file1 = "/Users/alicesong/Desktop/research/meshtrek/tmp_res/hotel/ambient/result_config_mesh.log"
# file2 = "/Users/alicesong/Desktop/research/meshtrek/tmp_res/hotel/ambient/result_config_mesh_2C.log"
# file3 = "/Users/alicesong/Desktop/research/meshtrek/tmp_res/hotel/ambient/result_config_mesh_4P.log"
# file4 = "/Users/alicesong/Desktop/research/meshtrek/tmp_res/hotel/ambient/result_config_mesh_4P_1C.log"
# file5 = "/Users/alicesong/Desktop/research/meshtrek/tmp_res/hotel/ambient/result_config_mesh_3P.log"
# file6 = "/Users/alicesong/Desktop/research/meshtrek/tmp_res/hotel/ambient/result_config_mesh_NP.log"
# plot_scatter(file1, file2, file3, file4, file5, file6)
histogram_mesh()