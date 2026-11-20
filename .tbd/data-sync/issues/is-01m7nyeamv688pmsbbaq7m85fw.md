---
type: is
id: is-01m7nyeamv688pmsbbaq7m85fw
title: "metab TARGET --present: resolve (--dry-run --json) and hand a target to the native app"
kind: feature
status: closed
priority: 1
version: 8
spec_path: docs/project/specs/active/plan-2026-11-17-open-anything-from-cli-and-app.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/540
    at: 2026-11-20T17:01:39.211Z
labels:
  - skill
  - alpha
dependencies: []
parent_id: is-01m7nnxhaqce1g2ewec3wbaf7e
created_at: 2026-11-17T23:45:57.914Z
updated_at: 2026-11-20T19:16:00.188Z
closed_at: 2026-11-18T17:04:22.836Z
close_reason: "Done in #540 (merged e769513d9): metab --present with dry-run JSON and handoff to the app."
resolution: null
duplicate_of: null
extensions: {}
---
Alpha slice of plan #534 per the skill review: cli/present.py; --dry-run --json resolves kind/root/page/refusal with no clone and no server import (reuse classify_root_argument, selection_view_href); delivery detects the release then dev bundle id (override by flag/env), checks a capability marker in the bundle before sending a URL, open -b, reports delivered_to, confirmed:false, reason; with no app or an untakeable target reports none and starts nothing; distinct exit codes; parity row and goldens with a recording open stand-in.
