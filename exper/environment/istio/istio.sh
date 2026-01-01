# this script is to setup Istio environment
NAMESPACE=$1

# download istio, note this must be done with kubenetes cluster exists
cd ~
export ISTIO_VERSION=1.26.0
curl -L https://istio.io/downloadIstio | ISTIO_VERSION=$ISTIO_VERSION sh -
cd istio-1.26.0
export PATH=$PWD/bin:$PATH
# install service mesh for bookinfo application
istioctl install -f ~/meshtrek/resources/istio_config/no_resource_limit.yaml -y
kubectl create namespace $NAMESPACE
kubectl label namespace $NAMESPACE istio-injection=enabled

# download wrk2 for performance test
sudo apt install libssl-dev
sudo apt install zlib1g-dev
git clone https://github.com/giltene/wrk2.git
cd wrk2
make
cd ..