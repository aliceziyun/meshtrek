FROM docker.io/istio/proxyv2:1.26.0
RUN apt-get update && \
    apt-get install -y \
        curl \
        iptables \
        bpftrace \
        bcc \
        binutils \ 
        gdb