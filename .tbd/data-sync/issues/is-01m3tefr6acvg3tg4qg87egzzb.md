---
type: is
id: is-01m3tefr6acvg3tg4qg87egzzb
title: "Tests: git pin and source suite — shard the 2,434-line pin golden and drop the route tests it already carries"
kind: task
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m3te95dfdnc80j5xywqje9ke
hold: null
hold_until: null
created_at: 2026-10-01T00:40:32.184Z
updated_at: 2026-10-01T15:52:20.606Z
started_at: 2026-10-01T10:30:09.267Z
closed_at: 2026-10-01T15:52:20.594Z
close_reason: "PR #257: the 2,434-line pin golden is six shards (largest 622 lines; 32 of 35 old blocks byte-identical, 3 after expanding one repeat marker), the oversized allowlist is empty, and the area's tests went 8,674 -> 7,913 lines. Independent review restored three READ_POLICY assertions and 17 safety-boundary checks no test caught before (hook-exported GIT_DIR, SSH_ASKPASS, stdin, umask, symlink target and hop budget, size gate boundary, /raw no-store). On the merged tip 373b59a9: 83 of 83 of the author's mutants and 57 of 61 of the reviewer's are caught (C01, C02, R04 equivalent; T11 is the uncalled method, mb-snpr); full local gate and CI green; make golden-update is a no-op."
resolution: null
duplicate_of: null
---
Part of the test-suite review epic. Survey of a896d8fe, 2026-09-30, read-only. Shared repository fixtures and helper duplication for this area are in the shared-fixtures bead; session isolation is in the isolation bead.

## Scope

- New in the stack: `tests/test_git_revision_content_routes.py` (2,024 lines, 33 tests), `test_git_tree_source.py` (848), `test_git_pin_scaling.py` (593), `test_git_blob_windows.py` (379), `test_git_process.py` (248), `test_git_process_group.py` (236), `test_git_revision_routes.py` (235), `test_git_store_read_policy.py` (212), `test_git_pin_failures.py` (146), `test_source_refresh.py` (911), `test_source_refs.py` (332), `test_serve_pin.py` (657), `test_cli_git_pin_show_selection.py` (130).
- Goldens: `tests/golden/cli-git-pin.txt` (2,434 lines, one test, driven by `tests/test_cli_git_pin_golden.py`, 454), `cli-git-refresh.txt` (289), `cli-api-source.tryscript.md` (477).
- Area cost in CI: git/source/acquire tests take 70.1 s of the 269.9 s pytest run.

## Findings

