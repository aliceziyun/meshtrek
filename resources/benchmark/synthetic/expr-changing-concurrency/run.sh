#!/bin/bash

cd $(dirname $0)
mkdir -p results

random_seed=123
# for folder in branch16-yamls branch1-yamls; do
for folder in branch1-yamls; do
    for concurrency in 2 4 8 16 32; do
        outfile="results/$folder-l2-c$concurrency.log"
        rm -f $outfile
        temp_env=$(mktemp)
        python3 ../gen_processing_time.py fanout-w16 $random_seed >temp_env
        echo "export ISTIO_CONCURRENCY=$concurrency" >>temp_env
        source temp_env
        
        cat temp_env >> $outfile
        rm temp_env

        for file in $(ls $folder/*.yaml); do
            envsubst < $file | kubectl delete -f - 
        done

        for file in $(ls $folder/*.yaml); do
            envsubst < $file | kubectl apply -f - 
        done

        sleep 30
        kubectl get pods -o wide >> $outfile

        # get service0 ip
        service0_ip=$(kubectl get svc service0 -o jsonpath='{.spec.clusterIP}')
        ~/istio-1.26.0/wrk2/wrk -t4 -c16 -R 50 -d 30 -L http://$service0_ip/endpoint1 >> $outfile
    done
done