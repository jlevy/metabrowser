---
type: is
id: is-01m2pttd3exe4x0cjsvyssr21k
title: Windows current-user-only ACL enforcement for cache and configuration directories
kind: task
status: open
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: null
labels: []
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-17T04:43:24.652Z
updated_at: 2026-10-03T06:14:38.841Z
started_at: 2026-09-23T00:40:31.032Z
---
mb-xa0p enforces owner-only application-home storage on POSIX and fails closed on Windows: every private-storage call there refuses as unverifiable, so no private cache data is written. Implement the equivalent current-user-only ACL creation and verification for src/metabrowser/home.py (validate_private_home, ensure_private_directory, open_private_file) using the standard library (for example ctypes over the Windows security APIs) without adding a dependency, including refusal of foreign-owned, permissive, or reparse-point ancestors. Requires a Windows CI runner before the enforcement can be trusted; until then Windows keeps the fail-closed behavior.

## Notes

2026-09-22 status audit: Windows ACL enforcement and Windows CI remain open; no Windows implementation or validation is claimed for v0.12. Storage epic mb-j2b7 now separates cache and configuration roots. Any Windows implementation must enforce the same owner-only/no-follow guarantees for both roots and define platform-specific directory resolution. METABROWSER_HOME and its single-root assumption are superseded. Windows remains fail-closed until validated on Windows CI.
