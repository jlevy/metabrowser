---
type: is
id: is-01m7nnxmbvvk8ctg8ckb0tzys7
title: Detect the app through LaunchServices and deliver by open -b
kind: feature
status: in_progress
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-17-open-anything-from-cli-and-app.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m7nnxvge8wvp33zmj3nkpnvg
parent_id: is-01m7nnxhaqce1g2ewec3wbaf7e
hold: null
hold_until: null
created_at: 2026-11-17T21:17:02.203Z
updated_at: 2026-11-18T22:10:15.308Z
started_at: 2026-11-18T21:02:22.182Z
---
Phase 1. ctypes LSCopyApplicationURLsForBundleIdentifier for the release bundle id; dev bundle only when chosen; test seam for goldens. Deliver with open -b <bundle> TARGET; map LaunchServices refusal to blocked. Browser path starts a detached server and opens the page once it answers.

## Notes

2026-11-18, checked against main a1100bca6. Landed in jlevy/metabrowser#540 (src/metabrowser/cli/present.py): LaunchServices detection through ctypes LSCopyApplicationURLsForBundleIdentifier, delivery by /usr/bin/open -b, LaunchServices refusal mapped to exit 5 (lookup_failed, open_failed) and no app to exit 4. Changed shape: it tries the release bundle id and then the dev one unless --app-bundle-id or METABROWSER_APP_BUNDLE_ID names one, and sends only to a build in an Applications folder (APP_INSTALL_LOCATIONS) whose Info.plist has MetabrowserOpensURLs. Remaining: the browser path (start a detached server, open the page once it answers, report delivered_to browser with the URL, and the pid until mb-qzny's idle exit); delivered_to is only app or none today. This also carries what mb-fb5k left (closed by #540).


2026-11-18: the browser path is built in jlevy/metabrowser#582 (open, not merged). serve_detached in cli/present.py starts the ordinary metab server (SERVER_COMMAND) with os.posix_spawn, in its own session, with output to an owner-only log in the logs directory and no other inherited descriptor. It waits up to server_announce_timeout_s for the Serving line, then reports delivered_to browser with url, pid, log, and the kill command that stops it. Codes: server_started and server_starting (0), server_failed (1). Under auto, the app codes that end in exit 4 fall back to a browser, with the reason in the report's fallback; lookup_failed stays 5. Each delivery starts a new server: reuse waits on mb-5xi4, idle exit on mb-qzny. Close when #582 merges.
