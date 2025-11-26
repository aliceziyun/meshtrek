import sys
import random

service_reuse = {
    "dag-relay": [1, 1, 1, 1, 3, 3, 3],
    "dag-cross": [1, 1, 2, 1, 4],
    "dynamic-once": [1, 1, 0.8, 0.2, 0.8],
    "dynamic-twice": [1, 0.2, 0.3, 0.5, 0.16, 0.15, 0.35],
    "dynamic-cache": [1, 1, 0.25],
    "dynamic-cycle": [1, 1.34, 0.34, 0.5, 0.5],
    "chain-d2": [1, 1, 1],
    "chain-d4": [1, 1, 1, 1, 1, 1],
    "chain-d8": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    "fanout-w3": [1, 1, 1, 1],
    "fanout-w5": [1, 1, 1, 1, 1, 1],
    "fanout-w7": [1, 1, 1, 1, 1, 1, 1, 1],
    "fanout-w10": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    "dag-balanced": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    "dag-unbalanced": [1, 1, 1, 1, 1, 1, 1, 1]
}

leaf_nodes = {
    "chain-d2": [2],
    "chain-d4": [5],
    "chain-d8": [9],
    "fanout-w3": [1,2,3],
    "fanout-w10": [1,2,3,4,5,6,7,8,9,10],
    "fanout-w7": [1,2,3,4,5,6,7],
    "fanout-w5": [1,2,3,4,5],
    "dag-balanced": [4,5,6,7,8,9,10,11,12], 
    "dag-unbalanced": [5,6],
    "dag-relay": [5,6],
    "dag-cross": [4],
    "dynamic-once": [3,4],
    "dynamic-cache": [2],
    "dynamic-cycle": [3,4],
    "dynamic-twice": [2,5,6]
}


def get_baseline_service_processing_time_synthetic(topology, random_seed):
    target = "service0" # root service, make it the smalledst processing time
    num = len(service_reuse[topology])
    random.seed(random_seed)
    random_numbers = [random.gauss(40, 15) for i in range(num)]
    random_numbers = [abs(r)+20 for r in random_numbers]   # just in case
    random_numbers.sort()

    processing_time = {}
    for i in range(num):
        if f"service{i}" == target:
            processing_time[f"service{i}"] = round(random_numbers.pop(0)  / service_reuse[topology][i], 2) / 1000
        else:
            processing_time[f"service{i}"] = round(random_numbers.pop(-1)  / service_reuse[topology][i], 2) / 1000
        print(f"export PROCESSING_TIME_SERVICE{i}={'{:.4f}'.format(processing_time[f'service{i}'])}")
    return processing_time

if __name__ == "__main__":
    topology = sys.argv[1]
    seed = int(sys.argv[2])
    processing_time = get_baseline_service_processing_time_synthetic(topology, seed)