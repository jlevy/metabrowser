---
type: is
id: is-01m3teckg1zyphvywvrzkwe3df
title: "Tests: cache suite — bind or drop self-checking contract fixtures, stop restating goldens in Python, and table-drive the repeats"
kind: task
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m3te95dfdnc80j5xywqje9ke
hold: null
hold_until: null
created_at: 2026-10-01T00:38:49.086Z
updated_at: 2026-10-01T10:30:15.944Z
started_at: 2026-10-01T10:30:15.934Z
---
Part of the test-suite review epic. Survey of a896d8fe, 2026-09-30, read-only. All files are new since `origin/main`.

## Scope

- `tests/test_cache_*.py`: 14 files, 7,925 lines, 530 collected cases, 29.9 s in CI. Largest: permissions (1,695), update (1,012), layout (896), routes (806), acquire (724), locks (552).
- `tests/test_repository_cache_contract_fixtures.py` (471) and `tests/fixtures/repository-cache/` (four JSON fixtures, 1,921 lines; four `*.schema.json`, 382 lines).
- Goldens: `tests/golden/cli-api-cache.tryscript.md` (418, 11 commands), `cli-cache-url-grammar.tryscript.md` (330, 43 commands, 20.5 s in CI), ten `cli-cache-*.txt` (1,007) driven by `tests/test_cli_cache_acquire_golden.py` (355) and `tests/test_cli_cache_recovery_golden.py` (576).

## Findings

1. Fixture tested against itself (vacuous). `tests/test_repository_cache_contract_fixtures.py:384-427, 430-458, 461-471` check state-machine well-formedness, scenario replay and crash coverage by reading only `state-machines.json` with a transition walker written in the test; no production code runs. `:52-55` validates each fixture against a schema nothing else uses. Rule: "A test is vacuous when it verifies only facts established by its own setup rather than behavior supplied by the program." Only `startup_sweep` (`tests/test_cache_reclaim.py:46-69, 135-151`) and one lock set (`tests/test_cache_publish.py:164-202`) are bound to production; `store_refresh` (`state-machines.json:445-634` and 8 scenarios) is replayed against nothing.
2. Constant echo. `tests/test_cache_urls.py:54-55` (`DEFAULT_PORTS == {...}`) and `tests/test_cache_locks.py:538-552` (literal `LockKind` values and ranks) repeat `tests/test_repository_cache_contract_fixtures.py:69-70, 303-308`.
3. URL grammar asserted at four layers: fixture replay (`tests/test_repository_cache_contract_fixtures.py:66-78`, 91 cases), `tests/test_cache_urls.py:18-51`, the 43-command tryscript (32 of them the one-line `Error: invalid ROOT (<reason>)` shape, `:124-321`), and `tests/test_cli_main.py:882-925`. Rule: "Keep overlapping execution when tests protect different public interfaces"; the CLI layer adds only the rendering.
4. Route tests restate the golden. Nine tests in `tests/test_cache_routes.py` (`:115-130, 176-183, 219-226, 252-255, 295-299, 313-342, 354-383, 389-398, 420-428`) re-assert as dict literals what `tests/golden/cli-api-cache.tryscript.md:33-418` records in full. Golden guideline: focused assertions beside a golden are fine; a second copy of its content is not.
5. Route data semantics with no golden. `tests/test_cache_routes.py:467-700` (14 tests: damaged, dangling, mismatched, not-private, unrecognized entries). AGENTS.md: such semantics "belong to a route or model reached through `metab` and a nontrivial golden."
6. Acquire tests duplicate the recovery goldens. `tests/test_cache_acquire.py:497-545, 549` are in `cli-cache-unsupported-git.txt`; `:589, 609` in `cli-cache-readonly-miss.txt`; `:629` in `cli-cache-repair-guidance.txt`.
7. Golden duplicates golden. `cli-cache-readonly-hit.txt` (16 lines) is a strict prefix of `cli-cache-readonly-miss.txt`; `cli-cache-recover.txt` is subsumed by `cli-cache-interrupt-store.txt`. Two elision implementations exist (`tests/test_cli_cache_acquire_golden.py:140-202` and `tests/test_cli_cache_recovery_golden.py:122-237`); in `cli-cache-acquire.txt` the alias `store_id` and the store `id` both print `<STORE_ID>`, so the golden cannot show they are equal ("Don't hide differences with overly broad placeholders").
8. Repeated tables. `is_valid_ref_name` is tabled twice: `tests/test_cache_update.py:856-889` (25 cases) and `tests/test_cache_resolve.py:45-84` (34 cases). About 40 of the 70 permission tests share one shape (arrange hostile state, `_refusal(call)`, assert violation and location, assert nothing changed).
9. Fixture provenance. The JSON fixtures are hand-authored with no generator and no stated regeneration command; `source-identity.json` holds 16 computed digests. Rule: "Say how a generated fixture is regenerated, and from which source or schema."

