---
type: is
id: is-01m0x6aedksxrggn0ba4tv66v0
title: Keep preview pending token rationale value-independent
kind: task
status: closed
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies: []
parent_id: is-01m0w542g2gzak7th85hx2bdz8
created_at: 2026-08-25T19:28:27.563Z
updated_at: 2026-08-25T19:31:06.841Z
closed_at: 2026-08-25T19:31:06.840Z
close_reason: Reworded the navigation-opacity token comment to describe intent without duplicating its numeric value; make format and make verify pass.
resolution: null
duplicate_of: null
---
Pre-commit review finding. src/metabrowser/static/styles.css describes the pending opacity token by restating its numeric percentage. Keep the rationale but remove the duplicated value so the comment cannot drift from the token. Acceptance: comment explains perceptual intent without restating the constant; formatting and design vocabulary tests pass.
