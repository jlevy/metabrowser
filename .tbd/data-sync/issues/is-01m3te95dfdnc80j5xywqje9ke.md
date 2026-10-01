---
type: is
id: is-01m3te95dfdnc80j5xywqje9ke
title: "v0.12 test-suite review: maximum coverage, minimum test complexity"
kind: epic
status: open
priority: 2
version: 21
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
child_order_hints:
  - is-01m3tet2paxkc94w1fz14sd58k
  - is-01m3teat7c8bvw4b8jwwzspm1n
  - is-01m3teqnqm0pdjtjg7dsmnwzkj
  - is-01m3testfrbmdgbyag085sf4ar
  - is-01m3tem0raag7zczfs9ce90jbv
  - is-01m3tefr6acvg3tg4qg87egzzb
  - is-01m3tecqkz4nc7e17rqtpmfj2z
  - is-01m3teckg1zyphvywvrzkwe3df
  - is-01m3tenyt9e2r7rrf5rdkf5jnt
  - is-01m3tefvpqrgqe0f6hc4dw4a56
  - is-01m3tej6vemtgtxc60p3jj36hw
  - is-01m3tem2eh3jqn4dg21jsy7fkr
  - is-01m3tesntkscpn8he8rvbkj8gc
  - is-01m3tet7v3nwr9jk3cen218a7p
  - is-01m3tej64v1fg6k1xkw5qd51pd
  - is-01m3tenv5qramdxdf3e60zsfzk
  - is-01m3tekwar2fhzsmfyyby736pg
  - is-01m3v42w1atgg9yb0565vzr1mx
created_at: 2026-10-01T00:36:56.339Z
updated_at: 2026-10-01T06:57:58.810Z
---
## Goal

Give the v0.12 stack the maximum coverage of public contracts for the minimum test complexity. Remove or restructure tests that are vacuous, spurious or redundant, and prefer concise golden tests wherever they carry the same evidence. The user's request: "make sure that it has the maximum coverage but the minimum complexity of the tests. We should have any tests that are vacuous or spurious removed or restructured so that we use cleaner, more concise golden testing wherever possible."

## Why now

Over `origin/main`, the stack tip (a896d8fe, `origin/codex/v012-p4-fixes`) adds about 61k lines of tests against about 45k lines of product source, of which about 13.5k is the retired Hosted Review layer (mb-whmn).

Measured on 2026-09-30 (lines: `git grep -c ''` on each ref; run time: CI `test (3.13)` job logs, run 35634453594 for main and 36077428696 for the tip):

| Measure | main | tip |
|---|---|---|
| `tests/test_*.py` files / lines | 203 / 49,436 | 287 / 83,818 |
| test helper modules, lines | 323 | 1,839 |
| `tests/dom` JS files / lines | 84 / 33,638 | 94 / 37,949 |
| `tests/golden` files / lines | 24 / 6,058 | 54 / 17,373 |
| `tests/fixtures` files / lines | 30 / 958 | 59 / 10,236 |
| `def test_` functions | 1,899 | 2,899 |
| pytest items collected in CI | 2,186 | 3,787 |
| skipped in CI | 0 | 27 |
| pytest wall time in CI | 64.0 s | 269.9 s |
| tryscript blocks / wall time in CI | 131 / 37.7 s | 278 / 138.8 s |

Tests grew 1.7x; pytest time grew 4.2x and tryscript time 3.7x. The `test` job runs on four Python versions, and 24 of the slowest files run again in two `admitted-git` jobs.

## Method

