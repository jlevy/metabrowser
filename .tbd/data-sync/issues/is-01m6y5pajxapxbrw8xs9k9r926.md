---
type: is
id: is-01m6y5pajxapxbrw8xs9k9r926
title: "Research: refresh desktop packaging research for a native macOS app"
kind: task
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-08T18:10:53.659Z
updated_at: 2026-11-08T20:12:50.756Z
started_at: 2026-11-08T18:11:00.633Z
closed_at: 2026-11-08T20:12:50.745Z
close_reason: "Delivered as docs/project/research/research-2026-11-08-macos-app-packaging.md in jlevy/metabrowser#338: shell options A-F (Swift WKWebView recommended, gated on a WebKit measurement), uv runtime layouts and isolation, CLI layering and shared installs, plugins without rebuilds, agent-controlled server options P/P+/S/F, and security models. August brief restored with a dated addendum. Local lint-check and docs tests pass; CI pending."
resolution: null
duplicate_of: null
---
Refresh docs/project/research/research-2026-08-16-desktop-app-packaging.md for a macOS-first native app: re-verify Electron, Tauri, and Electrobun against current sources; add hand-written Swift WKWebView, pywebview and Python-native packagers, browser-provided app windows, and long-tail frameworks; study the uv runtime layout, macOS signing and privacy rules, shipping precedents, and the sibling paraverse app; recommend a shell, a uv layout, and the server host contract.
