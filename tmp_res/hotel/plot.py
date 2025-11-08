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
                print(parts)
                rps.append(float(parts[4]))
                p50.append(float(parts[7]))
    return rps, p50

# Plotting scatter points of three different files
def plot_scatter(file1, file2, file3):
    rps1, p50_1 = read_file(file1)
    rps2, p50_2 = read_file(file2)
    rps3, p50_3 = read_file(file3)

    plt.figure(figsize=(10, 6))
    plt.scatter(rps1, p50_1, color='blue', label='No Limit')
    plt.scatter(rps2, p50_2, color='green', label='Istio Limit 1 core')
    plt.scatter(rps3, p50_3, color='red', label='Istio Limit 2 cores')

    plt.xlabel('Achieved RPS')
    plt.ylabel('P50 Latency (ms)')
    plt.title('RPS vs P50 Latency')
    plt.legend()
    plt.grid(True)
    plt.savefig('rps_vs_p50.png')
    plt.show()

plot_scatter("/Users/alicesong/Desktop/research/meshtrek/tmp_res/hotel/result_config_mesh.log", "/Users/alicesong/Desktop/research/meshtrek/tmp_res/hotel/result_config_mesh_istio_limit_1.log", "/Users/alicesong/Desktop/research/meshtrek/tmp_res/hotel/result_config_mesh_istio_limit_2.log")