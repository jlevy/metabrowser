---
type: is
id: is-01m7ey9kcf16gqcqxeejzp6tw7
title: CLI accepts options it then ignores
kind: bug
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies: []
parent_id: is-01m7ey9fq9v53mp3c974mg2d89
created_at: 2026-11-15T06:28:41.998Z
updated_at: 2026-11-15T06:28:41.998Z
---
--log-level is accepted with --diff and ignored; --zone and --project are accepted without --gcp and ignored; --ssh-options is ignored with --gcp. Refuse or apply them.
