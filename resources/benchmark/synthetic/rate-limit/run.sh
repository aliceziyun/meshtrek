#!/bin/bash

cd $(dirname "$0")

mkdir -p results

# run without rate limit
for limit in false; do
    for input_rate in 500 600 700 800 900 1000 1100 1200 1300 1400 1500 1600 1700 1800 1900 2000; do
        log_file="results/noistio-${input_rate}.log"

        kubectl delete -f simple.yaml
        kubectl delete -f local-rate-limit.yaml
        sleep 5
        if [ "$limit" = "true" ]; then
            kubectl apply -f local-rate-limit.yaml
            log_file="results/limit-${input_rate}.log"
        fi
        rm -f ${log_file}
        kubectl apply -f simple.yaml
        sleep 30
        kubectl get pods >${log_file} 2>&1
        service0_ip=$(kubectl get svc service0 -o jsonpath='{.spec.clusterIP}')
        ~/istio-1.26.0/wrk2/wrk -t4 -c16 -R $input_rate -d 30 -L http://$service0_ip:80/expensive  >>${log_file} 2>&1
    done
done
