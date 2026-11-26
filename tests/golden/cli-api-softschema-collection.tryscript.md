---
sandbox: true
path:
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "ERROR"
before: >-
  mkdir -p library/_schemas library/people library/empty &&
  printf '%s\n' '{"type":"object","properties":{"name":{"type":"string"}},"required":["name"],"x-softschema":{"contract":"example:Person/v1"}}'
  > library/_schemas/person.schema.json &&
  printf '%s\n' '{"softschema":{"contract":"example:Person/v1","envelope":"person","schema":"../_schemas/person.schema.json"},"person":{"name":"Ada Lovelace"}}'
  > library/people/ada.json
---
# Golden tests for SoftSchema folder tables

The served folder retains Overview.
The contract table and linked record are read by the shared table routes.

## Test: index a collection and keep the opened folder as the table scope

```console
$ metab library --show people --format json | jq -c '{kind,views:[.views[]|{id,default}]}'
{"kind":"folder","views":[{"id":"overview","default":true},{"id":"treemap","default":false},{"id":"table","default":false}]}
? 0
```

```console
$ metab library --api '/api/plugin/softschema/collection?path=people&wait=1' --format json > summary.json && jq -c '{root,state,complete,tables}' summary.json
{"root":"","state":"ready","complete":true,"tables":[{"id":"example:Person/v1","label":"Person/v1","count":1}]}
? 0
```

```console
$ metab library --api '/api/plugin/table/rows?path=people&table=example%3APerson%2Fv1&wait=1' --format json > rows.json && jq -c '{count,name:.rows[0].cells.name}' rows.json
{"count":1,"name":"Ada Lovelace"}
? 0
```

```console
$ key=$(jq -r '.rows[0].key' rows.json) && metab library --api "/api/plugin/table/record?path=people&table=example%3APerson%2Fv1&wait=1&key=$key" --format json > detail.json && jq -c '{label,source_path}' detail.json
{"label":"Ada Lovelace","source_path":"people/ada.json"}
? 0
```
