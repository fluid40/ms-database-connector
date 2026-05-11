# Interaction of ms-db-connector with other components

## Option 1: Use a ready-to-go configuration file

```mermaid
sequenceDiagram
    actor User
    participant DBC
    participant DMP
    participant DB@{ "type" : "database" }

    User->>DBC: Upload Config File
    DMP->>DBC: Configure connection to Influx DB
    DBC->>DB: Setup connection and create database
    DMP->>DBC: Send payload for DB
    DBC->>DB: Write to DB
```

Example `dbc-configuration.json`:

```json
    {
        "MappingConfigurations[0]": {
                "EnergyConnection_Electric.EnergyMeasure_EnergyTotal.value": "field",
                "EnergyConnection_Electric.EnergyMeasure_EnergyTotal.timeStamp": "timestamp",
                "EnergyConnection_Pneumatic.EnergyMeasure_Pressure.timeStamp": "field",
                "EnergyConnection_Pneumatic.EnergyMeasure_VolumeTotal.timeStamp": "field",
                "EnergyConnection_Pneumatic.EnergyMeasure_VolumeTotal.value": "field",
                "EnergyConnection_Pneumatic.EnergyMeasure_Pressure.value": "field",
                "machineStateData.counter": "tag",
                "machineStateData.pattern": "tag",
                "machineStateData.machineState": "tag"
        }
    }
```

Requirements for the configuration:

- All sink paths from one MappingConfiguration SML are written in one Measurement.
- The entire sink path will be used as Field name.
- `MappingConfigurations[0]` is the default name of the Influx Measurement. This can be changed to another name if wanted.
- Only one of the mapping elements inside a MappingConfiguration can be used for `timestamp`.
- For now, one must decide between the usage as `field` **or** `tag`. Both at once is not possible.
- A default tag named `source` will be used with the value of the idShort of the AAS.

### Local Dev Process

```mermaid
sequenceDiagram
    participant DBC
    participant DB@{ "type" : "database" }
    participant Registry
    actor User

    DBC->>DB: Connect to InfluxDB with Credentials from Config (or AID)
    alt db-mapping file missing
        DBC->>Registry: Get AIMC SM for AAS-ID
        Registry-->>DBC:
        DBC->>DBC: Extract AIMC.Seconds & generate db-mapping template
        User->>DBC: Get db-mapping
        DBC-->>User: empty db-mapping
        User->>DBC: upload updated db-mapping
    end
    DBC->>DB: Initialize connection
    DB-->>DBC: Connection healthy
    loop Inverval N
        DBC->>Registry: Retrieve values of AIMC.Seconds via Registry
        Registry-->>DBC:
        DBC->>DBC: Generate DB payload with db-mapping
        DBC->>DB: Write payload as values
    end
```

**Prerequisites for process:**

Influx/ Server Configuration `<server name or type>_server_config.json`

```json
{
    "ServerConfiguration": {
        "BaseUrl": "http://localhost:8030/",
        "TimeOut": 60,
        "ConnectionTimeOut": 60,
        "TrustEnv": false,
        "EncodedIds": false,
        "AuthenticationSettings": {
            "BasicAuthentication": {
                "Username": ""
            },
            "ServiceProviderAuthentication": {
                "ClientId": "",
                "TokenUrl": "",
                "GrantType": "client_credentials"
            },
            "BearerAuthentication": {
                "Token": ""
            }
        }
    },
    "SecretVarName": "SECRET_VAR_NAME"
}
```

`SECRET_VAR_NAME` must be set in compose.yml.

Service Configuration `service_config.json`

```json
{
    "AasId": "https://fluid40.de/ids/shell/5793_5449_7830_4223",
    "PollingInterval": 5,
    "ExternalUrl": "http://127.0.0.1",
    "ExternalPort": "3088"
}
```

---
The following sections are deprecated

## Option 1: Configure DBC for direct integration with ms-data-mapping-processor

```mermaid
sequenceDiagram
    actor Config
    participant DBC
    participant DMP
    participant DB@{ "type" : "database" }

    Config->>DBC: DMP Endpoint
    Config->>DBC: (SM-ID AIMC)
    DBC->>DMP: Get all cached SMs (incl. AIMC)
    DMP-->>DBC:

    DBC->>DBC: Extract Data Structure from cached SMs

    DBC->>DB: Write Data to Influx Table

```

## Option 2: Configure DBC for usage of Registry

```mermaid
sequenceDiagram
    actor Config
    participant DBC
    participant DMP
    participant Registry
    participant DB@{ "type" : "database" }


    Config->>DBC: SM-ID AIMC
    DBC->>Registry: Get AIMC SM-Descriptor
    Registry-->>DBC:
    DBC->>Repository: Get AIMC SM Option A
    Repository-->>DBC:
    DBC->>DMP: Get AIMC SM Option B
    DMP-->>DBC:

    Config->>DBC: SM-ID Energy
    DBC->>Registry: Get Energy SM-Descriptor
    Registry-->>DBC:
    DBC->>Repository: Get Energy SM Option A
    Repository-->>DBC:
    DBC->>DMP: Get Energy SM Option B
    DMP-->>DBC:

    DBC->>DBC: Extract Data Structure from SMs Energy + AIMC

    DBC->>DB: Write Data to Influx Table

```
