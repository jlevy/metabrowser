---
type: is
id: is-01m6hkbt0t0qhvrhxhktgefe38
title: Load PR catalog progressively with accurate repository totals and lazy details
kind: feature
status: in_progress
priority: 1
version: 22
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6f39t9zax1nbajkkasya6st
child_order_hints:
  - is-01m6hkgedpcnemk1d6x6tqrwen
  - is-01m6hkgesnhsg9eg7wy0pc1qvp
  - is-01m6hkgf5ksmp2zhha4qa5ak97
  - is-01m6hkgfhcm5wmwkm6ypfg74hx
  - is-01m6hknzgxphza4kbk01qdxjka
  - is-01m6hn9qa613jm4353kpgse5zw
  - is-01m6hn9r6c5ky1jek345fd78mz
  - is-01m6hnp2j641tnmwmw0ep18t4r
  - is-01m6hp3t5dhsp43qbz15j8k31h
  - is-01m6hp53m3z5s1a4y147rcdrk2
  - is-01m6hpa99cxdtgg3w4zk75qe25
  - is-01m6hpbyskz9sedf0bkt2t18e9
  - is-01m6hpdkmmd0t8paqm4q5gxy0c
  - is-01m6hpk8g024g79y02he6x1srw
  - is-01m6hr8f0x7hr7mhchrtx1sqb7
  - is-01m6hrdycpqxatz8424yb9p6mv
  - is-01m6hryve021ndx04tt967a6a9
hold: null
hold_until: null
created_at: 2026-11-03T20:59:41.464Z
updated_at: 2026-11-03T23:14:00.548Z
started_at: 2026-11-03T21:00:05.436Z
---
Owner requests incremental/resumable automatic prefetch of the lightweight catalog for all repository PRs, with exact repository/filter totals. Initially show up to500 and expand the display with Fetch more. Fetch full PR description/conversation/reviews/checks only on demand or a small nearby prefetch window; derive diffs from fetched Git objects, audit actual payload sizes and avoid repeated full diff transfers. Filters Open | Closed | All, defaultOpen. Bold numeric status with repository name and Showing last500 when partial. Align Conversation/Files changed tabs with the content column at wide and narrow widths. Preserve cache-only GETs, account/rate/fair scheduling, keyboard/history/visibility ownership and main/linked checkout vsmanaged URL workflows. No compatibility aliases; forward-only childPR above288; no merge.

## Notes

2026-11-03: All requested code is committed in three forward-only local layers above #288: catalog 81f082d8, setup/session guidance 8a62f7ce, and performance a78ad4c5. No branch push, new PR or owner merge yet. Final normal make verify is running at a78ad4c5; earlier interrupted runs are retained and not counted as completed gates. An npm-generated dependency directory was moved back onto external scratch and its required symlink restored before retrying the unchanged gate.

The catalog has exact provider totals, lightweight GraphQL pages, private indexed SQLite windows, resumable background backfill/deltas, Open default, first 500 displayed, Fetch more, bounded DOM and aligned PR tabs. Eight original findings were corrected and independently rechecked. The 12 Chrome runs (three each at 100/500/1000/5000 rows) cover seeded-cache rendering at catalog81f082d8 only; they are not cold-ingestion or final-tip/network latency claims. Public payload samples measured 40–47x smaller metadata responses; no latency speedup claimed.

New owner requests are tracked under mb-yto3 (dependencies/setup; children mb-qfnr and mb-asz3) and mb-8yo5 (performance/session review; children mb-xa7e and mb-xkdr). Missing/signed-out gh, no-tool local browsing and cache retention were audited. Setup uses standard installation/login, official links and existing keychain credentials without mandatory GH_TOKEN, wrappers or a new installer. Runtime copy passed 280 affected tests; docs and fixed anchors were independently reviewed. The existing server session now records ordered provider calls and zero calls for cached use.

Catalog jobs now do one initial account check and validate each GraphQL page viewer. The deliberate response-reader contract and stale-publication/account-switch controls passed independent review, 86 focused tests and two golden cases; the former stricter second-snapshot proof remains preserved separately. PR decoding/rendering/DOM readiness use existing finite profiler labels; 15 lifecycle/page/panel tests and one profiler test passed. Root independently reviewed the changes and committed-byte reconciliation is clean. The concise QA session separates cold metadata, warm revisit/restart and one incremental revalidation.

Remaining delivery gates: final full verify; exact-wheel eight public live tests, primary/dependency Chrome acceptance and a standard cold/warm/revalidation diagnostic; normal atomic push with quality hook; three chained PRs appended to native stack286, published reviews and current CI; global CLI replacement and detached owner-server restarts; final bead closure and issues-only sync. Keep owner-merge parents and low followups mb-0cr3/mb-dpvu open. Never merge or rewrite history; never name the private test repository publicly.
