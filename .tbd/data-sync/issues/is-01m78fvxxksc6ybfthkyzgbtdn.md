---
type: is
id: is-01m78fvxxksc6ybfthkyzgbtdn
title: One registry in the state home, with scopes
kind: task
status: open
priority: 1
version: 10
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies:
  - type: blocks
    target: is-01m78fw226k1aejzey9xamd4e7
  - type: blocks
    target: is-01m78fwdh6mt5frdg94thadjkh
  - type: blocks
    target: is-01m78fw3ppt7qjecxb1m4r276q
  - type: blocks
    target: is-01m78fw2nz4rpf95kybngf40zq
  - type: blocks
    target: is-01m78fw36avwntyj23v52vqqdm
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:21:07.379Z
updated_at: 2026-11-12T21:18:05.873Z
---
Phase 3 (plan: Sources and Scopes, The Registry, Trust and Consent; Key Decision 7). plugins.yml in a new state home (METABROWSER_STATE_DIR, XDG_STATE_HOME/metabrowser, ~/.local/state/metabrowser), contract metabrowser:PluginSources/0.1, permissive like config.yml (unknown fields kept and written back), written by metab-plugins by atomic replace under the home's lock, read with sharing refused, never created by serving. Serving does not import the home module today (tests/test_plugin_public_api.py): add a small reader, measure its import, and move the boundary deliberately. Sources with scopes (everywhere, named folders, a clone): metab-plugins --add PATH for directories and environments with --dry-run (metadata only, imports nothing) and --expect SHA256, --remove ID, --scope-add ID FOLDER; the ownership rule on add. Directory sources' Python on an isolated interpreter. GET /api/plugins with locations relative to the root or ~, never absolute; the sources model in metab --plugins --json and --doctor.

## Notes

Body rewritten 2026-11-12 after the Fable 5.2 design review; it supersedes the earlier review notes. The plan's Key Decisions are awaiting the owner.
