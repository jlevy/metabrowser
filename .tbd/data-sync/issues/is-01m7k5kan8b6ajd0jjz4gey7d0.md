---
type: is
id: is-01m7k5kan8b6ajd0jjz4gey7d0
title: "PR #485 A1: Agents act as the owner, and the plan gates neither local signing nor the CI approval against them"
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
hold: null
hold_until: null
created_at: 2026-11-16T21:53:18.503Z
updated_at: 2026-11-16T22:09:53.308Z
started_at: 2026-11-16T21:53:36.130Z
closed_at: 2026-11-16T22:09:53.307Z
close_reason: "Fixed in 83ef69fc3: Who Can Sign section; O1 moves the identity and notary profile into a dedicated release keychain (password at a prompt, locks on sleep and after 15 min idle, identity imported with neither -A nor -T, Allow never Always Allow); mb-qu6j reports whether it is unlocked; O4 turns the administrator bypass off; the owner approves macos-release deployments only in the web UI; the agent rule adds never calling the pending-deployments endpoint, never approving a deployment, and signing only during a release the owner started; Q1 and Risks weigh it."
resolution: null
duplicate_of: null
---
High. PLAN:56-57, :380-382, :386-387, :404-406, :523-528. O1 allows codesign once, after which any process running as the owner can sign; the notary profile is readable by any notarytool run; the CI required reviewer is the owner's account, which agents use through gh, and O4 keeps the administrator bypass. Fix: a dedicated, normally locked keychain with a short auto-lock that the doctor reports on; O1 says Allow, never Always Allow; O4 disallows the bypass; the owner approves macos-release deployments only in the web UI; the agent rule adds never calling the pending-deployments endpoint, never approving a deployment, and signing only during a release the owner started; weigh it in Q1. Review A (round 1) of PR #485: https://github.com/jlevy/metabrowser/pull/485#pullrequestreview-5928293258
