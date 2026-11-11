---
type: is
id: is-01m7491aamdnrexwfg1cp56ke4
title: Update the tbd desktop guidelines with what the sister app's pipeline teaches
kind: task
status: open
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T03:04:46.163Z
updated_at: 2026-11-11T03:46:17.207Z
---
Phase 1. The release-pipeline work found improvements to macos-webview-shell-patterns: development and release variants, a sanitized PATH in bundle scripts, VERSION-file versioning checked against a prefixed tag, DMG volume-icon and signing details, JSON-checked notarytool status with saved logs and a tri-state NOTARIZE, an official-build preflight, a no-entitlements assertion, a downloader-style DMG check, release-job hygiene, and a corrected Homebrew cask example. PR them to jlevy/tbd, written for any project.
