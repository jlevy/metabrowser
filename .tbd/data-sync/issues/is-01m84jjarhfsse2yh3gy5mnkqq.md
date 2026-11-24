---
type: is
id: is-01m84jjarhfsse2yh3gy5mnkqq
title: "A served test checkout's origin store fetches the real origin: no seam points a subprocess server at a local origin"
kind: bug
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
delegate: claude-code@spud10
labels:
  - ci
  - tests
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
hold: null
hold_until: null
created_at: 2026-11-23T16:07:02.661Z
updated_at: 2026-11-23T20:48:55.552Z
started_at: 2026-11-23T16:10:58.954Z
closed_at: 2026-11-23T17:29:17.705Z
close_reason: "Fixed in #762 (6fd2b2092): METABROWSER_ORIGIN_STORE=0 (ORIGIN_STORE_ENV in checkout_store.py) keeps the serve command from keeping a store of a folder's origin; tests/conftest.py sets it, so subprocess servers no longer fetch https://github.com/octo/demo. The three named Chrome tests pass locally, with the gh guard at 1 call from test_ref_selector_pulls_chrome, the count before #740."
resolution: null
duplicate_of: null
---
Since the folder origin store (#740, merged in the update-cadence stack at b68cc9571), a metab server started on a checkout whose origin is an https address the grammar accepts acquires a store of that origin when it starts (CheckoutStore.open -> request_acquisition). A Chrome test's server is a subprocess, so monkeypatching acquire.remote_url_for does not reach it, and the acquisition policy's Git environment ignores url.insteadOf, so no test can point it at a local file:// origin. The tests' servers therefore try the real https://github.com/octo/demo, from tests that say nothing is fetched.

Evidence:
- tests/test_ref_selector_pulls_chrome.py (verified). Locally, after the session, GET /api/source/refs?kind=remote on its server answered origin state absent, reason not_found_or_private, with the provider's gh hint in detail. The fixture (_stage_and_publish_source) publishes only a source record, so cached_source finds no store and the server acquires one. CI's gh guard for this test went from 1 gh call (main 72b7173b0, run 45157838585, chrome 3.13 4/4) to 2 (run 45187239621; and 45206569437 at 339567248): the second is provider_credential_hint after the refusal. The test's docstring says: nothing is fetched from it.
- tests/test_view_header_chrome.py (probable, not verified): serves a checkout with origin https://github.com/octo/demo.git through metab. Its gh guard count did not change, which a network_error refusal (no hint) or a different timing would explain.
- tests/test_root_kind_mark_chrome.py (possible, not verified): origin git@github.com:Octo/Demo.git, which a provider that reduces GitHub SSH to HTTPS would make fetchable.
- Any other test or golden that starts a metab server (not --api or --show) on a checkout with a GitHub origin.

Consequences: network access and a gh call in tests that should be hermetic; the result depends on whether the runner reaches github.com and how it answers; the server's extra start-up work changes page timing (it is the inferred trigger of the focus race fixed as mb-nbyu). Fix belongs in the server-side PR: a seam that points a subprocess server's acquisition at a local origin, or a test fixture that publishes a store so nothing is acquired. Not fixed in #756.
