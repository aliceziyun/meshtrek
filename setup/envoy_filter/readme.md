## Possible Filters

Reference: https://www.alibabacloud.com/help/zh/asm/

### Basic Functionality

- mTLS authentication
- HTTP/HTTPS, gRPC, WebSocket, TCP auto load balancing
- retry, fault injection
- observability

### Security Features

- KubeAPI operation auditing：Mesh Egress Telemetry on Internet access
- [Custom authorization](https://www.alibabacloud.com/help/en/asm/sidecar/implement-custom-authorization-by-using-the-grpc-protocol?spm=a2c63.l28256.0.i1)：Add a custom filter in envoy, which calls the external authorization API
- [OPA policy](https://www.alibabacloud.com/help/en/asm/sidecar/use-opa-to-implement-fine-grained-access-control-in-asm?spm=a2c63.l28256.0.i4): Similar to Custom authorization, add a filter calls OPA plugin. One interest point is that the OPA policy can be dynamically updated
- [JWT Authentication](https://www.alibabacloud.com/help/en/asm/sidecar/authenticate-and-authenticate-jwt-in-http-requests?spm=a2c63.l28256.0.i1): 

### Observability

- [OpenTelemetry Tracing](https://www.alibabacloud.com/help/en/asm/sidecar/integrated-tracking-of-applications-inside-and-outside-the-grid-using-observable-link-opentelemetry-version?spm=a2c63.l28256.0.i7):  Use XTrace or Zipkin to enable tracing (only for HTTP)
- Service mesh is not useful for gRPC tracing, still need to modify the application

### Traffic Management

- [Migrate TCP Traffic](https://www.alibabacloud.com/help/en/asm/sidecar/use-asm-to-transfer-tcp-traffic?spm=a2c63.l28256.0.0.5f966185koUV9t): Route TCP traffic by rules or proportion (*can this feature be achieved only by L4 policy?*)
- [Access External Services](https://www.alibabacloud.com/help/en/asm/sidecar/access-external-services-from-an-asm-instance?spm=a2c63.l28256.0.0.5f966185koUV9t): Access services pass-through outside the service cluster

### Other

- [DNS parsing](https://www.alibabacloud.com/help/zh/asm/sidecar/use-the-dns-proxy-feature-in-an-asm-instance?spm=a2c63.l28256.0.0.5f966185koUV9t): Use sidecar to cache the list of known services. And use sidecar to do DNS parsing.
- [Wasm Filter](https://www.alibabacloud.com/help/zh/asm/sidecar/use-coraza-wasm-plug-in-to-implement-waf-capability-on-asm-gateway?spm=a2c63.p38356.0.i12): An sandbox extension which allows user implement functionality without modifying the source code of Envoy (Feels like this method is different from other filters of Envoy)

### Example

- end-to-end canary release: add service tag to header or payload, the traffic is processed at the **gateway**, then route to different services (this seems not useful in gRPC)
- response header: add field to response header to ensure security
- metrics observation: service mesh generate Istio metrics and provide the information to metric monitor tool like Prometheus, then auto scale the service