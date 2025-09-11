git clone https://github.com/delimitrou/DeathStarBench.git ~/DeathStarBench

kubectl create ns social
helm install socialnetwork ./DeathStarBench/socialNetwork/helm-chart/socialnetwork/ --namespace social

luarocks install luasocket

cd ~/DeathStarBench/wrk2
sudo apt install libssl-dev
sudo apt install zlib1g-dev
git submodule update --init --recursive
make