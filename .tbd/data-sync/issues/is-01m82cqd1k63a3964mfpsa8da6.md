---
type: is
id: is-01m82cqd1k63a3964mfpsa8da6
title: Accept GitHub repository shortcuts in native Open URL
kind: feature
status: in_progress
priority: 2
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/694
    at: 2026-11-22T19:57:09.704Z
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
created_at: 2026-11-22T19:46:28.521Z
updated_at: 2026-11-22T19:57:15.314Z
---
Accept a bare GitHub owner/repo in the native Command-L panel. Normalize through the existing GitHub repository URL grammar and preserve full and schemeless GitHub URLs. Keep CLI delivery semantics unchanged. Verify through the Swift parser, panel state and the live metab dry run.

## Notes

Implemented on b0e193f2e. The native panel uses the existing repository URL grammar to expand a bare GitHub owner/repo. The 24 focused Swift tests passed, including all three forms against the real metab dry run. Normal pre-commit passed. Exact hosted general and macOS gates pending.
