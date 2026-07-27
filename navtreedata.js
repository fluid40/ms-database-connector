/*
 @licstart  The following is the entire license notice for the JavaScript code in this file.

 The MIT License (MIT)

 Copyright (C) 1997-2020 by Dimitri van Heesch

 Permission is hereby granted, free of charge, to any person obtaining a copy of this software
 and associated documentation files (the "Software"), to deal in the Software without restriction,
 including without limitation the rights to use, copy, modify, merge, publish, distribute,
 sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
 furnished to do so, subject to the following conditions:

 The above copyright notice and this permission notice shall be included in all copies or
 substantial portions of the Software.

 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
 BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
 NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
 DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

 @licend  The above is the entire license notice for the JavaScript code in this file
*/
var NAVTREE =
[
  [ "Database Connector Documentation", "index.html", [
    [ "ms-database-connector", "index.html", "index" ],
    [ "Configuration Guide", "md_docs_2configuration.html", [
      [ "Table of Contents", "md_docs_2configuration.html#autotoc_md2", null ],
      [ "Overview", "md_docs_2configuration.html#autotoc_md3", null ],
      [ "Required Folder Structure", "md_docs_2configuration.html#autotoc_md4", null ],
      [ "Environment Variables (using .env file)", "md_docs_2configuration.html#autotoc_md5", [
        [ "Recommended <tt>.env</tt> file", "md_docs_2configuration.html#autotoc_md6", null ],
        [ "How to load <tt>.env</tt>", "md_docs_2configuration.html#autotoc_md7", null ]
      ] ],
      [ "AAS Infrastructure Configuration", "md_docs_2configuration.html#autotoc_md8", null ],
      [ "AAS Registry Configuration", "md_docs_2configuration.html#autotoc_md9", null ],
      [ "Submodel Registry Configuration", "md_docs_2configuration.html#autotoc_md10", null ],
      [ "Repository Server Configuration", "md_docs_2configuration.html#autotoc_md11", [
        [ "How SecretVarName Works", "md_docs_2configuration.html#autotoc_md12", null ]
      ] ],
      [ "Main Service Configuration (including the InfluxDB config)", "md_docs_2configuration.html#autotoc_md13", [
        [ "Field reference", "md_docs_2configuration.html#autotoc_md14", null ],
        [ "InfluxDB notes", "md_docs_2configuration.html#autotoc_md15", null ]
      ] ],
      [ "DB Mapping Configuration", "md_docs_2configuration.html#autotoc_md16", null ],
      [ "Validation Checklist", "md_docs_2configuration.html#autotoc_md17", null ],
      [ "Typical Startup Errors", "md_docs_2configuration.html#autotoc_md18", [
        [ "1) <tt>No configuration file provided.</tt>", "md_docs_2configuration.html#autotoc_md19", null ],
        [ "2) ‘Configuration file ’.../service_config.json' not found or inaccessible.`", "md_docs_2configuration.html#autotoc_md20", null ],
        [ "3) ‘Configuration base path 'configuration’ not found.`", "md_docs_2configuration.html#autotoc_md21", null ],
        [ "4) <tt>No AAS registry configuration files found...</tt> or <tt>No Submodel registry configuration files found...</tt>", "md_docs_2configuration.html#autotoc_md22", null ],
        [ "5) <tt>Invalid AAS registry connection file.</tt> / <tt>Invalid Submodel registry connection file.</tt>", "md_docs_2configuration.html#autotoc_md23", null ],
        [ "6) <tt>InfluxDB connection failed. Set INFLUXDB_V2_TOKEN and ensure server reachability.</tt>", "md_docs_2configuration.html#autotoc_md24", null ],
        [ "7) <tt>No Asset Administration Shell ID provided in configuration file.</tt>", "md_docs_2configuration.html#autotoc_md25", null ],
        [ "8) ‘...descriptor with ID ’...' not found...`", "md_docs_2configuration.html#autotoc_md26", null ],
        [ "9) Mapping validation errors (for example invalid target type or multiple timestamps)", "md_docs_2configuration.html#autotoc_md27", null ]
      ] ]
    ] ],
    [ "Setup for Database Connector Demo Workflow", "md_docs_2demo.html", null ],
    [ "Mapping Process: From SubmodelElements to Influx Objects", "md_docs_2mapping.html", [
      [ "Overview", "md_docs_2mapping.html#autotoc_md30", null ],
      [ "Process Flow", "md_docs_2mapping.html#autotoc_md31", null ],
      [ "Class Architecture", "md_docs_2mapping.html#autotoc_md32", [
        [ "InfluxMapper Class", "md_docs_2mapping.html#autotoc_md33", null ]
      ] ],
      [ "Detailed Steps", "md_docs_2mapping.html#autotoc_md34", [
        [ "1. Validation Phase", "md_docs_2mapping.html#autotoc_md35", null ],
        [ "2. Reference Mapping Phase", "md_docs_2mapping.html#autotoc_md36", null ],
        [ "3. Measurement Processing Phase", "md_docs_2mapping.html#autotoc_md37", null ],
        [ "4. Value Retrieval Phase", "md_docs_2mapping.html#autotoc_md38", null ],
        [ "5. Value Assignment Phase", "md_docs_2mapping.html#autotoc_md39", null ]
      ] ],
      [ "Configuration Structure", "md_docs_2mapping.html#autotoc_md40", [
        [ "DB Mapping Format", "md_docs_2mapping.html#autotoc_md41", null ],
        [ "Example Configuration", "md_docs_2mapping.html#autotoc_md42", null ]
      ] ],
      [ "Data Flow Example", "md_docs_2mapping.html#autotoc_md43", [
        [ "Input", "md_docs_2mapping.html#autotoc_md44", null ],
        [ "Processing Steps", "md_docs_2mapping.html#autotoc_md45", null ],
        [ "Output", "md_docs_2mapping.html#autotoc_md46", null ]
      ] ],
      [ "Error Handling", "md_docs_2mapping.html#autotoc_md47", [
        [ "Access Validation Failures", "md_docs_2mapping.html#autotoc_md48", null ],
        [ "Retrieval Failures", "md_docs_2mapping.html#autotoc_md49", null ],
        [ "Assignment Failures", "md_docs_2mapping.html#autotoc_md50", null ]
      ] ],
      [ "Integration Points", "md_docs_2mapping.html#autotoc_md51", [
        [ "Upstream Dependencies", "md_docs_2mapping.html#autotoc_md52", null ],
        [ "Downstream Usage", "md_docs_2mapping.html#autotoc_md53", null ]
      ] ],
      [ "Performance Considerations", "md_docs_2mapping.html#autotoc_md54", null ],
      [ "Constraints & Limitations", "md_docs_2mapping.html#autotoc_md55", null ],
      [ "Future Enhancements", "md_docs_2mapping.html#autotoc_md56", null ]
    ] ],
    [ "Interaction of ms-db-connector with other components", "md_docs_2process.html", [
      [ "Option 1: Use a ready-to-go configuration file", "md_docs_2process.html#autotoc_md58", [
        [ "Local Dev Process", "md_docs_2process.html#autotoc_md59", null ]
      ] ],
      [ "Option 1: Configure DBC for direct integration with ms-data-mapping-processor", "md_docs_2process.html#autotoc_md61", null ],
      [ "Option 2: Configure DBC for usage of Registry", "md_docs_2process.html#autotoc_md62", null ]
    ] ],
    [ "Tips and Tricks for Data Visualization in InfluxDB", "md_docs_2visualization.html", null ],
    [ "Namespaces", "namespaces.html", [
      [ "Namespace List", "namespaces.html", "namespaces_dup" ],
      [ "Namespace Members", "namespacemembers.html", [
        [ "All", "namespacemembers.html", null ],
        [ "Functions", "namespacemembers_func.html", null ],
        [ "Variables", "namespacemembers_vars.html", null ]
      ] ]
    ] ],
    [ "Classes", "annotated.html", [
      [ "Class List", "annotated.html", "annotated_dup" ],
      [ "Class Index", "classes.html", null ],
      [ "Class Hierarchy", "hierarchy.html", "hierarchy" ],
      [ "Class Members", "functions.html", [
        [ "All", "functions.html", "functions_dup" ],
        [ "Functions", "functions_func.html", null ],
        [ "Variables", "functions_vars.html", null ],
        [ "Properties", "functions_prop.html", null ]
      ] ]
    ] ],
    [ "Files", "files.html", [
      [ "File List", "files.html", "files_dup" ]
    ] ]
  ] ]
];

var NAVTREEINDEX =
[
"____init_____8py.html",
"classtest__db__mapping__validation_1_1TestHttpErrorsForInvalidMapping.html#a56258324fc99189c164735196d9096f6",
"classtest__polling__worker_1_1TestWriteInfluxPoints.html#a2f910c28aee2c3cb7732d02d31decac3",
"md_docs_2mapping.html#autotoc_md51"
];

var SYNCONMSG = 'click to disable panel synchronisation';
var SYNCOFFMSG = 'click to enable panel synchronisation';