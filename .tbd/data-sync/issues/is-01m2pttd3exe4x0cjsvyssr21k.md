---
type: is
id: is-01m2pttd3exe4x0cjsvyssr21k
title: Windows current-user-only ACL enforcement for the application home
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-09-17T04:43:24.652Z
updated_at: 2026-09-17T04:43:24.652Z
---
mb-xa0p enforces owner-only application-home storage on POSIX and fails closed on Windows: every private-storage call there refuses as unverifiable, so no private cache data is written. Implement the equivalent current-user-only ACL creation and verification for src/metabrowser/home.py (validate_private_home, ensure_private_directory, open_private_file) using the standard library (for example ctypes over the Windows security APIs) without adding a dependency, including refusal of foreign-owned, permissive, or reparse-point ancestors. Requires a Windows CI runner before the enforcement can be trusted; until then Windows keeps the fail-closed behavior.
