---
type: is
id: is-01m2md9arhx6qq2jga12jh4jpw
title: Bind ResourceSet semantics to the exact installed registry snapshot
kind: bug
status: closed
priority: 0
version: 2
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase:hosted-review-0c1
  - review:fable
dependencies: []
parent_id: is-01m2krxbqajmpk9zhjm8berj18
created_at: 2026-09-16T06:08:24.848Z
updated_at: 2026-09-16T07:13:34.212Z
closed_at: 2026-09-16T07:13:34.212Z
close_reason: "Fixed in 614fef15793ff7cffd0c4e85a577342472fd9686, independently re-reviewed with no remaining findings, published in the PR #135 disposition map, and validated by green local and GitHub CI."
resolution: null
duplicate_of: null
---
Independent delivery review reproduced that validate_record receives only a contract map and ResourceSet's validator falls back to the process-global get_installed_registries snapshot. A custom explicit InstalledRegistries snapshot with its own valid profile then fails as unregistered. Make artifact/record validation carry the complete atomic InstalledRegistries semantic context or bind the exact profile registry into ResourceSet validation after registry construction; add a non-global custom-profile regression.
