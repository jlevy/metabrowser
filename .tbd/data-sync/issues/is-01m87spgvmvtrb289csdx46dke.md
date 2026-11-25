---
type: is
id: is-01m87spgvmvtrb289csdx46dke
title: The trusted shell can be framed by another site
kind: bug
status: open
priority: 2
version: 2
spec_path: docs/project/architecture/arch-threat-model.md
labels:
  - security
dependencies: []
parent_id: is-01m8898kcprj50strs0xfshvjn
created_at: 2026-11-24T22:09:23.314Z
updated_at: 2026-11-25T02:43:53.850Z
---
Threat model T5. The trusted shell sends no CSP, X-Frame-Options, or frame-ancestors (server.py index returns plain HTML when active_content is on), so any website can frame it and try to trick a click on its controls (pin, refresh). Send frame-ancestors 'none' and X-Frame-Options: DENY on the trusted shell too, and pin it in tests/test_untrusted_markdown.py's trusted-shell test.
