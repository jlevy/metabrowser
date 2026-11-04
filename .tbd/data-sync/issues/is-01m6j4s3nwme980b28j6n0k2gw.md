---
type: is
id: is-01m6j4s3nwme980b28j6n0k2gw
title: Show small lazy GitHub author avatars in PR metadata
kind: task
status: closed
priority: 1
version: 7
spec_path: docs/design-system.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6j4m8h98qy2w5w5wj5d46gj
hold: null
hold_until: null
created_at: 2026-11-04T02:04:03.131Z
updated_at: 2026-11-04T17:14:29.699Z
started_at: 2026-11-04T02:28:29.842Z
closed_at: 2026-11-04T17:14:29.699Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Owner requests a small circular profile image alongside the GitHub author. Reuse existing metadata/avatar facilities where possible; audit minimal catalog/detail fields and CSP. Explicit small dimensions, circular clipping, lazy loading/async decode, meaningful decorative/accessibility choice and graceful missing-image fallback. Avoid fetching all catalog avatars, extra per-row API calls, or blocking PR content. Use fixed validated GitHub avatar hosts or existing cache/proxy policy; no new dependency.

## Notes

Frontend validates exact canonical HTTPS avatars.githubusercontent.com/(u|in)/decimal?s=40, renders optional decorative lazy18px anonymous/no-referrer images for catalog/header/conversation using the same actor as username, and retains the fixed slot on failure. Backend fields coordinated separately. Direct production controls cover invalid URLs, bots, actor/merger identity, request attributes and image failure; no per-row data calls added.