1. Apply `tbd guidelines general-testing-rules`, `golden-testing-guidelines`, `general-tdd-guidelines`, `ci-and-gates-rules`, and the repo's own rules in `docs/e2e-testing.md` and `docs/development.md` ("CLI and Functional UI Parity").
2. Work area by area through the child beads. Each child names its scope, the surveyed findings with file:line, the rule each breaks, the restructuring, and what must stay.
3. For every test, state the contract, boundary, failure mode or failure location it adds that the rest of the suite does not. If that cannot be written, merge or remove it.
4. Prefer, in order: delete a vacuous test; collapse repeated examples into a table or one compact golden; move CLI-observable behavior from Python into a tryscript golden; move browser interaction from source-text assertions into a browserless session; keep a focused Python test only where it gives an invariant, speed or failure location the public interface cannot.
5. Line coverage is a discovery tool only. The suite has no coverage tooling today (`uv.lock` has neither `coverage` nor `pytest-cov`); the baseline child bead decides whether to add it.

## Accept rule (applies to every child)

- Every removed or merged test names, in the PR description, the independent evidence that still covers its contract (test, golden block or session, by path and line).
- Coverage of public contracts does not drop: `devtools/check_parity.py` stays green, and no route, kind, CLI mode, persisted state or failure class loses its last evidence.
- `make verify` is green.
- Test lines (Python, DOM JS, goldens, fixtures) and run time (pytest and tryscript, from the CI `test (3.13)` job) are reported before and after in each PR and totalled here when the epic closes.

## Notes

- Survey of 2026-09-30 was read-only at a896d8fe. Two PRs above #244 were in progress and are not covered.
- Local `pytest --durations` was not run (machine load stayed above 40); the timings come from CI log timestamps at per-file resolution.

## Children and expected reductions

Estimates from the survey; some overlap, so they do not add exactly. Order: baseline first, then the release-labelled beads, then the rest.

| Bead | Area | Expected reduction | Release label |
|---|---|---|---|
| mb-jqbg | Baseline and reporting | none (adds about 100 lines of tooling) | yes |
| mb-haxx | Hosted Review and oracle tests; surviving contract-layer tests | −4,579 test lines, −1,703 fixture lines, about −19 s; then about −590 to −1,250 | yes (after mb-whmn) |
| mb-onzb | Isolation and determinism | about −150 lines; removes order- and load-dependent failures | yes |
| mb-cxsk | Skips, tiers, timeouts | about −350 lines; up to about 110 s in three matrix jobs if the user agrees | yes |
| mb-99pm | Golden machinery | drivers about −350, goldens about −150 | yes |
| mb-79t3 | Git pin and source suite | tests about −1,050; pin golden sharded | yes (after mb-99pm) |
| mb-738k | GitHub pull-request suite | tests about −325, fixtures about −900, goldens about −555 | yes (after mb-99pm) |
| mb-sqlv | Cache suite | tests about −750, fixtures −382 to −740, about −14 s | yes (after mb-99pm) |
| mb-weez | Tooling tests and explorations | tests about −900 | yes, for the explorations steps |
| mb-aj7y | Source-shape: delete and move to a check | tests about −1,350 | no |
| mb-0u3p | Node runner; goldens own session output | Python about −2,000, JS about −435 | no |
| mb-fkt5 | CLI tests to tryscript | tests about −900, goldens about +200 | no |
| mb-an7c | Shared fixtures | about −650 lines; run time to be measured | no (after mb-onzb) |
| mb-19t8 | Guidance: ratchet checks and one rule | none | no |
| mb-syj4 | Source-shape: convert to sessions | Python about −2,300, JS about +500, goldens about +400 | no (after mb-aj7y) |
| mb-888s | Inventory and route suites | tests about −1,150, goldens about +90 | no |
| mb-x6qa | Shared DOM shim | JS about −1,150 to −1,450 | no (after mb-0u3p) |

Rough total if all land: about 15k to 17k of the 85.7k lines of Python tests and helpers, about 3k of the 10.2k fixture lines, about 1.2k to 1.5k net of the 37.9k lines of DOM JS. Golden lines stay roughly flat: repeated blocks go and new coverage replaces Python tests.

## Notes

- Survey of 2026-09-30 was read-only at a896d8fe. Two PRs above #244 were in progress and are not covered.
- Local `pytest --durations` was not run (machine load stayed above 40); the timings come from CI log timestamps at per-file resolution.
