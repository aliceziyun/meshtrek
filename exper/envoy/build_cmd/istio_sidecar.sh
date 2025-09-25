cd ~/service-mesh/proxy
make build_envoy BUILD_WITH_CONTAINER=1
sudo cp /var/lib/docker/volumes/cache/_data/bazel/_bazel_user/1e0bb3bee2d09d2e4ad3523530d3b40c/execroot/io_istio_proxy/bazel-out/k8-opt/bin/envoy ../istio_sidecar

cd ../
docker build -t alicesong2002/modified_istio_proxy:v14.3 -f istiotest.dockerfile .
docker push alicesong2002/modified_istio_proxy:v14.3