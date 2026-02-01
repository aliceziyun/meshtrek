#!/bin/bash

NAMESPACE="hotel"
DEPLOYMENT_DIR="$HOME/meshtrek/exper/metric/script/ambient_inject/deployments"
SHADOW_DEPLOY_TEMPLATE_FILE="$HOME/meshtrek/resources/ambient/deploy-shadow.yaml"

# 删除并创建deployment dir
rm -rf "$DEPLOYMENT_DIR"
mkdir -p "$DEPLOYMENT_DIR"

# 获取现有所有的waypoint
waypoints=($(kubectl get deploy -n $NAMESPACE | grep waypoint | awk '{print $1}'))
for waypoint in "${waypoints[@]}"; do
    对每个waypoint执行patch，移除owner reference
    kubectl patch deploy "$waypoint" -n $NAMESPACE --type=json -p='[
        {"op":"remove","path":"/metadata/ownerReferences"}
    ]'

    # dump当前waypoint的yaml前4行 (metadata 部分)到文件
    kubectl get deploy "$waypoint" -n $NAMESPACE -o yaml | head -n 14 > "$DEPLOYMENT_DIR/${waypoint}.yaml"

    # 把shadow deployment的全部内容追加到文件
    cat "$SHADOW_DEPLOY_TEMPLATE_FILE" >> "$DEPLOYMENT_DIR/${waypoint}.yaml"

    # 替换占位符
    sed -i -e "s/gnosia/$waypoint/g" "$DEPLOYMENT_DIR/${waypoint}.yaml"

    # 应用新的shadow deployment
    kubectl apply -f "$DEPLOYMENT_DIR/${waypoint}.yaml" -n $NAMESPACE
    echo "Processed waypoint: $waypoint"
done

# wait for ready
sleep 10