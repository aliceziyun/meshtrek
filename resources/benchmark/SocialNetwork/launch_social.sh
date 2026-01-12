curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
chmod 700 get_helm.sh
./get_helm.sh

git clone https://github.com/delimitrou/DeathStarBench.git ~/DeathStarBench

# fix scheduling
~/meshtrek/exper/cluster/script/fix_schedule_hotel.sh

kubectl create ns social
helm install socialnetwork ~/meshtrek/resources/benchmark/SocialNetwork/helm-chart/socialnetwork/ --namespace social

sudo apt-get -y install luarocks
sudo luarocks install luasocket

cd ~/DeathStarBench/wrk2
sudo apt -y install libssl-dev
sudo apt -y install zlib1g-dev
git submodule update --init --recursive
make