FROM golang:1.13-alpine

LABEL maintainer="MinIO Inc <dev@min.io>"

ENV GOPATH /go
ENV CGO_ENABLED 0
ENV GO111MODULE on

RUN  \
     apk add --no-cache git && \
     git clone https://github.com/minio/mc && cd mc && \
     go install -v -ldflags "$(go run buildscripts/gen-ldflags.go)"

FROM alpine:3.10

COPY --from=0 /go/bin/mc /usr/bin/mc

RUN  \
     apk add --no-cache ca-certificates && \
     echo 'hosts: storage.osparc.io:10.44.13.11' >> /etc/nsswitch.conf

ENTRYPOINT ["mc"]