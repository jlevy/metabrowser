---
type: is
id: is-01m7nnxked1k05wen14gte7ccb
title: "open_in preference: config.yml, METABROWSER_OPEN_IN, --open-in, reported by --doctor"
kind: feature
status: closed
priority: 2
version: 7
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
updated_at: 2026-11-19T00:25:04.330Z
started_at: 2026-11-18T21:02:16.459Z
closed_at: 2026-11-19T00:25:04.330Z
close_reason: "Landed in #582 (14f9ec033)"
resolution: null
duplicate_of: null
---
Phase 1. auto (default: app on macOS when detected), app (refuse when missing), browser. Known field in ApplicationConfig. --doctor --json reports value and source.

## Notes

2026-11-18: built in jlevy/metabrowser#582 (open, not merged). src/metabrowser/open_in.py reads --open-in, then METABROWSER_OPEN_IN, then open_in in config.yml, then the default auto, and records the source (flag, environment, config, default). ApplicationConfig.open_in in cache/records.py, with softschema and conformance cases. --doctor prints an open_in line on a clean run; --doctor --json adds open_in {value, source, app}, where app is what detection found (null under browser). An unreadable preference, or app where no app takes a target, is a doctor problem. --present reads only the setting from config.yml (bounded by CONFIG_MAX_BYTES, through the owner-only helper) to keep the dry run near --version; tests/test_open_in.py holds that reader to read_config's answer. Not built: a command that writes open_in, so config.yml is edited by hand. Bare metab PATH does not read the preference (plan Q4, mb-6n8j). Close when #582 merges.


2026-11-18, review A on #582: present_browser: false in config.yml (read from the file alone, no flag or variable overrides it) turns browser delivery off, code browser_off, status 4; --doctor reports it. Default unset = allowed, an owner question in the PR. Head bafef973e.

2026-11-18, review B on #582: no option of the command lifts present_browser; --present now refuses --config-dir (a usage error), which had let a command a sandbox rule matches read an empty configuration directory. METABROWSER_CONFIG_DIR, XDG_CONFIG_HOME, and HOME still choose the directory, and one without config.yml allows a browser; the docs, open_in.py, arch-cli.md, the skill, and the changelog fragment changelog.d/mb-gh6l.md say so. The skill adds --open-in app to every rerun outside the sandbox, pinned by test_skill_commands. Head 4ec4a0bb5.
