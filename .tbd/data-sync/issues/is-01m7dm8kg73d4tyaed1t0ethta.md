---
type: is
id: is-01m7dm8kg73d4tyaed1t0ethta
title: Pulls says 'Run gh auth login' although gh is signed in (app-launched server)
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-14T18:14:09.153Z
updated_at: 2026-11-14T18:14:09.153Z
---
The user (2026-11-14, forwarded from another session) saw in a Metabrowser app window's Pulls tab: "jlevy/metabrowser — Run gh auth login --hostname github.com to connect." gh 2.98.0 at ~/.local/bin/gh is authenticated with stored credentials (no GH_TOKEN). Possibly the release-variant window from the end-to-end run (mb-hwxu), launched from a DMG with fresh settings; possibly a real fresh-install bug: a GUI-launched app's server lacks ~/.local/bin (or /opt/homebrew/bin) on PATH, or cannot read gh's credential store, and the panel reports "auth login" instead of "gh not found".

Done when the cause is shown with evidence (the server's PATH, which gh ran, the exact command and its error); if real, the app's server finds gh the way the user's shell does (or the panel says gh was not found and how to fix it), with a test.
