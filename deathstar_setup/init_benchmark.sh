# this script is to setup Deathstart benchmark with Isoti deployed

# clone benchmark
git clone https://github.com/delimitrou/DeathStarBench.git

# make workload generator
cd ~/DeathStarBench/wrk2
git submodule update --init --recursive
make all

cd ~

# modification on files to make benchmark run correctly
sed -i 's|\$EXEC build -t "$USER"/"$IMAGE":"$TAG" -f Dockerfile . --platform linux/arm64,linux/amd64 --push|\$EXEC build -t "$USER"/"$IMAGE":"$TAG" -f Dockerfile . --load|' ~/DeathStarBench/hotelReservation/kubernetes/scripts/build-docker-images.sh
sed -i 's|- ./frontend|- /go/bin/frontend|' ~/DeathStarBench/hotelReservation/kubernetes/frontend/frontend-deployment.yaml
sed -i 's|- ./geo|- /go/bin/geo|' ~/DeathStarBench/hotelReservation/kubernetes/geo/geo-deployment.yaml
sed -i 's|- ./profile|- /go/bin/profile|' ~/DeathStarBench/hotelReservation/kubernetes/profile/profile-deployment.yaml
sed -i 's|- ./rate|- /go/bin/rate|' ~/DeathStarBench/hotelReservation/kubernetes/rate/rate-deployment.yaml
sed -i 's|- ./recommendation|- /go/bin/recommendation|' ~/DeathStarBench/hotelReservation/kubernetes/reccomend/recommendation-deployment.yaml
sed -i 's|- ./reservation|- /go/bin/reservation|' ~/DeathStarBench/hotelReservation/kubernetes/reserve/reservation-deployment.yaml
sed -i 's|- ./search|- /go/bin/search|' ~/DeathStarBench/hotelReservation/kubernetes/search/search-deployment.yaml
sed -i 's|- ./user|- /go/bin/user|' ~/DeathStarBench/hotelReservation/kubernetes/user/user-deployment.yaml

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

# deploy DeathStar
cd ~/DeathStarBench/
sudo ~/DeathStarBench/hotelReservation/kubernetes/scripts/build-docker-images.sh
kubectl apply -Rf ~/DeathStarBench/hotelReservation/kubernetes/