# Tips and Tricks for Data Visualization in InfluxDB

The initial field and tag names can be very long due to the Submodel Element paths used here.
To make this more readable, an Influx Query can be used, where the fields are mapped to shorter and readable names.

**Example for Influx V2:**

```flux
from(bucket: "fluid40-bucket")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "MappingConfigurations[0]")
  |> filter(fn: (r) =>
      r["_field"] == "https://fluid40.de/ids/sm/9413_4589_8838_2510/submodel-elements/EnergyConnection_Electric.EnergyMeasure_EnergyTotal.value" or
      r["_field"] == "https://fluid40.de/ids/sm/9413_4589_8838_2510/submodel-elements/EnergyConnection_Pneumatic.EnergyMeasure_Pressure.value" or
      r["_field"] == "https://fluid40.de/ids/sm/9413_4589_8838_2510/submodel-elements/EnergyConnection_Pneumatic.EnergyMeasure_VolumeTotal.value"
  )
  |> aggregateWindow(every: v.windowPeriod, fn: last, createEmpty: false)
  |> map(fn: (r) => ({
      r with
      // Field Mapping
      _field:
        if r["_field"] == "https://fluid40.de/ids/sm/9413_4589_8838_2510/submodel-elements/EnergyConnection_Electric.EnergyMeasure_EnergyTotal.value"
          then "Electric_Energy_Total"
        else if r["_field"] == "https://fluid40.de/ids/sm/9413_4589_8838_2510/submodel-elements/EnergyConnection_Pneumatic.EnergyMeasure_Pressure.value"
          then "Pneumatic_Pressure"
        else if r["_field"] == "https://fluid40.de/ids/sm/9413_4589_8838_2510/submodel-elements/EnergyConnection_Pneumatic.EnergyMeasure_VolumeTotal.value"
          then "Pneumatic_Volume_Total"
        else r["_field"],
      // Tag Mapping
      counter:
        if exists r["https://fluid40.de/ids/sm/4383_5760_6913_4373/submodel-elements/machineStateData.counter"]
          then r["https://fluid40.de/ids/sm/4383_5760_6913_4373/submodel-elements/machineStateData.counter"]
          else "",
      pattern:
        if exists r["https://fluid40.de/ids/sm/4383_5760_6913_4373/submodel-elements/machineStateData.pattern"]
          then r["https://fluid40.de/ids/sm/4383_5760_6913_4373/submodel-elements/machineStateData.pattern"]
          else "",
      machineState:
        if exists r["https://fluid40.de/ids/sm/4383_5760_6913_4373/submodel-elements/machineStateData.machineState"]
          then r["https://fluid40.de/ids/sm/4383_5760_6913_4373/submodel-elements/machineStateData.machineState"]
          else ""
  }))
  |> drop(columns: [
      "https://fluid40.de/ids/sm/4383_5760_6913_4373/submodel-elements/machineStateData.counter",
      "https://fluid40.de/ids/sm/4383_5760_6913_4373/submodel-elements/machineStateData.pattern",
      "https://fluid40.de/ids/sm/4383_5760_6913_4373/submodel-elements/machineStateData.machineState"
  ])
```
