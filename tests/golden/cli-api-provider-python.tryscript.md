---
sandbox: true
path:
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "WARNING"
  METABROWSER_INVENTORY_PROVIDER: "python"
before: >-
  mkdir -p root &&
  printf 'one\n' > root/one.txt &&
  touch -t 202311142213.20 root/one.txt root
---
# Golden tests: the Python provider names itself

Every other transcript matches the inventory provider’s name as `[PROVIDER]`, so the
goldens run against whichever provider `METABROWSER_INVENTORY_PROVIDER` selects.
This one selects the Python provider itself and pins the name the inventory routes
report for it; each shipped provider has a transcript like it.

## Test: index progress names the provider

```console
$ metab root --api /api/index/progress
api: /api/index/progress
status: 200
{
  "status": "done",
  "indexed_files": 1,
  "max_files": 500000,
  "truncated": false,
  "complete": true,
  "active": false,
  "provider": "python",
  "contract": "inventory-provider-v1"
}
? 0
```
