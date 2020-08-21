# oSparc Simcore Operations Development - Deployed on Dalco

[Upstream GitHubosparc-ops](https://github.com/ITISFoundation/osparc-ops)

[![Build Status](https://travis-ci.com/ITISFoundation/osparc-ops.svg?branch=master)](https://travis-ci.com/ITISFoundation/osparc-ops)

Tools for oSPARC deployment and management (not directly part of osparc platform)

## Sim-Core deployed

| Service   | Description | Endpoint   |
|:-------------:|:-------------:|:-------------:|
| latest | [latest release](https://github.com/ITISFoundation/osparc-simcore/releases) | **[https://osparc.speag.com](https://osparc.speag.com)**

## Support services

| Service   | Description | Endpoint   | User   | Password   | -- |
|:-------------:|:-------------:|:-------------:|:-----:|:---:|:---:|
| [Adminer](services/adminer) | Database management | **[https://monitoring.osparc.speag.com/adminer](https://monitoring.osparc.speag.com/adminer/?pgsql=production_postgres:5432&username=postgres&db=simcoredb&ns=public)** | postgres | ghj56fgf | Host :  production_postgres:5432<br> DB : simcoredb
| [Grafana](services/monitoring) | Metrics display | **[https://monitoring.osparc.speag.com/grafana/](https://monitoring.osparc.speag.com/grafana/)** | admin | pandasles |
| [Graylog](services/graylog) | Logs aggregator | **[https://monitoring.osparc.speag.com/graylog/](https://monitoring.osparc.speag.com/graylog/)** | admin | pandasles |
| [Jaeger](services/jaeger) | Request tracer | **[https://monitoring.osparc.speag.com/jaeger/search](https://monitoring.osparc.speag.com/jaeger/search)** | admin | pandasles |
| [Minio](https://storage.osparc.speag.com/) | Minio | **[https://storage.osparc.speag.com/](https://storage.osparc.speag.com/)** | https://storage.osparc.speag.com/ | gfhfgh765gjtyjtj | fjghjgjdsdg345 | bucket : production-simcore
| [Portainer](services/portainer/) | Docker management tool | **[https://monitoring.osparc.speag.com/portainer/#/home](https://monitoring.osparc.speag.com/portainer/#/home)** | admin | pandasles |
| [Registry](services/registry) | Docker images registry | **[https://registry.osparc.speag.com/v2/_catalog](https://registry.osparc.speag.com/v2/_catalog)** | admin | pandasles |
| [Prometheus](services/monitoring) | Metrics Monitoring | **[https://monitoring.osparc.speag.com/prometheus](https://monitoring.osparc.speag.com/prometheus)** | admin | pandasles |
| [RabbitMQ UI](https://www.rabbitmq.com/documentation.html) | RabbitMQ management UI | **[https://monitoring.osparc.speag.com/production_rabbit/](https://monitoring.osparc.speag.com/production_rabbit/)** | admin | pandasles |
| [Redis-commander](services/redis-commander) | Redis database management | **[https://monitoring.osparc.speag.com/redis](https://monitoring.osparc.speag.com/redis)** | admin | pandasles |
| [Traefik](services/traefik/) | Reverse-proxy | **[https://monitoring.osparc.speag.com/dashboard/](https://monitoring.osparc.speag.com/dashboard/)** | admin | pandasles |
| [Deployment agent](services/deployment-agent/) | Auto-deployer
| [Mail](services/mail/) | Mail service
