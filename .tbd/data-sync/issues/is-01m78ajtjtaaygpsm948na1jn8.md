---
type: is
id: is-01m78ajtjtaaygpsm948na1jn8
title: Setup accepts a 0.12.1 development metab that predates --exit-on-eof
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m76h3hxc44pkpkv2k8syp145
created_at: 2026-11-12T16:48:46.169Z
updated_at: 2026-11-12T17:28:24.870Z
closed_at: 2026-11-12T17:28:24.864Z
close_reason: "Fixed on #377 in 34d7a22c and 41858a3d (review D's D1-D3). Setup validates with metab --exit-on-eof --version; only an exit 2 naming the flag is followed by --version alone, after the file's trust is checked again, and reports the build as too old. Review E approves."
resolution: null
duplicate_of: null
---
Found in the end-to-end check (mb-hwxu) on 2026-11-12. After an app update, the saved runtime setup could not be decoded (FileFingerprint gained a required mode field in f58eb702), so RuntimeSettings.load() returned nil and discovery ran again. It took ~/.local/bin/metab, a uv tool install of 0.12.1.dev38, which MetabRequirement.accepts (any 0.12.1 development build counts as the minimum) but which has no --exit-on-eof. Every window then failed with click's 'No such option: --exit-on-eof' usage error, with no remedy shown. Fix: validate a runtime with 'metab --exit-on-eof --version', which an old build rejects with exit 2 and a current build answers with its version and exit 0; on that rejection, run --version alone and report the runtime as too old, so discovery passes over it and the first-run screen shows the upgrade path. The decode-as-none behavior for setups saved by unreleased builds stays as designed.
