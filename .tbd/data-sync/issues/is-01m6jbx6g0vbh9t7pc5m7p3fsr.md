---
type: is
id: is-01m6jbx6g0vbh9t7pc5m7p3fsr
title: Remove the unreachable catalog GitHub-footer projection
kind: chore
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6hkbt0t0qhvrhxhktgefe38
created_at: 2026-11-04T04:08:37.118Z
updated_at: 2026-11-04T04:08:37.118Z
---
Finalwheelbrowserpreparation confirmed describePulls initializes github:null and never assigns it; the See the rest on GitHub renderer branch is unreachable under the current incremental catalog model. No user-visible failure; helperconstructor/source-session coverage is honest, not a fabricated live-route test. Follow-up can remove the dead model property/renderer with affected model/session expectation cleanup. Keep outside current frozen539finalgate to avoid unrelated source churn; no backward-compatibility requirement justifies retaining it.
