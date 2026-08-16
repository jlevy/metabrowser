---
type: is
id: is-01kxry31k2e62styhj8t59jj12
title: "Platform A4: core bounded async subprocess runner (timeout, output caps, sanitized env, cancel-on-disconnect)"
kind: feature
status: open
priority: 1
version: 4
labels: []
dependencies:
  - type: blocks
    target: is-01kxse0vfwwkcq1a6mfdx6v9ad
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T21:00:33.250Z
updated_at: 2026-08-16T08:06:16.208Z
extensions:
  linear:
    id: b2c972be-cc9e-4692-b3ca-d041777ec425
    linked_at: 2026-08-16T08:06:16.208Z
---
Only subprocess use today is macOS mount detection (watch_backends.py:135). Git adapter, archives, future tools need one safe runner with gz_io-style bounds.
