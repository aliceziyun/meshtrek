## Train-Ticket Deployment

First, run launch_train_ticket_worker.sh on the worker node, then run launch_train_ticket.sh on the master node.
Make sure all pods in the openebs namespace are in Running state.

kubectl create ns train

Then run:
make deploy Namespace=train

Step 1: create the MySQL pod for nacosdb.
After the three pods are running, run:
```
for pod in $(kubectl get pods -n train --no-headers -o custom-columns=":metadata.name" | grep mysql); do
  kubectl exec -n train $pod -- mysql -uroot -e "CREATE USER IF NOT EXISTS 'root'@'::1' IDENTIFIED WITH mysql_native_password BY '' ; GRANT ALL ON *.* TO 'root'@'::1' WITH GRANT OPTION ;"
  kubectl exec -n train $pod -c xenon -- /sbin/reboot
done
```
Otherwise nacos-0 will keep crashing.
After this, other pods will also start one by one.

Wait for a while. When tsdb-mysql is running, run the same command again:
```
for pod in $(kubectl get pods -n train --no-headers -o custom-columns=":metadata.name" | grep tsdb-mysql); do
  kubectl exec -n train $pod -- mysql -uroot -e "CREATE USER IF NOT EXISTS 'root'@'::1' IDENTIFIED WITH mysql_native_password BY '' ; GRANT ALL ON *.* TO 'root'@'::1' WITH GRANT OPTION ;"
  kubectl exec -n train $pod -c xenon -- /sbin/reboot
done
```
Then wait until all pods are up (this will take a very long time).

## Train-Ticket Test
Test the API to make sure it works.
Visit [node_ip]:32677, and the train-ticket frontend UI will show up.

Make a ticket booking:
First login, then search any date until tickets appear.
Book a ticket until a popup shows (this step is a bit slow...).
Then go to pay.

At the beginning, these actions have some delay. If you leave the service running for a while, it seems to get better.