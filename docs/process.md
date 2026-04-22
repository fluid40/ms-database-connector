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
