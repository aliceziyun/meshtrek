#!/bin/bash

cd $(dirname $0)

export PROCESSING_TIME_SERVICE0=0.0100
export PROCESSING_TIME_SERVICE1=0.0100
export PROCESSING_TIME_SERVICE1_BUSY=0.1000
export WORKER_NODE_SERVICE0=node2.test.brown-atlas-pg0.utah.cloudlab.us
export WORKER_NODE_SERVICE1=node2.test.brown-atlas-pg0.utah.cloudlab.us
export WORKER_NODE_SERVICE1_BUSY=node1.test.brown-atlas-pg0.utah.cloudlab.us

for file in $(ls yamls/*.yaml); do
    envsubst < $file | kubectl apply -f - 
done
