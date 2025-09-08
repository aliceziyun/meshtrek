#!/bin/bash

# traverse all the perf.data to perf.script
RES_DIR="/tmp/perf_results"
cd $RES_DIR

for PERF_FILE in $(ls *.data); do
    echo "Processing $PERF_FILE"
    perf script -i $PERF_FILE > "${PERF_FILE%.data}.script"
    rm $PERF_FILE
done