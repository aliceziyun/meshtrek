#!/bin/bash

cd $(dirname $0)

random_seed=123
temp_env=$(mktemp)
python3 ../gen_processing_time.py simple-test $random_seed >temp_env
source temp_env
cat temp_env
rm temp_env

for file in $(ls simple-test/*.yaml); do
    envsubst < $file | kubectl apply -f - 
done