---
type: is
id: is-01m3tem0raag7zczfs9ce90jbv
title: "Tests: golden machinery — one harness, a complete golden-update, a size check, and precise placeholders"
kind: task
status: open
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m3tefr6acvg3tg4qg87egzzb
  - type: blocks
    target: is-01m3tecqkz4nc7e17rqtpmfj2z
  - type: blocks
    target: is-01m3teckg1zyphvywvrzkwe3df
parent_id: is-01m3te95dfdnc80j5xywqje9ke
created_at: 2026-10-01T00:42:52.032Z
updated_at: 2026-10-01T00:46:59.559Z
---
Part of the test-suite review epic. Survey of a896d8fe, 2026-09-30, read-only. Area-specific golden work is in the area beads: sharding `cli-git-pin.txt` (git bead), de-duplicating the pull-request record and its `grep` slices (GitHub bead), the label-only UI blocks (Node runner bead). This bead covers the shared golden machinery and the remaining anti-patterns.

## Scope

- `tests/golden/`: 54 files, 17,373 lines at the tip (24 files, 6,058 lines on `main`): 35 tryscript files and 19 in-process `.txt` goldens.
- Drivers for the `.txt` goldens: `tests/test_cli_golden.py` plus seven `*_golden.py` files and `tests/test_serve_pin.py`, 2,466 lines for 18 tests; 1,443 of those lines (58%) precede the first test.
- Tooling: the `test` and `golden-update` Make targets, `devtools/golden_fixup.py` (120 lines, no tests), `src/metabrowser/normalize.py`.
- Recorded response fixtures that feed `cli-ui-*` goldens: six files, 5,052 lines.

## Findings

1. `make golden-update` is incomplete. It runs `GOLDEN_UPDATE=1` for `tests/test_source_kind_session.py` and `tests/test_source_freshness_session.py` only (Makefile `golden-update` target). The recordings written by `tests/test_source_ref_selector_session.py`, `tests/test_github_pull_page_session.py`, `tests/test_inert_toc.py` and `tests/test_inert_html.py` are regenerated only by a command in each docstring, so the target can rewrite a `cli-ui-*` golden from a stale recording. Rule: "Say how a generated fixture is regenerated, and from which source or schema."
2. No size guard. The golden guideline says "Don't let artifacts grow unbounded—add lint checks to warn on size thresholds." Nothing checks golden size; four goldens are 977 lines or more and one is 2,434.
3. Harness duplicated per driver. There is one shared `check_golden` (`tests/test_cli_golden.py:83-104`), but seven block renderers (`tests/test_cli_golden.py:127, 143`, `tests/test_cli_cache_acquire_golden.py:190`, `tests/test_cli_cache_recovery_golden.py:191`, `tests/test_cli_git_refresh_golden.py:124`, `tests/test_cli_github_url_golden.py:107`, `tests/test_cli_github_pull_golden.py:97`, `tests/test_serve_pin.py:175`), two `_elide_payload` implementations and three in-process runners. About 300 duplicated lines (estimate).
4. Placeholders over values the fixture could pin. `tests/golden/serve-pin-banner.txt:5` prints `Revision: <REVISION>`; the commit is unstable only because `tests/test_cache_acquire.py:62-74` omits `GIT_*_DATE`, while sibling drivers pin theirs. `<TIME>` appears 73 times in the `.txt` goldens although one seam exists (`src/metabrowser/cache/records.py:70`, `canonical_now`) and the pull driver already fixes its clock (`tests/test_cli_github_pull_golden.py:70`); the blanket placeholder hides equality that Python then re-asserts. `tests/test_cli_cache_acquire_golden.py:140-158` elides by key name at any depth, which `src/metabrowser/normalize.py:35-38` rejects. Golden anti-pattern 1: "Patterns should only match truly unstable fields."
5. Broad elisions. `tests/golden/cli-api-shell.tryscript.md:716` is `"html": "[..]"`, hiding a deterministic render; `:679` elides `version` and `:669` a whole line. The `"at": "[..]"` elisions (`cli-api-source.tryscript.md:468`, `cli-github-pull.tryscript.md:868, 896, 924`) match any string where a timestamp pattern would be precise. "Don't hide differences with overly broad placeholders; prefer precise normalization."
6. Repeated blocks. `cli-api-shell.tryscript.md:717-868` and `:886-1037` are byte-identical: a 152-line KPress asset manifest pinned twice. The prose above the first says the assets are elided; they are literal.
7. Narrow slices outside the GitHub golden. `tests/golden/cli-api-untrusted-markdown.tryscript.md:42` prints tag and attribute names only, so a `javascript:` href value would pass; `:73` is `grep -cE 'a|b'`, which answers 1 if either token survives. `tests/golden/cli-diff.tryscript.md:108` is `| head -24`. Golden anti-pattern 2.
8. Pipes hide exit status. `tests/golden/cli-github-pull.tryscript.md:960-978, 984-1001`: the prose says the command "exits 1 when it failed"; the block ends `? 0` because the status is `grep`'s. No block records that exit code.
9. Counts are not asserted. tryscript exits 1 on an empty glob (read in `node_modules`), but nothing asserts the number of files or blocks, and a file with zero blocks is skipped silently. Rule: "If the count can be asserted, assert it."
10. A stated reason is stale for CI. `docs/development.md` says acquisition sessions run in-process "because CI's Git is below the acquisition floor". The runner's Git in the tip's CI run was 2.55.0, which `acquisition_allowed` admits. Developer machines may still be below the floor.

## Proposed restructuring

1. One `tests/golden_harness.py`: block renderer, in-process runner, label normalizer in the recovery driver's style (`<STORE-A>`), a fixed clock through `canonical_now`, and a pinned git environment. Port the eight drivers to it.
2. Run every recorder from `make golden-update`, and add a check that each recorded fixture is named there.
3. Add a golden size threshold to a check in `make lint-check`, with a negative probe. Until the git bead shards `cli-git-pin.txt`, list that one file as a tracked exception naming the git bead; the exception is removed there.
4. Pin the revision and clock so `<REVISION>` and most `<TIME>` placeholders become literal; replace `[..]` on timestamps with a timestamp pattern; show the KPress asset manifest once.
5. Replace the slices in finding 7 with full or precisely scoped output, and record the real exit status for the blocks in finding 8.
6. Assert the tryscript file and block counts in the gate.
7. Re-state or correct the reason in finding 10, and decide whether an admitted-Git tryscript tier is worth having.
8. Give `devtools/golden_fixup.py` a positive and a negative test.

## Expected reduction

- Drivers: about −350 lines.
- Goldens: about −150 lines here (asset manifest), and the area beads account for the larger cuts (about −460 in the pin golden, about −740 in the pull goldens).
- No run-time change expected.

## Acceptance

- The epic's accept rule.
- `make golden-update` on a clean tree is a no-op, shown in the PR.
- The size check fails on its probe.
- Every placeholder that remains is listed with the reason the fixture cannot pin it.

## Must NOT be removed

- The Python invariants beside goldens that a transcript cannot show: `_snapshot` equality, inode reuse, "a cache hit runs no Git", `.pack` and sandbox-leak checks in `tests/test_cli_cache_recovery_golden.py`.
- The `[CWD]`, `[BUILTIN]`, `[VERSION]` and watcher elisions: truly unstable.
- The clock patch cannot reach the SIGKILL child or the live subprocess; those keep `<TIME>`.

Labelled `release:v0.12.0`: 30 of the 54 goldens are new in the stack, and findings 1 and 8 are goldens that can pass while wrong.
