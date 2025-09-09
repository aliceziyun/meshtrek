# install helm
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
chmod 700 get_helm.sh
./get_helm.sh

# sudo apt-get install -y lvm2
sudo modprobe dm-snapshot
sudo modprobe nvme_tcp
sudo modprobe iscsi_tcp
echo "dm-snapshot" | sudo tee -a /etc/modules-load.d/dm-snapshot.conf

# --------------- these are not useful anymore-----------------
# use /dev/sda4 as containerd storage

# sudo mkdir -p /mnt/data
# sudo mkdir -p /mnt/openebs
# sudo mount -t ext4 /dev/sda4 /mnt/data
# sudo mkdir -p /mnt/data/containerd
# sudo mkdir -p /mnt/data/openebs
# sudo mount --bind /mnt/data/openebs /mnt/openebs

# sudo systemctl stop containerd
# sudo cp -a /var/lib/containerd/ /var/lib/containerd.backup
# sudo rsync -avx /var/lib/containerd/ /mnt/data/containerd/
# sudo sed -i 's|root = "/var/lib/containerd/"|root = "/mnt/data/containerd"|g' /etc/containerd/config.toml
# sudo chattr +i /etc/containerd/config.toml
# sudo systemctl daemon-reload
# sudo systemctl start containerd

# sudo mkfs.ext4 /dev/sda3
# ---------------------------------------------------------------

sudo mkdir -p /mnt/openebs
sudo mount /dev/sda3 /mnt/openebs

# install openebs (main node)
helm repo add openebs https://openebs.github.io/openebs
helm repo update
helm install openebs openebs/openebs \
  --namespace openebs \
  --create-namespace \
  --set localprovisioner.basePath="/mnt/openebs" \
  --set ndm.enabled=false \
  --set ndmOperator.enabled=false

# deploy train ticket
git clone --depth=1 https://github.com/FudanSELab/train-ticket.git ~/train-ticket
cd ~/train-ticket/

# create default StorageClass
kubectl patch storageclass openebs-hostpath -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'