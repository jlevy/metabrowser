---
type: is
id: is-01m7kbrbabfqkxv95e340xg8tj
title: A commit author's profile icon shows their GitHub avatar where the GitHub plugin can resolve it by the commit's oid (GraphQL object(oid) author avatarUrl), cached and bounded, swapping the person glyph after paint; no author email is sent anywhere
kind: feature
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m7k1tfbjprkhwep83e9xbzhh
created_at: 2026-11-16T23:40:54.474Z
updated_at: 2026-11-16T23:40:54.474Z
---
The rest of mb-s3g8 after #487 (which holds the 18 px box from first paint with a neutral glyph). Needs a GitHub plugin route with a parity row and golden, a cache and bound, and an SDK hook the core commit page calls after paint.
