---
type: is
id: is-01m24nhxxpkrb7cvgyvtxb5d0r
title: Audit current main for release readiness and install development build
kind: task
status: in_progress
priority: 1
version: 11
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
updated_at: 2026-09-10T16:41:41.743Z
---
Review the consolidated origin/main tip against the latest published release and repository release contracts; inspect open work and remote CI; run the complete make verify gate; then replace the user-level uv tool installation with the reviewed checkout and smoke-test the installed metab and metabrowser entry points. Record any release blockers instead of declaring readiness.
