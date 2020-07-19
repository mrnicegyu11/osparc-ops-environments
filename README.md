# oSparc Simcore Operations Development - Deployed on AWS

[Upstream GitHubosparc-ops](https://github.com/ITISFoundation/osparc-ops)

[![Build Status](https://travis-ci.com/ITISFoundation/osparc-ops.svg?branch=master)](https://travis-ci.com/ITISFoundation/osparc-ops)

Tools for oSPARC deployment and management (not directly part of osparc platform)

## Sim-Core deployed

| Service   | Description | Endpoint   |
|:-------------:|:-------------:|:-------------:|
| latest | [latest release](https://github.com/ITISFoundation/osparc-simcore/releases) | **[https://osparc.io](https://osparc.io)**

## Support services

| Service   | Description | Endpoint   | User   | Password   | -- |
|:-------------:|:-------------:|:-------------:|:-----:|:---:|:---:|
| [Adminer](services/adminer) | Database management | **[https://monitoring.osparc.io/adminer](https://monitoring.osparc.io/adminer/?pgsql=osparc-production.c1fhr9qft53p.us-east-1.rds.amazonaws.com:5432&username=postgres_osparc&db=simcoredb&ns=public)** | postgres_osparc | 14Bk3VyP3ZIQNrtlbCBdMZDvTNpJ7k | Host :  osparc-production.c1fhr9qft53p.us-east-1.rds.amazonaws.com:5432<br> DB : simcoredb
| [Grafana](services/monitoring) | Metrics display | **[https://monitoring.osparc.io/grafana/](https://monitoring.osparc.io/grafana/)** | admin | wkdjkwd9898wdkjkwjdD |
| [Graylog](services/graylog) | Logs aggregator | **[https://monitoring.osparc.io/graylog/](https://monitoring.osparc.io/graylog/)** | admin | wkdjkwd9898wdkjkwjdD |
| [Jaeger](services/jaeger) | Request tracer | **[https://monitoring.osparc.io/jaeger/search](https://monitoring.osparc.io/jaeger/search)** | admin | wkdjkwd9898wdkjkwjdD |
| [S3](https://aws.amazon.com/s3/) | S3 storage | **[https://aws.amazon.com/s3/](https://aws.amazon.com/s3/)** | https://itis.signin.aws.amazon.com/console - itis - s3-viewer - caa0v2c98PDSMgHJJOp*Klup8@7WPv | bucket : production-simcore
| [Portainer](services/portainer/) | Docker management tool | **[https://monitoring.osparc.io/portainer/#/home](https://monitoring.osparc.io/portainer/#/home)** | admin | wkdjkwd9898wdkjkwjdD |
| [Registry](services/registry) | Docker images registry | **[https://registry.osparc.io/v2/_catalog](https://registry.osparc.io/v2/_catalog)** | admin | wkdjkwd9898wdkjkwjdD |
| [Prometheus](services/monitoring) | Metrics Monitoring | **[https://monitoring.osparc.io/prometheus](https://monitoring.osparc.io/prometheus)** | admin | wkdjkwd9898wdkjkwjdD |
| [RabbitMQ UI](https://www.rabbitmq.com/documentation.html) | RabbitMQ management UI | **[https://monitoring.osparc.io/production_rabbit/](https://monitoring.osparc.io/production_rabbit/)** | admin | wkdjkwd9898wdkjkwjdD |
| [Redis-commander](services/redis-commander) | Redis database management | **[https://monitoring.osparc.io/redis](https://monitoring.osparc.io/redis)** | admin | wkdjkwd9898wdkjkwjdD |
| [Traefik](services/traefik/) | Reverse-proxy | **[https://monitoring.osparc.io/dashboard/](https://monitoring.osparc.io/dashboard/)** | admin | wkdjkwd9898wdkjkwjdD |
| [Deployment agent](services/deployment-agent/) | Auto-deployer
