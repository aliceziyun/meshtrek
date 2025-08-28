FROM docker.io/istio/proxyv2:1.26.0
RUN apt-get update && \
    apt-get install -y \
        curl \
        iptables \
        bpftrace \
        bcc \
        binutils \ 
        gdb

RUN apt-get install -y python3 python3-pip && \
    apt-get install -y apt-transport-https ca-certificates curl clang llvm jq && \
    apt-get install -y libelf-dev libpcap-dev libbfd-dev binutils-dev build-essential make && \
    apt-get install -y linux-tools-common && \
    apt-get install -y bpfcc-tools kmod && \
    apt-get install -y pahole && \
    apt-get install -y vim

COPY ./customized_envoy /usr/local/bin/envoy
RUN chmod +x /usr/local/bin/envoy