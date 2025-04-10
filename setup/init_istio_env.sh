# this script is to setup Istio environment

# make workload generator
cd ~/DeathStarBench/wrk2
git submodule update --init --recursive
make all

cd ~

# download luarocks
sudo apt-get install -y luarocks
sudo luarocks install luasocket

# download istio, note this must be done with kubenetes cluster exists
curl -L https://istio.io/downloadIstio | sh -
cd istio-1.25.1
export PATH=$PWD/bin:$PATH
istioctl install -f samples/bookinfo/demo-profile-no-gateways.yaml -y
kubectl label namespace default istio-injection=enabled

# download k8s gateway api
kubectl get crd gateways.gateway.networking.k8s.io &> /dev/null || \
{ kubectl kustomize "github.com/kubernetes-sigs/gateway-api/config/crd?ref=v1.2.1" | kubectl apply -f -; }

# TODO: add argument to control
# kubectl apply -f samples/bookinfo/platform/kube/bookinfo.yaml

# wrk2
# git clone https://github.com/giltene/wrk2.git
# cd wrk2
# make

# TrainTicket
git clone --depth=1 https://github.com/FudanSELab/train-ticket.git 
cd train-ticket/