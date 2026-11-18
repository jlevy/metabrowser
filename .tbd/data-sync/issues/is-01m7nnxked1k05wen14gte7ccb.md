---
type: is
id: is-01m7nnxked1k05wen14gte7ccb
title: "open_in preference: config.yml, METABROWSER_OPEN_IN, --open-in, reported by --doctor"
kind: feature
status: in_progress
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-17-open-anything-from-cli-and-app.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m7nnxvge8wvp33zmj3nkpnvg
parent_id: is-01m7nnxhaqce1g2ewec3wbaf7e
hold: null
hold_until: null
created_at: 2026-11-17T21:17:01.261Z
updated_at: 2026-11-18T23:03:26.248Z
started_at: 2026-11-18T21:02:16.459Z
---
Phase 1. auto (default: app on macOS when detected), app (refuse when missing), browser. Known field in ApplicationConfig. --doctor --json reports value and source.

## Notes

2026-11-18: built in jlevy/metabrowser#582 (open, not merged). src/metabrowser/open_in.py reads --open-in, then METABROWSER_OPEN_IN, then open_in in config.yml, then the default auto, and records the source (flag, environment, config, default). ApplicationConfig.open_in in cache/records.py, with softschema and conformance cases. --doctor prints an open_in line on a clean run; --doctor --json adds open_in {value, source, app}, where app is what detection found (null under browser). An unreadable preference, or app where no app takes a target, is a doctor problem. --present reads only the setting from config.yml (bounded by CONFIG_MAX_BYTES, through the owner-only helper) to keep the dry run near --version; tests/test_open_in.py holds that reader to read_config's answer. Not built: a command that writes open_in, so config.yml is edited by hand. Bare metab PATH does not read the preference (plan Q4, mb-6n8j). Close when #582 merges.


2026-11-18, review A on #582: present_browser: false in config.yml (read from the file alone, no flag or variable overrides it) turns browser delivery off, code browser_off, status 4; --doctor reports it. Default unset = allowed, an owner question in the PR. Head bafef973e.
