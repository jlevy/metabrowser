---
type: is
id: is-01m78fvxxksc6ybfthkyzgbtdn
title: One registry in the state home, read fail-closed, with scopes
kind: task
status: open
priority: 1
version: 14
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
assignee: null
delegate: null
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
hold: null
hold_until: null
created_at: 2026-11-12T18:21:07.379Z
updated_at: 2026-11-26T08:37:20.285Z
started_at: 2026-11-26T08:35:34.383Z
---
Phase 2 (plan: Sources and Scopes, The Registry, Trust and Consent; Key Decision 7). plugins.yml in the state home, which exists on main (state_directory in home.py; the app passes its variables), contract metabrowser:PluginSources/0.1. Unlike config.yml it is read fail-closed by entry: an entry with a field this metab does not know is kept on a write and not used, and --doctor names it, because a newer release may have added the field to narrow a grant. Written by metab by atomic replace under the home's lock, read with sharing refused, never created by serving. Sources with scopes (everywhere, named folders, a clone) and an authority (full, or confined): metab --plugins-add PATH for directories and environments with --dry-run (metadata only, imports nothing) and --expect SHA256, --plugins-remove ID, --plugins-scope-add ID FOLDER; the ownership rule on add. Directory sources' Python on an isolated interpreter. GET /api/plugins with locations relative to the root or ~, never absolute, with its rows in the parity registry and the views map; the sources model in metab --plugins --json and --doctor.

## Notes

Rewritten 2026-11-26 with the plan's second revision (review against main); supersedes the 2026-11-12 body.