1. Oversized golden. `cli-git-pin.txt` is 2,434 lines in one file from one test: 35 command blocks (8 `--show`, 4 index/status, 4 `/api/tree` at 1,055 lines, rollup 514, catalog 93, 13 file/plugin, refusals). Three of the four tree blocks end in a byte-identical 158-line tally tail. Golden guideline: "small enough to manually review in PRs ... e.g. <2000 lines" and "Prefer many small artifacts (shard by scenario/phase) over monolithic traces." Its normalization is precise (`<ORIGIN>`, `<TIME>` only) and it has no narrow slices.
2. The driver re-asserts the golden. `tests/test_cli_git_pin_golden.py:315-406` repeats about 90 lines of golden content as Python asserts; the guideline allows "targeted assertions for critical invariants", not a second copy.
3. Route tests repeat the pin golden. Both layers drive the same in-process ASGI app, so they are not independent. Fully shown by the golden: `tests/test_git_revision_content_routes.py:1651-1699` (golden `:69-166`), `:1702-1761` (`:194-364`), `:612-642` (`:1763-1855`), `:462-511` (`:1856-1900, 1997-2041`), `:397-459` (`:365-1017`). Partly shown, keep only the rows the golden lacks: `:258-394, 514-580, 1416-1463, 1466-1522`. Repetition inside the file: `status_code == 200` 90 times, `str(store) not in` 39, `"mtime" not in` 26. Rule: "If that statement cannot be written, merge or remove the test."
4. Stated reason no longer holds. `tests/test_cli_git_pin_golden.py:3-8` says a successful `--api` on a pin cannot be a tryscript; `tests/golden/cli-api-source.tryscript.md:9-14` does it by pre-acquiring with `tests/source_mirror_fixture.py`. Rule: prefer language-neutral goldens "when both approaches cover the same contracts."
5. Duplicate policy tests. `tests/test_git_store_read_policy.py:48-70` equals the `STORE_READ_POLICY` iteration of `tests/test_git_process.py:101-123`; `:36-45` is a field echo of `src/metabrowser/git/process.py:156-166`; `tests/test_git_process.py:40-53` is a subset of `:101-123`.
6. Same failure tested one layer up and down. `tests/test_git_tree_source.py:637-674` (LFS), `:677-717` (missing blob), `:316-345` (oversize) repeat `tests/test_git_revision_content_routes.py:1764-1801, 1804-1850, 645-742`, which read through the same source.
7. Vacuous. `tests/test_git_blob_windows.py:308-310` asserts the module's own constants exceed the ceiling; `tests/test_git_pin_failures.py:76-77` echoes a default message; `tests/test_git_api.py:779-783` is `isinstance(out, bytes)`.
8. Parametrized cases that hit one branch. `tests/test_serve_pin.py:490-508` (4 cases) and `tests/test_git_revision_content_routes.py:1952` (2) all hit a refusal that fires before the path is read (`src/metabrowser/git/content_routes.py:1685-1686`); each serve_pin case builds a fresh origin and acquisition. `tests/test_serve_pin.py:214-236` (7 cases) builds an origin per case to check one printed address. `tests/test_git_pin_scaling.py:58-106, 177-218, 221-261` are single-threshold versions of `:455-476, 519-537, 571-593`.
9. CLI behavior asserted in Python where a golden shows it. `tests/test_source_refresh.py:360-384` (in `cli-git-refresh.txt:1-107`); `tests/test_source_refs.py:113, 138, 155, 171, 187, 214` (in `cli-api-source.tryscript.md:238-410`); `tests/test_cli_git_pin_show_selection.py` (4 tests) could be `--show` rows in the pin golden.
10. Shell-text assertions: `tests/test_source_refresh.py:651-660, 735`, `tests/test_source_refs.py:300-307`, `tests/test_serve_pin.py:441-449`.

## Proposed restructuring

1. Shard `cli-git-pin.txt` by scenario (show / index and status / tree / rollup and catalog / file and plugin / refusals), each under about 700 lines; print the shared tally tail once.
2. Add the missing refusal rows (filesystem-spelling 404s, `/raw`, gitlink refusals, error codes) to `api_refusals` in `tests/test_cli_git_pin_golden.py:301`, then delete or trim the route tests in finding 3 and cut the driver's Python re-assertions to 5–10 invariants.
3. Decide whether the pin sessions move to tryscript now that pre-acquisition works there (finding 4); if not, record the reason that still holds.
4. Apply findings 5–10: delete duplicates, fold single-threshold scaling tests into the growth tests, one case per trust profile, one banner transcript.

## Expected reduction

- Tests: about −750 lines (steps 1–2) and about −300 (step 4).
- Goldens: +150 to +250 lines for the added rows, but no file over 700 lines.

## Acceptance

- The epic's accept rule.
- No golden in `tests/golden/` exceeds the size threshold set by the golden-hygiene bead.
- Each removed route test names the golden block that carries its envelope.

## Must NOT be removed

- `tests/test_git_process_group.py` (helper kill on timeout, cancel and spawn window).
- `tests/test_acquire_stall_and_hangup.py`, `tests/test_refresh_signals.py` (real signals against the real `metab`).
- `tests/test_git_store_read_policy.py:81-164` (no-lazy-fetch seam), `tests/test_git_process.py:65-155` (environment isolation with real Git).
- `tests/test_git_full_clone_acceptance.py`, `tests/test_git_revision_open.py`, `tests/test_admitted_git_gate.py`.
- `tests/test_serve_pin.py:280-332` (startup-failure exits) and `:580-657` (isolation sweep).
- In `tests/test_git_revision_content_routes.py`: `:1058-1100` (symlink oracle), `:1988-2024` (PATH_MAX bound), `:1764, 1804` (LFS and `object_unavailable`), `:1899-1985` (raw sandbox), `:1525` (parse off the event loop).
- The scaling growth tests, `tests/test_git_pin_failures.py:80-146`, `tests/test_source_refresh.py:562-645, 727-797`.

Labelled `release:v0.12.0`: the files are new in the stack and the 2,434-line golden is the largest unreviewable artifact it adds.
