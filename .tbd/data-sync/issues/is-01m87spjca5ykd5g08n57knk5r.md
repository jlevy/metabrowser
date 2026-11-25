---
type: is
id: is-01m87spjca5ykd5g08n57knk5r
title: A served folder's own textconv and ext-diff drivers run under --untrusted
kind: bug
status: open
priority: 2
version: 2
spec_path: docs/project/architecture/arch-threat-model.md
labels:
  - security
dependencies: []
parent_id: is-01m8898kcprj50strs0xfshvjn
created_at: 2026-11-24T22:09:24.872Z
updated_at: 2026-11-25T02:45:54.270Z
---
Threat model T8. git/process.py READ_POLICY (isolate_user_config=False) honors a served folder's own .git/config, so its textconv and external-diff drivers run, even under --untrusted. A directory received whole (an archive) carries an author's config. Under the untrusted profile, read the folder's repository with --no-textconv --no-ext-diff (diff_driver_args) as a store is read; pin it.
