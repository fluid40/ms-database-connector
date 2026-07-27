# ms-database-connector
Microservice 'database connector' to write dynamic data into a time series database

## Devcontainer Endpoint Overview

This project uses the services defined in `.devcontainer/docker-compose.yaml`.
The following endpoints are exposed to your host machine during local development.

### Direct host endpoints (port mappings)

| Service | URL | Purpose |
|---|---|---|
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
