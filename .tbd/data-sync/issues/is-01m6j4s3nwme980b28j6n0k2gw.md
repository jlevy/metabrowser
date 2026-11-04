---
type: is
id: is-01m6j4s3nwme980b28j6n0k2gw
title: Show small lazy GitHub author avatars in PR metadata
kind: task
status: in_progress
priority: 1
version: 6
spec_path: docs/design-system.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6j4m8h98qy2w5w5wj5d46gj
hold: null
hold_until: null
created_at: 2026-11-04T02:04:03.131Z
updated_at: 2026-11-04T02:56:02.237Z
started_at: 2026-11-04T02:28:29.842Z
---
Owner requests a small circular profile image alongside the GitHub author. Reuse existing metadata/avatar facilities where possible; audit minimal catalog/detail fields and CSP. Explicit small dimensions, circular clipping, lazy loading/async decode, meaningful decorative/accessibility choice and graceful missing-image fallback. Avoid fetching all catalog avatars, extra per-row API calls, or blocking PR content. Use fixed validated GitHub avatar hosts or existing cache/proxy policy; no new dependency.

## Notes

Frontend validates exact canonical HTTPS avatars.githubusercontent.com/(u|in)/decimal?s=40, renders optional decorative lazy18px anonymous/no-referrer images for catalog/header/conversation using the same actor as username, and retains the fixed slot on failure. Backend fields coordinated separately. Direct production controls cover invalid URLs, bots, actor/merger identity, request attributes and image failure; no per-row data calls added.
