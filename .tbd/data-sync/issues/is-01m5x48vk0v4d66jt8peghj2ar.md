---
type: is
id: is-01m5x48vk0v4d66jt8peghj2ar
title: "Update the seven tbd doc-forks #219 brought in"
kind: chore
status: closed
priority: 3
version: 4
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-10-26T22:11:07.483Z
updated_at: 2026-11-04T17:14:29.497Z
started_at: 2026-11-01T16:05:50.764Z
closed_at: 2026-11-04T17:14:29.497Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Merging #219 on 2026-10-26 brought in `.tbd/doc-forks/`, which forks seven of tbd's shortcut docs so the repository can carry its own PR-sizing guidance. The base snapshots under `.tbd/doc-forks/base/shortcut/` were captured against the tbd of 2026-09-23, and the installed tbd is now 0.10.0, so `tbd sync` reports:

    • Docs: 7 forked doc(s) have upstream updates; run 'tbd docs update'

Run `tbd docs update`, re-read each fork to keep the local PR-sizing guidance that #219 added, and commit what the tool generates.

Not a blocker and not a build failure: it is drift in generated documentation, and nothing in the build, CI, test or publishing path reads these files. It is recorded because AGENTS.md says the tbd-generated hook configs, session scripts and agent skills are committed exactly as generated, and warns that a local edit survives only until the next upgrade reverts it and "someone has to notice". This is the noticing.

Checked on the merged result before #219 landed: devtools.public_hygiene, devtools.check_supply_chain, devtools.check_parity and the flowmark format check (with --no-cache) all pass with these files present, so nothing is gated on the drift.

## Notes

2026-11-01: fixed in PR #272, open, CI green at its last read. Close when it merges; its required review has not run.
