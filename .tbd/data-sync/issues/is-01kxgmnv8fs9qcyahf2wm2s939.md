---
type: is
id: is-01kxgmnv8fs9qcyahf2wm2s939
title: Validate the standalone repository and distributions
kind: task
status: closed
priority: 1
version: 6
spec_path: docs/project/specs/done/plan-2026-07-14-metabrowser-v0.1.0-standalone-package.md
labels:
  - validation
dependencies:
  - type: blocks
    target: is-01kxgmnvg1heqtbjjc3bnz1pxk
parent_id: is-01kxgmkc6gb2e8s23jf409j4bv
created_at: 2026-07-14T15:42:08.142Z
updated_at: 2026-07-17T21:16:32.317Z
closed_at: 2026-07-14T15:59:46.681Z
close_reason: "Initial standalone import is committed and pushed in PR #1; local make verify and GitHub Actions pass on Python 3.12, 3.13, and 3.14 with clean distribution and installed-wheel validation."
---
Run formatting, lint, type, browser, public-hygiene, test, source-distribution, wheel, and isolated-install gates locally and in GitHub Actions.

## Notes

Local make verify passes with 591 tests and clean installed-wheel CLI/assets/plugins/KPress smoke coverage. GitHub Actions passes on Python 3.12, 3.13, and 3.14; external review check remains in progress.
