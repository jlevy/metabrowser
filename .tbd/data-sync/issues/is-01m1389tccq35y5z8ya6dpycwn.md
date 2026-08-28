---
type: is
id: is-01m1389tccq35y5z8ya6dpycwn
title: "Git status goldens: dirty-tree states and honest truncation"
kind: task
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-28-cli-first-delivery-map.md
labels: []
dependencies: []
parent_id: is-01m10z5hmf2m2tndf00k0jznx8
created_at: 2026-08-28T03:58:30.794Z
updated_at: 2026-08-28T03:58:30.794Z
---
cli-git-status.tryscript.md covers conflicts, staged, unstaged, untracked, renames, an unborn HEAD, binary files, and submodules against a deterministically built fixture repository. cli-git-status-bounds.tryscript.md proves truncation is reported rather than silent. Both run through metab --api '/api/git/status', so they prove the wire and not only the library. Fixture repos use pinned GIT_AUTHOR_DATE/GIT_COMMITTER_DATE and identity so revisions are stable and asserted literally.
