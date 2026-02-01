#!/bin/bash

cd $(dirname $0)
mkdir -p results

random_seed=123
# for each folder of yamls
# for folder in branch1-yamls branch2-yamls branch4-yamls branch8-yamls branch16-yamls; do
for folder in branch16-yamls; do
    for istio_enabled in false; do
        echo "Running with istio_enabled=$istio_enabled in folder=$folder"
        outfile="results/$folder-istio-$istio_enabled.log"
        rm -f $outfile
        if [ "$istio_enabled" = true ]; then
            kubectl label namespace default istio-injection=enabled --overwrite
        else
            kubectl label namespace default istio-injection-
        fi
        temp_env=$(mktemp)
        python3 ../gen_processing_time.py fanout-w16 $random_seed >temp_env
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

        # sleep 30
        ~/wrk/wrk -t16 -c128 -d 30 -L http://$service0_ip/endpoint1 >> $outfile.throughput
    done
done