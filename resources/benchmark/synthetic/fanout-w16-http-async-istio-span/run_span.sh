#!/bin/bash

cd $(dirname $0)
mkdir -p results

random_seed=123
# for each folder of yamls
# for folder in branch1-yamls branch2-yamls branch4-yamls branch8-yamls branch16-yamls; do
for folder in branch1-yamls; do
    for istio_enabled in true; do
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
        ~/meshtrek/exper/envoy/benchmark_trace.sh istio default 0 0 0 0 &

        sleep 10

        ~/meshtrek/exper/envoy/trace_all.sh istio default 25

        wait

        # rename the trace_output
        mv ~/trace_res ~/trace_res_"$folder"
    done
done