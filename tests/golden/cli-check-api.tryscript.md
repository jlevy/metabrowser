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

The API check drives the same initial tree, Live-filter, cleared-filter, and filtered
requests as the navigation panel, without opening a browser.
The fixture has pinned old mtimes so the Live result and aggregate output are
deterministic.

The final step is the filtered tree projection.
`logs/` holds no Markdown, so a `.md` filter has to leave it out entirely rather than
list it as a folder that might contain something — `empty_dirs=0` is that check, and
`rows` dropping from 2 to 1 is it happening.

## Test: Live, clear, then filter

```console
$ metab checkroot --check-api
api check: checkroot
scenario: nav-live-clear-filter
initial tree: 200; response=tree
live filter: 200; files=0
cleared filter: 200; response=tree
index: done
final nav: 200; rows=2; files=2; size=12; index=done
filtered nav: 200; rows=1; files=1; size=7; empty_dirs=0
result: pass
? 0
```
