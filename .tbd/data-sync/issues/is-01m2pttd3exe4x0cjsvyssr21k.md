---
type: is
id: is-01m2pttd3exe4x0cjsvyssr21k
title: Windows current-user-only ACL enforcement for the application home
kind: task
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: null
labels: []
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-17T04:43:24.652Z
updated_at: 2026-09-23T00:40:58.693Z
started_at: 2026-09-23T00:40:31.032Z
---
mb-xa0p enforces owner-only application-home storage on POSIX and fails closed on Windows: every private-storage call there refuses as unverifiable, so no private cache data is written. Implement the equivalent current-user-only ACL creation and verification for src/metabrowser/home.py (validate_private_home, ensure_private_directory, open_private_file) using the standard library (for example ctypes over the Windows security APIs) without adding a dependency, including refusal of foreign-owned, permissive, or reparse-point ancestors. Requires a Windows CI runner before the enforcement can be trusted; until then Windows keeps the fail-closed behavior.

## Notes

2026-09-22 status audit: remove the obsolete v0.11 release assignment. Windows ACL enforcement and Windows CI remain open; no platform implementation or validation is claimed by the v0.12 alpha review. The current cache continues to fail closed on Windows.
