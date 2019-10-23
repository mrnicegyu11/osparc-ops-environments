# oSparc Simcore Operations Development

[![Build Status](https://travis-ci.com/ITISFoundation/osparc-ops.svg?branch=master)](https://travis-ci.com/ITISFoundation/osparc-ops)

Tools for oSPARC deployment and management (not directly part of osparc platform)

## Contents

### services

Support services used for the deployment of the oSPARC platform:

- [Portainer](services/portainer/): Docker management tool
- [Traefik](services/traefik/): Reverse-proxy to handle secured entrypoints
- [Minio](services/minio/): AWS compatible S3 storage
- [Portus](services/portus/): Docker images registry
- [Graylog](services/graylog): Logs aggregator
- [Jaeger](services/jaeger): Tracing system
- [Monitoring](services/monitoring/): Prometheus/Grafana monitoring
- [Adminer](services/adminer): Database management
- [Maintenance](services/maintenance/): Notebooks for internal maintenance (in development)
- [Deployment agent](services/deployment-agent/): SIM-Core auto deploy tool

- [Simcore](services/simcore): Configuration for [osparc-simcore](https://github.com/ITISFoundation/osparc-simcore)

### usage

```console
git clone https://github.com/ITISFoundation/osparc-ops.git
cd osparc-ops
make help
```

#### local deployment
  ```console
  make up-local
  ```
A self-signed certificate may be generated. The system host file may be modified using the default **osparc.local** fully qualified domain name (FQDN) to point to the local machine.

The services above will be deployed and pre-configured on the following endpoints:
  - Traefik: [https://osparc01.speag.com:9001/dashboard/](https://osparc01.speag.com:9001/dashboard/)
  - Portainer: [https://osparc01.speag.com/portainer/](https://osparc01.speag.com/portainer/)
  - Minio: [https://osparc01.speag.com/minio](https://osparc01.speag.com/minio) and [https://osparc01.speag.com:10000](https://osparc01.speag.com:10000)
  - Portus: [https://osparc01.speag.com:5000](https://osparc01.speag.com:5000)
  - Deployment agent: no UI
  - Graylog: [https://osparc01.speag.com/graylog/](https://osparc01.speag.com/graylog/)
  - Adminer: [https://osparc01.speag.com/adminer](https://osparc01.speag.com/adminer)
  - Monitoring: [https://osparc01.speag.com/grafana](https://osparc01.speag.com/grafana) and Prometheus: [http://osparc01.speag.com:9090](http://osparc01.speag.com:9090)
  - Maintenance: not reversed proxied yet
  - **Simcore:** **[https://osparc01.speag.com](https://osparc01.speag.com)**

Default credentials are the following:
  user: admin
  password: adminadmin


To change the default domain name and/or services credentials edit [repo.config](repo.config) file.

#### cluster deployment

Each service may be configured and deployed according to the needs. Please see each service README.md file to gather information.

### virtual_cluster (deprecated)

- Deploy a virtual cluster to your own host.  Suitable as an infrastructure plaform for oSPARC Simcore.
