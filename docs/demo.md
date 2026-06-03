To setup a demonstration, do the following:
1. Ensure the docker network referenced in the devcontainer docker compose exists (`docker network create ms-shared-network `)
2. If not done yet, generate the Influx API Token
   1. Open to the influx db UI (`http://localhost:8031/`) and navigate to the API Token View
   2. Generate a new Token: **Read + Write for the _fluid40-bucket_ and Read rights for all other resources**
   3. Save the generated API Token value (e.g. in keepass)
3. Prepare the `.env` file inside the devcontainer (The Client credentials for the OAuth2 Authentication can be retrieved from the KeyCloak UI. Use for Login the credentials stored as environment variables _KEYCLOAK_ADMIN_ _KEYCLOAK_ADMIN_PASSWORD_ in the _keycloak_ service in the devcontainer docker-compose.yml).

```env
LOCAL_WORKSPACE_FOLDER_BASE_NAME=ms-database-connector
BASYX_VERSION=2.0.0-SNAPSHOT
AAS_WEBUI_VERSION=v2-260505
KEYCLOAK_VERSION=24.0.4
INFLUXDB_V2_TOKEN='<your-influx-token-value>'
DBC_AAS_CLIENT_SECRET='<client secret for workstation-1 client id>'
```

4. The _ExternalUrl_ and _ExternalPort_ in `demo/configuration/service_config.json` must match the compose service name and exposed port
5. Prepare the .env file that will be needed by the ms-data-mapping-processor:

```env
APP_HOST=0.0.0.0
APP_PORT=3088
CONFIG_FILE_NAME=service_config.json
DBC_AAS_CLIENT_SECRET='<client secret for workstation-1 client id>'
```

6. The Submodel Descriptor of the dynamic Submodel must point to the initial endpoint `http://aasenv.basyx.localhost/submodels/RW5lcmd5TW9uaXRvcmluZw`. This can be checked by a GET Request to `http://smreg.basyx.localhost/submodel-descriptors/RW5lcmd5TW9uaXRvcmluZw==` with the corresponding OAuth credentials for workstation-1 clientId.
7. Navigate with shell into the _demo_ folder and start compose stack (`docker compose up -d`). The service should start, change the SM registry endpoint from above to the locally hosted Submodel instance (`http://demo-ms-data-mapping-processor/submodels/RW5lcmd5TW9uaXRvcmluZw`) and start pulling from the OPC-UA server endpoint.
8. Adapt the configuration `configuration/service_config.json`:

```json
{
    "AasId": "https://fluid40.de/ids/shell/5793_5449_7830_4223",
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

9. Adapt the mapping file `configuration/db_mapping.json` to fit the data used in the demo:

```json
{
    "MappingConfigurations[0]": {
        "EnergyMonitoring/submodel-elements/EnergyConnection1.EnergyMeasures.TotalElectricEnergy.value": "field"
    }
}
```

10. press f5 to start the database-connector microservice. The service will connect to the influx DB and poll the values from the submodel elements referenced as sinks in the AIMC submodel. This values are written to the InfluxDB Bucket. You can query it in the Influx UI and make the field values with a specific flux-query more readable:

```flux
from(bucket: "fluid40-bucket")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "MappingConfigurations[0]")
  |> filter(fn: (r) =>
    r["_field"] == "EnergyMonitoring/submodel-elements/EnergyConnection1.EnergyMeasures.TotalElectricEnergy.value"
  )
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> map(fn: (r) => ({
    r with
    _field:
      if r["_field"] == "EnergyMonitoring/submodel-elements/EnergyConnection1.EnergyMeasures.TotalElectricEnergy.value" then "TotalElectricEnergy"
      else r["_field"]
  }))
```
