---
type: is
id: is-01m6hr8f0x7hr7mhchrtx1sqb7
title: Clarify GitHub CLI setup and validate optional dependency failures
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6hkbt0t0qhvrhxhktgefe38
child_order_hints:
  - is-01m6hra3df66c1bt2efxqw0q9q
  - is-01m6hrpg9zw9a8gxe6w7s3fqq2
hold: null
hold_until: null
created_at: 2026-11-03T22:25:14.780Z
updated_at: 2026-11-04T17:14:30.896Z
started_at: 2026-11-03T22:25:23.775Z
closed_at: 2026-11-04T17:14:30.896Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Owner requests a dependency/setup audit across local browsing, existing Git checkouts, managed repository URLs and PR metadata. Verify gh missing, signed out, too old/broken, and cached offline behavior; provide clean descriptive actionable UI/CLI messages and straightforward installation/authentication guidance aligned with tbd shortcut setup-github-cli. Prefer standard gh installation and gh auth login/status; no wrappers, unnecessary installer or compatibility scaffolding. Distinguish Git admission requirements from optional gh metadata support, keep cached reads network-free, and prove ordinary local browsing remains usable. Independent runtime and documentation agents audit findings before any forward change; final wheel acceptance covers relevant states.
