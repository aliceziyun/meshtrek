# install helm
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
chmod 700 get_helm.sh
./get_helm.sh

# sudo apt-get install -y lvm2
sudo modprobe dm-snapshot
sudo modprobe nvme_tcp
sudo modprobe iscsi_tcp
echo "dm-snapshot" | sudo tee -a /etc/modules-load.d/dm-snapshot.conf

# use /dev/sda4 as data storage
sudo mkdir -p /mnt/data     # mount container data
sudo zfs create zfspv-pool/data
sudo zfs set mountpoint=/mnt/data zfspv-pool/data

sudo mkdir -p /var/openebs/local
sudo zfs create zfspv-pool/openebs
sudo zfs set mountpoint=/var/openebs/local zfspv-pool/openebs

sudo cp -rp /var/lib/containerd /mnt/data/

sudo apt install -y zfsutils-linux

# use `sudo fdisk -l` to see all available disk section
# sudo zpool create -f zfspv-pool /dev/sdb
sudo zpool create -f zfspv-pool /dev/sda4

truncate -s 1024G /tmp/disk.img
sudo losetup -f /tmp/disk.img --show

sudo pvcreate /dev/loop0
sudo vgcreate lvmvg /dev/loop0

# install openebs (main node)
helm repo add openebs https://openebs.github.io/openebs
helm update
helm install openebs --namespace openebs openebs/openebs --create-namespace

# after start deploying the mysql node of train ticket
# create default StorageClass
kubectl patch storageclass openebs-hostpath -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'

# after nacos-mysql pod launched
for pod in $(kubectl get pods --no-headers -o custom-columns=":metadata.name" | grep nacosdb-mysql); do
  kubectl exec $pod -- mysql -uroot -e "CREATE USER 'root'@'::1' IDENTIFIED WITH mysql_native_password BY '' ; GRANT ALL ON *.* TO 'root'@'::1' WITH GRANT OPTION ;"
  kubectl exec $pod -c xenon -- /sbin/reboot
done