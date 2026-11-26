---
type: is
id: is-01m8cfgb7tygn471x857dgjzpb
title: "KPress: sanitize without diagnostics, for Metabrowser's Markdown projection"
kind: task
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-11-26T17:47:27.347Z
updated_at: 2026-11-26T17:47:27.347Z
---
Measured for mb-3dkn on docs/plugins.md (85 KB a side), best of 7 at load ~50: sanitize_raw_html takes ~56 ms a side, of which ~49 ms is its diagnostics (the _SanitizerAudit parse ~17 ms and two _content_events parses ~32 ms). markdown_projection._hardened discards the diagnostics. A keyword such as diagnose=False that skips the audit and the content-event comparison, keeping nh3.clean, the filter errors, and _canonical_inputs, would cut about a third of each side's ~135 ms. Needs a KPress PR and release, then a kpress bump here.