## Proposed restructuring

1. Contract fixtures: delete `tests/test_cache_urls.py:18-55`, `tests/test_cache_locks.py:538-552`, the schema test and the four schema files. For the unbound state machines, either bind them to production (emit the machine events from acquire and update, as reclaim does) or move those sections to the architecture document; do not keep a fixture that only tests itself. Add a provenance note to each fixture.
2. Cut `cli-cache-url-grammar.tryscript.md` from 43 commands to about 12 (one per outcome class, plus a credential case and an option-like case); the 91-case fixture replay stays the authority.
3. Routes: strip the restated dicts; add a `build_damaged_home` to `tests/cache_home_fixture.py` and record the 14 damage cases in the cache golden.
4. Acquire: collapse `:497-629` to one parametrized test of the typed exceptions; port the acquire-golden sessions onto the recovery `_Session`; drop `cli-cache-readonly-hit.txt` and `cli-cache-recover.txt`.
5. One ref-name table in `tests/test_cache_resolve.py`; a table over the declarative permission refusals.

## Expected reduction

- Tests: about −750 lines (fixtures/urls/locks −150, routes −270, acquire and golden drivers −190, permissions and ref-name tables −200 to −300 taken at the low end).
- Goldens: about −270 lines removed and about +150 added for the damage cases.
- Fixtures: −382 (schemas), or about −740 if the unbound machines move to docs.
- Run time: about −14 s per job from the URL-grammar golden (31 fewer `metab` processes at about 0.47 s each).

## Acceptance

- The epic's accept rule.
- Each deleted route or acquire test names the golden block that carries its contract.
- The damage-case golden shows full envelopes, with no `grep`/`jq` slices.

## Must NOT be removed

- `tests/test_cache_permissions.py` as a whole: the only evidence for owner-only modes, TOCTOU swaps, hard links, FIFOs and ACLs. No CLI exposes these, so a golden cannot replace them. Restructure only.
- Crash safety: `tests/test_cache_atomic.py:123, 253, 161-203, 356-384`.
- Lock exclusion: `tests/test_cache_locks.py:155-195, 287, 352-381, 452-535`; all of `tests/test_cache_async_locks.py`.
- `tests/test_cache_reclaim.py` (`:135` is the only production-bound machine replay), `tests/test_cache_publish.py:179-224`, `tests/test_cache_layout.py:428-523, 604, 698-896`, `tests/test_cache_update.py:360, 454, 684, 783`, `tests/test_cache_origin.py:90, 179`, `tests/test_cache_records.py:255-295, 307-345`.
- The production replays in `tests/test_repository_cache_contract_fixtures.py:66, 132-221, 238, 311-377`.
- Goldens: interrupt-store, interrupt-alias, unsupported-git, fetch-failures, repair-guidance, readonly-miss, acquire, orphan-kept.

Labelled `release:v0.12.0`: these files are all new in the stack, so trimming them before landing avoids landing and then deleting them.
