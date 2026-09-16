---
type: is
id: is-01m2mf2bbmrqrewkt8dc22794s
title: Validate browser parser fields before composing their ID
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase-0c1
  - review
dependencies: []
parent_id: is-01m2krxbqajmpk9zhjm8berj18
created_at: 2026-09-16T06:39:33.235Z
updated_at: 2026-09-16T07:13:34.389Z
closed_at: 2026-09-16T07:13:34.389Z
close_reason: "Fixed in 614fef15793ff7cffd0c4e85a577342472fd9686, independently re-reviewed with no remaining findings, published in the PR #135 disposition map, and validated by green local and GitHub CI."
resolution: null
duplicate_of: null
---
Fable R18: BrowserParserSpec validation applied a regex only to the f-string parser_id, so non-string export_name values such as None could stringify to valid identifiers and pass doctor. Validate module_id and export_name independently as runtime strings and add malformed-shape regressions.
