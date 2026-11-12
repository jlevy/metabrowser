---
type: is
id: is-01m78fvxxksc6ybfthkyzgbtdn
title: Plugin source registry, directory sources, GET /api/plugins, and sources in --plugins and --doctor
kind: task
status: open
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies:
  - type: blocks
    target: is-01m78fvywxsmc0m4481ypk3zbq
  - type: blocks
    target: is-01m78fw226k1aejzey9xamd4e7
  - type: blocks
    target: is-01m78fwdh6mt5frdg94thadjkh
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:21:07.379Z
updated_at: 2026-11-12T18:47:16.343Z
---
Phase 1 (plan: Sources, The Registry, Trust and Consent, Diagnostics, CLI and Routes). plugins.yml in the configuration home with contract metabrowser:PluginSources/0.1 (enforced), read through the home's verified reader with sharing refused, never created by serving; --plugins-add DIR [--dry-run] [--yes] and --plugins-remove ID for directory sources; precedence and collision reporting per the Sources table; the sources model in --plugins --json and --doctor --json; GET /api/plugins with its parity row and golden. No route writes the registry: record that reason in the parity table. Lets the macOS app reach JavaScript-only plugin folders, which its child environment allowlist blocks today.

## Notes

Review (2026-11-12, independent design review; plan updated to match): plugins.yml is permissive like config.yml (unknown fields kept and written back), since several Metabrowser versions can share a home. Serving does not import metabrowser.home today (tests/test_plugin_public_api.py holds the boundary): add a small reader, measure its import, and move the boundary deliberately. --plugins-add --dry-run reads metadata only and prints a listing hash; --yes --expect SHA256 refuses a changed listing. Apply the ExecutableTrust ownership rule to added sources. GET /api/plugins shows locations relative to the root or ~, never absolute paths. No 'gap' wording: writes are CLI modes with goldens, the read model is a route.
