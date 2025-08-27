## Guidance of Hook

### Compilation

If you just want to build Envoy, use script under `ci` directory.

If you want to build Istio-proxy Envoy, change directory to `proxy`, and change the link in `WORKSPACE` pointing to local repository.

```bazel
# http_archive()

local_repository(
    name = "envoy",
    path = "/envoy",
)
```

Then, run `make build_envoy BUILD_WITH_CONTAINER=1` to build. After compilation succeed, run `docker inspect volume cache` and `ls -lh bazel-bin` to get the actual directory of building output, copy it to directory you want.



### Write `Uprobe` Script

The only thing you need to know is the symbol of the hook functions.  I like name the hook functions like `hookpoint[FunctionName]`. So it's easy for me to find the symbol. I'll just run `nm [path_to_envoy] | grep hookpoint` and can directly use the symbol in bcc script.

If you change the signature of a function, the symbol will change, otherwise it won't.



### Make Container

Make sure you have `custom_istio.dockerfile` and compiled Envoy under your current directory.

```shell
docker build -t [tag] -f custom_istio.dockerfile .
docker tag [tag]:latest [username]/[tag]:[version]
docker push
```

So the image will be pushed to remote docker hub, which can be used in later.



### Inject Customized Container

Now we can inject our customized container to Istio.

First, in the YAML file used to describe cluster, manually add `istio-proxy` as a sidecar, so the customized container will overwrite the original one, but other configuration will still be the same.

```yaml
- name: istio-proxy
        image: docker.io/[username]/[tag]:[version]
        securityContext:
          allowPrivilegeEscalation: true
          privileged: true
          capabilities:
            add: ["SYS_ADMIN"]
```

Keep the container as privileged so we can add `uprobe` on it.

Then we need to mount some directories to container. Make sure that you have Linux header files on the host machine by checking `/lib/modules` and `/usr/src`. 

So the full configuration generally will be:

```yaml
- name: istio-proxy
        image: docker.io/[username]/[tag]:[version]
        securityContext:
          allowPrivilegeEscalation: true
          privileged: true
          capabilities:
            add: ["SYS_ADMIN"]
        volumeMounts:
        - mountPath: /lib/modules
          name: lib-modules
        - mountPath: /usr/src
          name: linux-headers
        - name: tmp
          mountPath: /tmp
      volumes:
      - name: tmp
        emptyDir: {}
      - name: lib-modules
        hostPath:
          path: /lib/modules
          type: Directory
      - name: linux-headers
        hostPath:
          path: /usr/src
          type: Directory
```

Use this new YAML file to launch the cluster, then run script `trace_all.sh` to start `uprobe` on each container.

## Version Record
I should have done this earlier...

### Modified_Istio_Proxy
- 10.1: version fits `envoy_trace_full` ✅
- 11.5: Record absolute time of filters, which can be used on gRPC application ✅
- 11.6(deprecated): Use `x-request-id` instead of uber id to trace filter. But unfortunately gRPC will not forward the `x-request-id` automatically.
- 11.7(deprecated): Add hookpoint before router decoding headers. Because the filters chain might end after upstream is connected, which will be influenced by network
- 11.8: The working version of 11.7

- 12.0: add `linux-tools-6.8.0-71-generic` to support perf ✅

### Cilium Envoy Modified
- 2.0(deprecated): upgrade cilium to 1.8.0 and envoy to 1.34.4. However, this version will add much overhead to network.
- 2.1: use release version to attach uprobe. no symbol. **Only for test**
- 2.2: use no-modified version, optimize with symbol

### Istio_Perf
- 1.0: http parsing. Insert fifo write to open perf. From Dispath() -> onHeadersComplete() (not so useful in fine-grain control)
- 1.1: based on modified istio proxy **v10.1**
