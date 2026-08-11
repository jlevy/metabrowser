---
type: is
id: is-01kxmqafgjkg9mjp17e4tbh1bh
title: Expose a stable Python sidekick API for external plugins
kind: task
status: closed
priority: 1
version: 4
labels: []
dependencies: []
created_at: 2026-07-16T05:45:19.122Z
updated_at: 2026-07-16T05:59:16.506Z
closed_at: 2026-07-16T05:59:16.505Z
close_reason: null
---
Publish and document the safe path, transparent compression, log detection, root lifecycle, and generic chart projection helpers required by installed Python data-hook plugins. Cover the contract with tests so trading-owned Metaproc plugins do not import MetaBrowser internals.

## Notes

Added documented public sidekick facade and root exports for root-bounded path resolution, ArtifactPath transparent compression, log detection/registration, root lifecycle callbacks, and cached agent charts. Added root-restoring tests. Full suite 676 passed; lint, types, Flowmark, package policy, and public-hygiene gates pass.
