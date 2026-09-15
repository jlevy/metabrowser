---
type: is
id: is-01m2h9jjh45d8db9rbd0qtscf7
title: "Plugin SDK: installed plugin address spaces and browser navigation lifecycle"
kind: feature
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2h7hrjt6yzb16neh8g2zvsd
parent_id: is-01m10vgwqwn8gjdv8fm183vztr
created_at: 2026-09-15T01:05:50.112Z
updated_at: 2026-09-15T01:19:57.063Z
---
Add an installed-plugin AddressSpaceSpec and registerAddressSpace SDK surface with parser, formatter, selection apply/mount, preview claim, startup, popstate, root replacement, and disposal. Core refuses reserved, duplicate, or overlapping prefixes and requires exactly one owner for each address; browser navigation, href generation, and metab --show share the registry. Treat as additive SDK 0.6 only if existing behavior is unchanged, updating plugin docs and CHANGELOG; otherwise bump all manifests. Prove the exact /review lifecycle through production functions in hosted-review-session and cli-ui-hosted-review.
