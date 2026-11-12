---
type: is
id: is-01m78fw3ppt7qjecxb1m4r276q
title: Project plugin declarations and trust
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies: []
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:21:13.301Z
updated_at: 2026-11-12T18:21:13.301Z
---
Phase 5 (plan: Trust and Consent; Sources). .metabrowser/plugins.toml in a served root names directories and environments by paths that must resolve inside the root; nothing runs before trust; ROOT --plugins-trust and --plugins-untrust record trust in plugins.yml keyed by the canonical root and the declaration's SHA-256, so a changed declaration is untrusted until approved; sources apply to that root's server only; never for Git sources opened from a URL, pins, mirrors, or --untrusted; the server reports an untrusted declaration for the app's trust bar. Replaces the macOS plan's project-plugin trust spec (mb-m1mw).
