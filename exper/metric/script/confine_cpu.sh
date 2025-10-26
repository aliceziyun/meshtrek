DEFAULT_CPU="500m"
TARGET_CPU=$1
NAMESPACE=$2

pods=$(kubectl -n $NAMESPACE get pods -o jsonpath="{.items[*].metadata.name}")
for pod in $pods; do
  kubectl patch pod $pod -n $NAMESPACE -p \
    '{"spec": {"template": {"spec": {"containers": [{"name": "'$pod'", "resources": {"limits": {"cpu": "'$TARGET_CPU'"}, "requests": {"cpu": "'$DEFAULT_CPU'"}}}]}}}}' 
done