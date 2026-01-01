#!/bin/bash

rm -rf ~/meshtrek/resources/envoy_filter/listeners
rm -r ~/meshtrek/resources/envoy_filter/generated_envoyfilters
~/meshtrek/resources/envoy_filter/istio_proxy_config.sh

cd ~/meshtrek/resources/envoy_filter
python3 ./generate_l4_policy.py

kubectl apply -Rf ./generated_envoyfilters/ -n hotel

sleep 30