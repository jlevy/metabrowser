---
type: is
id: is-01kzctrvcdztesz9gabmf7zfsn
title: "git: /api/git/ route collection"
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-06-git-graph-view.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzcts0hgggxj5n7rrnj0t0br
  - type: blocks
    target: is-01kzctsqjdfn84ykr7cr4hzhxm
parent_id: is-01kzctqt5s7te6w75jm5pvg6g7
created_at: 2026-08-07T00:43:03.948Z
updated_at: 2026-08-07T01:29:03.000Z
closed_at: 2026-08-07T01:29:03.000Z
close_reason: null
---
Add metabrowser/git/routes.py exporting the route table for GET /api/git/repo, /api/git/refs, /api/git/log, and /api/git/commit/{revision}; compose it into server.ROUTES as a separate collection. Clamp limit, gate the revision path parameter on a strict hex-and-length pattern before it reaches any argv, and return the negative envelope rather than an error when there is no repository.
