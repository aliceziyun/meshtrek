#!/bin/bash

cd $(dirname "$0")
folder=k6-results-automate
mkdir -p $folder


kubectl label namespace default istio-injection=enabled
for limit in false true; do
        log_file="$folder/default.json"

        kubectl delete -f simple.yaml
        kubectl delete -f local-rate-limit.yaml
        sleep 5
        if [ "$limit" = "true" ]; then
            kubectl apply -f local-rate-limit.yaml
            log_file="$folder/limit.json"
        fi
        rm -f ${log_file}
        kubectl apply -f simple.yaml
        sleep 30
        #kubectl get pods >${log_file} 2>&1
        service0_ip=$(kubectl get svc service0 -o jsonpath='{.spec.clusterIP}')
        #~/istio-1.26.0/wrk2/wrk -t4 -c16 -R $input_rate -d 30 -L http://$service0_ip:80/expensive  >>${log_file} 2>&1
	URL="http://$service0_ip:80/expensive" k6 run --out json=$log_file k6-test.js
done

kubectl label namespace default istio-injection-
log_file="$folder/noistio.json"

kubectl delete -f simple.yaml
kubectl delete -f local-rate-limit.yaml
rm -rf $log_file
kubectl apply -f simple.yaml
sleep 30
#kubectl get pods >${log_file} 2>&1
service0_ip=$(kubectl get svc service0 -o jsonpath='{.spec.clusterIP}')
#~/istio-1.26.0/wrk2/wrk -t4 -c16 -R $input_rate -d 30 -L http://$service0_ip:80/expensive  >>${log_file} 2>&1
URL="http://$service0_ip:80/expensive" k6 run --out json=$log_file k6-test.js

# python3 k6-plot.py $folder/default.json --out $folder/default.png
# python3 k6-plot.py $folder/limit.json --out $folder/limit.png
# python3 k6-plot.py $folder/noistio.json --out $folder/noistio.png
