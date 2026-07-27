# Configuration Guide

## Table of Contents

- [Overview](#overview)
- [Required Folder Structure](#required-folder-structure)
- [Environment Variables (using .env file)](#environment-variables-using-env-file)
- [AAS Infrastructure Configuration](#aas-infrastructure-configuration)
- [Main Service Configuration (including the InfluxDB config)](#main-service-configuration-including-the-influxdb-config)
- [DB Mapping Configuration](#db-mapping-configuration)
- [Validation Checklist](#validation-checklist)
- [Typical Startup Errors](#typical-startup-errors)

## Overview

The `ms-database-connector` reads its runtime configuration from JSON files in the `configuration/` folder and from environment variables (typically loaded from a `.env` file).

At startup, the service validates and initializes:

1. Main service configuration (`service_config.json`)
2. DB mapping configuration (`db_mapping.json`)
3. AAS infrastructure connection files (`aas_registry/`, `submodel_registry/`, `repo_server/`)
4. InfluxDB connection (using `INFLUXDB_V2_TOKEN` for the current Influx v2 implementation)

If any required part is missing or invalid, startup fails with a clear error.

## Required Folder Structure

The application expects the following folder structure relative to the repository root:

```text
configuration/
    service_config.json
    db_mapping.json
    aas_registry/
        aas_registry_server_config.json
    submodel_registry/
        sm_registry_server_config.json
    repo_server/
        aas_repo_server_config.json
```

Required at startup:

- The service currently reads from a fixed base path: `configuration/`
- at least one file in aas_registry/
- at least one file in submodel_registry/

Optional but recommended:

- one or more files in repo_server/

## Environment Variables (using .env file)

The service uses environment variables for runtime behavior and secrets.

### Recommended `.env` file

Create a `.env` file in your workspace:

```env
# Required: path to main service config
DBC_CONFIGURATION_FILE=configuration/service_config.json

# Required for InfluxDB writes
INFLUXDB_V2_TOKEN=<your-influxdb-token>

# Required if your AAS infrastructure needs a secret for server authentication
<your-secret-env-var-name>=<your-oauth-client-secret>

# Optional runtime host/port for uvicorn
APP_HOST=127.0.0.1
APP_PORT=3090

# Optional: set to 0 to prevent launching uvicorn in __main__
RUN_SERVER=1
```

### How to load `.env`

This project does not automatically call `load_dotenv()`, so ensure variables are exported before starting the service.

Example (shell):

```bash
set -a
source .env
set +a
python -m ms_database_connector
```

Example (Docker):

```bash
docker run --rm -p 3090:3090 \
  --env-file .env \
  -v "$(pwd)/configuration:/app/configuration" \
  ms-database-connector:latest
```

## AAS Infrastructure Configuration

## AAS Registry Configuration

Folder:

- configuration/aas_registry/

Example:

```json
{
    "ServerConfiguration": {
        "BaseUrl": "https://my-aas-registry/",
        "TimeOut": 60,
        "ConnectionTimeOut": 60,
        "TrustEnv": false,
        "EncodedIds": false
    },
    "SecretVarName": ""
}
```

Notes:

- If multiple files exist, the first discovered JSON file is used.
- SecretVarName is optional and can be empty when no auth secret is needed.

## Submodel Registry Configuration

Folder:

- configuration/submodel_registry/

Example:

```json
{
    "ServerConfiguration": {
        "BaseUrl": "https://my-sm-registry/",
        "TimeOut": 60,
        "ConnectionTimeOut": 60,
        "TrustEnv": false,
        "EncodedIds": false
    },
    "SecretVarName": ""
}
```

Notes:

- If multiple files exist, the first discovered JSON file is used.

## Repository Server Configuration

Folder:

- configuration/repo_server/

You can define multiple repository targets, for example different environments or providers.

Example with OAuth:

```json
{
    "ServerConfiguration": {
        "BaseUrl": "https://my-aas-repo/",
        "TimeOut": 60,
        "ConnectionTimeOut": 60,
        "TrustEnv": false,
        "EncodedIds": false,
        "AuthenticationSettings": {
            "OAuth": {
                "ClientId": "workstation-1",
                "TokenUrl": "https://.../token",
                "GrantType": "client_credentials"
            }
        }
    },
    "SecretVarName": "DBC_AAS_CLIENT_SECRET"
}
```

Example with BasicAuth:

```json
{
    "ServerConfiguration": {
        "BaseUrl": "https://my-aas-repo/",
        "TimeOut": 60,
        "ConnectionTimeOut": 60,
        "TrustEnv": false,
        "EncodedIds": false,
        "AuthenticationSettings": {
            "BasicAuth": {
                "Username": "your-user"
            }
        }
    },
    "SecretVarName": "DBC_AAS_SECRET"
}
```

Important:

- If SecretVarName is set, the environment variable with that exact name must be available at runtime.
- The secret value is read from environment and used as password/client secret depending on auth mode.

### How SecretVarName Works

SecretVarName defines the name of an environment variable that contains a secret used for server authentication.

Short flow:

- The JSON file provides the variable name (for example DBC_AAS_CLIENT_SECRET).
- At runtime, the service reads the value from the environment.
- The value is forwarded to the configured auth method (for example OAuth client secret or BasicAuth password).
If SecretVarName is empty, no secret variable lookup is performed for that config file.

## Main Service Configuration (including the InfluxDB config)

Main configuration file: `configuration/service_config.json`

Example:

```json
{
  "AasId": "https://fluid40.de/ids/aas/9911_6092_2508_3450",
  "PollingInterval": 5,
  "ExternalUrl": "http://127.0.0.1",
  "ExternalPort": "3088",
  "PersistDbMappingFileChanges": true,
  "InfluxDbVersion": 2,
  "InfluxDbConfig": {
    "Url": "http://ms-dbc-influx-v2:8086/",
    "Organization": "fluid40-org",
    "Bucket": "fluid40-bucket",
    "TimeOut": 60,
    "ConnectionTimeOut": 60,
    "TrustEnv": false
  }
}
```

### Field reference

- `AasId` (required): Asset Administration Shell ID used at startup.
- `PollingInterval` (optional, default `5`): Polling interval in seconds.
- `ExternalUrl` (optional, default `http://127.0.0.1`): Public URL reference.
- `ExternalPort` (optional, default `3088`): Public port reference.
- `PersistDbMappingFileChanges` (optional, default `true`): Whether mapping updates are written back to `db_mapping.json`.
- `InfluxDbVersion` (optional, default `2`): Set to `2`.
- `InfluxDbConfig` (required for DB writes): InfluxDB connection details.

### InfluxDB notes

- Token is never read from `service_config.json`; it must come from `INFLUXDB_V2_TOKEN`.
- If `INFLUXDB_V2_TOKEN` is missing, the client is not initialized and startup fails.
- The v2 client appends `-org` automatically when `Organization` does not already end with `-org`.

## DB Mapping Configuration

Mapping file: `configuration/db_mapping.json`

Structure:

```json
{
  "<measurement_name>": {
    "<aas_sink_path>": "field | tag | timestamp"
  }
}
```

Valid target values:

- `field`
- `tag`
- `timestamp`

Rules:

- At most one `timestamp` entry is allowed per measurement.
- A measurement mapping must not be empty.
- `null` values are allowed only for initialization templates (for example via `PUT /initialize-db-mapping`).

Example:

```json
{
  "play_4_in_a_row": {
    "https://fluid40.de/ids/sm/1704_4135_2769_8983/submodel-elements/AxisPositions.Axis1Position": "field",
    "https://fluid40.de/ids/sm/1704_4135_2769_8983/submodel-elements/AxisPositions.Axis2Position": "field",
    "https://fluid40.de/ids/sm/1704_4135_2769_8983/submodel-elements/AxisPositions.Axis3Position": "field",
    "https://fluid40.de/ids/sm/1704_4135_2769_8983/submodel-elements/Emission.CurrentEmission": "field"
  }
}
```

## Validation Checklist

Use this checklist before startup:

1. Folder structure exists exactly as expected (`configuration/`, `aas_registry/`, `submodel_registry/`, `repo_server/`).
2. `.env` is present and exported in the current shell.
3. `DBC_CONFIGURATION_FILE` points to an existing JSON file.
4. `INFLUXDB_V2_TOKEN` is set.
5. AAS config files contain valid JSON and include both `ServerConfiguration` and `SecretVarName`.
6. `AasId` exists and is reachable via AAS registry/repository.
7. `db_mapping.json` contains valid target values and no duplicate timestamps per measurement.
8. InfluxDB URL, organization, and bucket are correct and reachable.

Optional quick checks:

```bash
# Verify required env vars in current shell
env | grep -E '^(DBC_CONFIGURATION_FILE|INFLUXDB_V2_TOKEN|DBC_AAS_CLIENT_SECRET|APP_HOST|APP_PORT)='

# Validate JSON syntax
jq . configuration/service_config.json >/dev/null
jq . configuration/db_mapping.json >/dev/null
jq . configuration/aas_registry/aas_registry_server_config.json >/dev/null
jq . configuration/submodel_registry/sm_registry_server_config.json >/dev/null
jq . configuration/repo_server/aas_repo_server_config.json >/dev/null
```

## Typical Startup Errors

### 1) `No configuration file provided.`

Cause:

- `DBC_CONFIGURATION_FILE` is unset or empty.

Fix:

- Set `DBC_CONFIGURATION_FILE` in `.env` and export it.

### 2) `Configuration file '.../service_config.json' not found or inaccessible.`

Cause:

- Wrong path in `DBC_CONFIGURATION_FILE`.
- Missing volume mount in container setup.

Fix:

- Correct the path.
- Mount the `configuration/` directory into the container.

### 3) `Configuration base path 'configuration' not found.`

Cause:

- Missing `configuration/` directory in working directory.

Fix:

- Ensure startup is executed from the project root or provide the expected folder at runtime.

### 4) `No AAS registry configuration files found...` or `No Submodel registry configuration files found...`

Cause:

- Required registry config folder is empty.

Fix:

- Add at least one valid JSON config file to each required folder.

### 5) `Invalid AAS registry connection file.` / `Invalid Submodel registry connection file.`

Cause:

- Malformed JSON or missing required keys (`ServerConfiguration`, `SecretVarName`).

Fix:

- Validate JSON and key names.

### 6) `InfluxDB connection failed. Set INFLUXDB_V2_TOKEN and ensure server reachability.`

Cause:

- Missing `INFLUXDB_V2_TOKEN`.
- InfluxDB URL not reachable.
- Wrong organization/bucket.

Fix:

- Set token and verify InfluxDB endpoint connectivity.
- Verify Influx settings in `service_config.json`.

### 7) `No Asset Administration Shell ID provided in configuration file.`

Cause:

- Missing or empty `AasId`.

Fix:

- Set a valid AAS ID in `service_config.json`.

### 8) `...descriptor with ID '...' not found...`

Cause:

- AAS/Submodel ID does not exist in registry.
- Registry points to outdated/misconfigured endpoint.

Fix:

- Verify descriptor registration and endpoint URLs.
- Ensure OAuth client credentials are valid.

### 9) Mapping validation errors (for example invalid target type or multiple timestamps)

Cause:

- Mapping values not in `field|tag|timestamp`.
- More than one `timestamp` in one measurement.

Fix:

- Correct the mapping structure and target values.
