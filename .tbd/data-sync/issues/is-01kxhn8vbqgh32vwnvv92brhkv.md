---
type: is
id: is-01kxhn8vbqgh32vwnvv92brhkv
title: Upgrade MetaBrowser to next published KPress patch
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/specs/metabrowser-v0.1.0.md
labels: []
dependencies: []
parent_id: is-01kxgmkc6gb2e8s23jf409j4bv
created_at: 2026-07-15T01:11:45.270Z
updated_at: 2026-07-15T02:21:51.403Z
closed_at: 2026-07-15T02:21:51.402Z
close_reason: MetaBrowser now pins and verifies the exact public kpress==0.2.2 release, including the host-decoded export seam and complete 625-test package gate.
---
After the post-v0.2.0 KPress changes are published, update MetaBrowser's exact first-party pin, lock, supply-chain exception, policy checks, public docs, and complete verification gate.

## Notes

Upgraded the standalone package to exact public kpress==0.2.2 after PR #20 and Trusted Publishing completed. Verified registry wheel SHA256 46c3e9f0496f30d7e5c19c08c38a96634bee257af15124da0795fa267e9698e1 and sdist SHA256 475f78dde2cd762f40add1351e3ca49b6c186182b2ef6fe1f8069182e14fb2cc; lock contains only the expected KPress package/artifact changes and no new dependencies. Full MetaBrowser gate passes 625 tests.
