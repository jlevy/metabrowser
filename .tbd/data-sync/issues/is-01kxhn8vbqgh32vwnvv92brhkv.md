---
type: is
id: is-01kxhn8vbqgh32vwnvv92brhkv
title: Upgrade MetaBrowser to next published KPress patch
kind: task
status: open
priority: 1
version: 2
spec_path: docs/specs/metabrowser-v0.1.0.md
labels: []
dependencies: []
parent_id: is-01kxgmkc6gb2e8s23jf409j4bv
created_at: 2026-07-15T01:11:45.270Z
updated_at: 2026-07-15T01:12:00.359Z
---
After the post-v0.2.0 KPress changes are published, update MetaBrowser's exact first-party pin, lock, supply-chain exception, policy checks, public docs, and complete verification gate.

## Notes

MetaBrowser already pins latest published kpress==0.2.0. Verified GitHub and PyPI contain no newer release; KPress main is seven commits ahead of v0.2.0, including the same-document tooltip fix and tooling updates. Awaiting authorization or publication of the next patch release before changing the exact dependency.
