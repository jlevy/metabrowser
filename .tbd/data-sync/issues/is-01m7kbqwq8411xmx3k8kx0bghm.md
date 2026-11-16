---
type: is
id: is-01m7kbqwq8411xmx3k8kx0bghm
title: "PR #485 B4: The attestation command in mb-xd4o cannot run as written"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
hold: null
hold_until: null
created_at: 2026-11-16T23:40:39.527Z
updated_at: 2026-11-16T23:48:27.364Z
started_at: 2026-11-16T23:40:40.271Z
closed_at: 2026-11-16T23:48:27.363Z
close_reason: "Fixed in 9e7d362be: mb-xd4o's command is gh attestation verify FILE --repo jlevy/metabrowser --signer-workflow ... --source-ref ...; checked against gh 2.98.0's help (--owner or --repo required)."
resolution: null
duplicate_of: null
---
Low. PLAN:629-630. gh attestation verify needs --owner or --repo and the file. Fix: gh attestation verify FILE --repo jlevy/metabrowser --signer-workflow ... --source-ref .... Review B (follow-up, round 2) of PR #485: https://github.com/jlevy/metabrowser/pull/485#pullrequestreview-5929906549
