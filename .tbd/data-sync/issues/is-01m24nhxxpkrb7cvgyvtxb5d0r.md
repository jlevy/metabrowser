---
type: is
id: is-01m24nhxxpkrb7cvgyvtxb5d0r
title: Audit current main for release readiness and install development build
kind: task
status: closed
priority: 1
version: 12
labels: []
dependencies: []
child_order_hints:
  - is-01m24prkbajqpa7hj9km2yts1n
  - is-01m24prp8erw9pz74yk216z2r0
  - is-01m24prrthw0y3a1gf4ycnzv22
  - is-01m24prv3xysab8f4twwzsyxcj
  - is-01m24prxgbn1g54s2q6jwj3b2w
  - is-01m24v531rws8fqeztbdh3xx02
  - is-01m24wene3t205tj4qgkybczrt
  - is-01m262x5e7vy8h0k325mq4xv24
  - is-01m2634k3vzpvryvzmjvce0pcr
created_at: 2026-09-10T03:25:04.300Z
updated_at: 2026-09-10T17:56:03.103Z
closed_at: 2026-09-10T17:56:03.102Z
close_reason: "Completed on codex/release-hardening at 632f74bc. Astra-max senior review approved with no remaining blockers; make verify passed 1,917 tests, 99 CLI goldens, audits, distribution inspection, and installed-wheel smoke; PR #108 CI is green across Python 3.12, 3.13, 3.14, and 3.14t; uv tool 0.9.0 was replaced with 0.9.2.dev131+632f74bc and its doctor and no-browser API scenario pass."
resolution: null
duplicate_of: null
---
Review the consolidated origin/main tip against the latest published release and repository release contracts; inspect open work and remote CI; run the complete make verify gate; then replace the user-level uv tool installation with the reviewed checkout and smoke-test the installed metab and metabrowser entry points. Record any release blockers instead of declaring readiness.
