---
type: is
id: is-01m8hhs5j4a18my57acn1bw1af
title: Remove the standalone pull request link from the navigation footer
kind: bug
status: closed
priority: 2
version: 4
labels: []
dependencies: []
created_at: 2026-11-28T17:03:25.763Z
updated_at: 2026-11-28T17:49:33.452Z
closed_at: 2026-11-28T17:21:29.869Z
close_reason: "Implemented, independently reviewed, and verified by green CI. Delivered in open PR #926."
resolution: null
duplicate_of: null
---
Use the existing browser and native navigation history to return to previously visited pages. Keep source fetch and revision actions in the footer.

## Notes

PR #926 merged at 31f1af0f after independent review and green exact-head and base CI. The combined merge tree matches the tested one. The separate title-bar design remains in draft PR #927.
