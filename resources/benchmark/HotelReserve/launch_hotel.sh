sudo apt-get -y install luarocks
sudo luarocks install luasocket

# clone benchmark
git clone https://github.com/delimitrou/DeathStarBench.git ~/DeathStarBench

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

# deploy DeathStar
cd ~/DeathStarBench/
kubectl create namespace hotel
# sudo ~/DeathStarBench/hotelReservation/kubernetes/scripts/build-docker-images.sh
# kubectl apply -Rf ~/DeathStarBench/hotelReservation/kubernetes/ -n hotel
kubectl apply -Rf ~/meshtrek/resources/benchmark/HotelReserve/kubernetes/ -n hotel

cd ~/DeathStarBench/wrk2
sudo apt install -y libssl-dev
sudo apt install -y zlib1g-dev
git submodule update --init --recursive
make