---
type: is
id: is-01m5x48vk0v4d66jt8peghj2ar
title: "Update the seven tbd doc-forks #219 brought in"
kind: chore
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-10-26T22:11:07.483Z
updated_at: 2026-10-26T22:11:07.483Z
---
Merging #219 on 2026-10-26 brought in `.tbd/doc-forks/`, which forks seven of tbd's shortcut docs so the repository can carry its own PR-sizing guidance. The base snapshots under `.tbd/doc-forks/base/shortcut/` were captured against the tbd of 2026-09-23, and the installed tbd is now 0.10.0, so `tbd sync` reports:

    • Docs: 7 forked doc(s) have upstream updates; run 'tbd docs update'

Run `tbd docs update`, re-read each fork to keep the local PR-sizing guidance that #219 added, and commit what the tool generates.

Not a blocker and not a build failure: it is drift in generated documentation, and nothing in the build, CI, test or publishing path reads these files. It is recorded because AGENTS.md says the tbd-generated hook configs, session scripts and agent skills are committed exactly as generated, and warns that a local edit survives only until the next upgrade reverts it and "someone has to notice". This is the noticing.

Checked on the merged result before #219 landed: devtools.public_hygiene, devtools.check_supply_chain, devtools.check_parity and the flowmark format check (with --no-cache) all pass with these files present, so nothing is gated on the drift.
