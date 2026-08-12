---
sandbox: true
path:
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "WARNING"
before: >-
  mkdir -p checkroot/logs &&
  printf 'readme\n' > checkroot/README.md &&
  printf 'line\n' > checkroot/logs/run.log &&
  touch -t 202311142213.20 checkroot/README.md checkroot/logs/run.log
  checkroot/logs checkroot
---
# Golden test: navigation API check

The API check drives the same initial tree, Live-filter, and cleared-filter requests as
the navigation panel without opening a browser.
The fixture has pinned old mtimes so the Live result and aggregate output are
deterministic.

## Test: Live then clear

```console
$ metab checkroot --check-api
api check: checkroot
scenario: nav-live-clear
initial tree: 200; response=tree
live filter: 200; files=0
cleared filter: 200; response=tree
final nav: 200; rows=2; files=2; size=12; index=done
result: pass
? 0
```
