# Microservice: Database Connector

[![License: MIT](https://img.shields.io/badge/license-MIT-%23f8a602?label=License&labelColor=%23992b2e)](https://github.com/fluid40/ms-database-connector/blob/main/LICENSE)
[![CI](https://github.com/fluid40/ms-database-connector/actions/workflows/CI.yml/badge.svg?branch=main&cache-bust=1)](https://github.com/fluid40/ms-database-connector/actions)

Microservice 'database connector' to write dynamic data into a time series database

This service reads mapping and infrastructure configuration from the AAS ecosystem and continuously writes mapped dynamic asset data into a configured time-series database.

## Features

- Connects to AAS infrastructure services to resolve shells and submodels.
- Loads Asset Interface Mapping Configuration (AIMC) and referenced AID submodels.
- Maps incoming asset data to InfluxDB-compatible measurements and fields.
- Supports local development, container execution, and GitHub release bundle deployment.

## Prerequisites

- Python 3.11 or newer.
- Reachable AAS infrastructure services (AAS Registry, Submodel Registry, and at least one Repository server).
- Valid JSON configuration files under the `configuration/` folder, including:
  - `configuration/service_config.json`
  - `configuration/db_mapping.json`
  - `configuration/aas_registry/*.json`
  - `configuration/submodel_registry/*.json`
  - `configuration/repo_server/*.json`
- An AAS containing an AIMC submodel and referenced AID submodels.
- Optional for containerized deployment: Docker engine with network access to the required backend services.

## Process

1. The service reads `service_config.json` and the referenced infrastructure connector configuration files.
2. It discovers and resolves target AAS shells and submodels via registry and repository endpoints.
3. It loads AIMC and AID information, builds the mapping model, and initializes polling jobs.
4. It continuously polls asset data, transforms values according to the mapping, and writes time-series points to the database.

## Devcontainer Endpoint Overview

This project uses the services defined in `.devcontainer/docker-compose.yaml`.
The following endpoints are exposed to your host machine during local development.

### Direct host endpoints (port mappings)

| Service | URL | Purpose |
| --- | --- | --- |
| InfluxDB v2 | http://127.0.0.1:8031 | InfluxDB v2 API and UI |
| AAS Environment | http://127.0.0.1:8081 | AAS repository endpoints |
| AAS Discovery | http://127.0.0.1:8084 | AAS discovery/lookup service |
| AAS Registry | http://127.0.0.1:8076 | AAS descriptor registry |
| Submodel Registry | http://127.0.0.1:8077 | Submodel descriptor registry |
| AAS Web UI | http://127.0.0.1:8078 | BaSyx AAS web interface |
| Keycloak | http://127.0.0.1:9095 | Identity and access management |
| Nginx proxy | http://127.0.0.1 | Virtual-host routing entrypoint |

### Virtual-host endpoints through nginx proxy

If your environment resolves `*.basyx.localhost` to localhost, you can also use:

- http://aasgui.basyx.localhost
- http://aasenv.basyx.localhost
- http://aasreg.basyx.localhost
- http://smreg.basyx.localhost
- http://discovery.basyx.localhost
- http://keycloak.basyx.localhost

### Database Connector API (development run)

When you run this service (default: `APP_HOST=127.0.0.1`, `APP_PORT=3088`), these endpoints are available:

- http://127.0.0.1:3088/health
- http://127.0.0.1:3088/aas/shells
- http://127.0.0.1:3088/aas/registry

### GitHub Release Bundle

The GitHub Actions workflow builds a local Docker image and uploads a portable release bundle.

The bundle contains:

- `image.tar` for `docker load`
- the `configuration/` directory next to it
- a short usage note

Typical local usage after downloading and extracting the bundle:

```bash
docker load -i image.tar
docker run --rm -p 3090:3090 \
	-e DBC_CONFIGURATION_FILE=/app/configuration/service_config.json \
	ms-database-connector:0.0.1-<git-hash>
```

If you want to override the bundled configuration with a local directory, mount it into the container:

```bash
docker run --rm -p 3090:3090 \
	-v "$(pwd)/configuration:/app/configuration" \
	-e DBC_CONFIGURATION_FILE=/app/configuration/service_config.json \
	ms-database-connector:0.0.1-<git-hash>
```

## Resources

- Documentation:
  - [Configuration Guide](docs/configuration.md)
  - [Demo Setup Guide](docs/demo.md)
  - Detailed description of the [Mapping Process](docs/mapping.md)
  - Process description for planned [interaction processes with the Connector](docs/process.md)
- Changelog: [GitHub releases notes](https://github.com/fluid40/ms-database-connector/releases)
- GitHub Release: [Latest release](https://github.com/fluid40/ms-database-connector/releases/latest)
- MIT License: [LICENSE](LICENSE)
