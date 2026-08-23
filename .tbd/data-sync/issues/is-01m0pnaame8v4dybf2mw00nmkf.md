---
type: is
id: is-01m0pnaame8v4dybf2mw00nmkf
title: Verify two builds under comparison are actually different builds
kind: task
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m0pn7vkfkd7tfzt7r331jkp8
created_at: 2026-08-23T06:35:51.309Z
updated_at: 2026-08-23T07:24:20.001Z
---
WHAT HAPPENED. A side-by-side comparison ran with both builds reporting version 0.6.0. The candidate was a source checkout thirty commits past its tag, but `importlib.metadata` reports the version recorded at install time, so the number never moved. Every timing collected in that round was attributed to a build whose identity was unverified.

THE FIX THAT LANDED, in #71: `build_version.py` annotates a displayed version with the repository state -- distance past the tag, the commit, and whether the tree is dirty -- so the candidate now says `0.6.1.dev27+9084e6b (+30 commits, 8d78c29)`. Note what that string admits: the package version is stale at dev27 while the actual commit is 8d78c29. The annotation is the only part that is true.

WHAT IS STILL MISSING, which is why this is open. The harness prints both versions and does not check them. It should refuse to run when the two identify as the same build, because that is never a comparison anyone wants and it is not detectable from the results afterwards. The check is two lines and it closes the hole that #71 only made visible.

RELATED HAZARD, worth knowing when reading old measurements: any timing recorded before #71 has an unverifiable candidate identity. Treat pre-#71 comparison numbers as provisional.

## Notes

FIXED in #73, and the fix caught a second case the bead did not anticipate.

The harness refuses to run when the two builds report the same version. It also resolves each build to an absolute path first and refuses when both resolve to the SAME BINARY -- which is a distinct failure, since two paths can differ while naming one file.

The second guard earned itself immediately. Run under `uv run`, a bare `metab` resolves to the project venv before the globally installed release, so "baseline" silently becomes a second candidate. That happened while smoke-testing the harness. The resolved paths are now printed in the output, so a reader can see which binary each name meant.
