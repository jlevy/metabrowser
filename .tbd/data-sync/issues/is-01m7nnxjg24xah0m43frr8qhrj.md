---
type: is
id: is-01m7nnxjg24xah0m43frr8qhrj
title: "metab TARGET --present: client-mode resolution, report, --json, --dry-run, exit codes"
kind: feature
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-17-open-anything-from-cli-and-app.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7nnxmbvvk8ctg8ckb0tzys7
  - type: blocks
    target: is-01m7nnxrj9txmcjawfmkz6frad
parent_id: is-01m7nnxhaqce1g2ewec3wbaf7e
created_at: 2026-11-17T21:17:00.290Z
updated_at: 2026-11-18T20:21:04.158Z
closed_at: 2026-11-18T20:21:04.157Z
close_reason: "Landed in jlevy/metabrowser#540 (src/metabrowser/cli/present.py, cli/exit_codes.py exits 3/4/5, goldens tests/golden/cli-present.tryscript.md and cli-present-delivery.txt): resolution without clone or server import, --dry-run, the report, --format json (not --json). The app-or-browser choice and browser delivery were not built; they remain under mb-gh6l (open_in) and mb-kze0 (browser path)."
resolution: null
duplicate_of: null
---
Phase 1. Resolve TARGET as ROOT is classified (folder, file, source URL with selection; --path kept) without cloning; choose app/browser; report delivered_to, confirmed, url, reason; distinct exit codes for blocked and app-missing in cli/exit_codes.py; --dry-run --json stops after choosing. Must not import the server. Goldens for every target kind.
