FROM golang:1.22-alpine AS build
WORKDIR /src
COPY main.go .
RUN go build -trimpath -ldflags="-s -w" -o /out/forwarder main.go

FROM alpine:3.19
RUN apk add --no-cache ca-certificates
COPY --from=build /out/forwarder /usr/local/bin/forwarder
EXPOSE 15001
ENTRYPOINT ["/usr/local/bin/forwarder"]

