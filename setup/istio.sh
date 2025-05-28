# this script is to setup Istio environment

# download istio, note this must be done with kubenetes cluster exists
curl -L https://istio.io/downloadIstio | sh -
cd istio-1.26.0
export PATH=$PWD/bin:$PATH
# install service mesh for bookinfo application
istioctl install -f samples/bookinfo/demo-profile-no-gateways.yaml -y
kubectl label namespace bookinfo istio-injection=enabled

# download k8s gateway api
kubectl get crd gateways.gateway.networking.k8s.io &> /dev/null || \
{ kubectl kustomize "github.com/kubernetes-sigs/gateway-api/config/crd?ref=v1.2.1" | kubectl apply -f -; }

# download jaeger
# kubectl apply -f https://raw.githubusercontent.com/istio/istio/release-1.26/samples/addons/jaeger.yaml
# cat <<EOF > ./tracing.yaml
# apiVersion: install.istio.io/v1alpha1
# kind: IstioOperator
# spec:
#   meshConfig:
#     enableTracing: true
#     defaultConfig:
#       tracing: {} # disable legacy MeshConfig tracing options
#     extensionProviders:
#     - name: jaeger
#       opentelemetry:
#         port: 4317
#         service: jaeger-collector.istio-system.svc.cluster.local
# EOF
# istioctl install -f ./tracing.yaml --skip-confirmation

# kubectl apply -f - <<EOF
# apiVersion: telemetry.istio.io/v1
# kind: Telemetry
# metadata:
#   name: mesh-default
#   namespace: istio-system
# spec:
#   tracing:
#   - providers:
#     - name: jaeger
# EOF

# patch services so we can access jaeger from outside
# kubectl patch svc tracing -n istio-system -p '{"spec":{"type":"NodePort"}}'

# download wrk2 for performance test
git clone https://github.com/giltene/wrk2.git
cd wrk2
make
cd ..