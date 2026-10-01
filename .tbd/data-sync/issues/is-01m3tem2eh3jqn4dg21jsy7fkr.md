---
type: is
id: is-01m3tem2eh3jqn4dg21jsy7fkr
title: "Tests: replace Python CLI tests that a tryscript golden already covers, and move the uncovered ones into goldens"
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels: []
dependencies: []
parent_id: is-01m3te95dfdnc80j5xywqje9ke
created_at: 2026-10-01T00:42:53.774Z
updated_at: 2026-10-01T00:42:53.774Z
---
Part of the test-suite review epic. Survey of a896d8fe, 2026-09-30, read-only. Every test in the seven files below was read and classified.

## Scope

Python tests of CLI behavior, 116 tests in 7 files:

| File | Lines | Remove | Move to golden | Keep |
|---|---|---|---|---|
| `tests/test_cli_main.py` | 1,255 | 15 | 8 | 32 |
| `tests/test_cli_show_mode.py` | 309 | 13 | 1 | 3 |
| `tests/test_cli_api_mode.py` | 101 | 6 | 1 | 0 |
| `tests/test_plugins_cli.py` | 202 | 6 | 5 | 0 |
| `tests/test_cli_no_serve_surface.py` | 87 | 6 | 1 | 1 |
| `tests/test_remote_cli.py` | 408 | 0 | 1 | 10 |
| `tests/test_cli_acquire_error_modes.py` | 259 | 0 | 0 | 7 |

Also `tests/test_cli_acquire.py` (506 lines, 24 tests): about 11 duplicate the in-process goldens. Most of these files are on `main`; `test_cli_no_serve_surface.py` and the two acquire files are new.

## Findings

1. 46 Python tests duplicate a golden block. Rule: "For a CLI, prefer golden fixtures that invoke the built executable and record arguments, stdout, stderr, exit status, and relevant files over language-coupled unit or integration tests when both approaches cover the same contracts."
   - `tests/test_cli_main.py:75` is `tests/golden/cli-surface.tryscript.md:24-237`; `:113, 125, 165, 172, 195` are `cli-errors.tryscript.md:143, 23, 59, 71, 131`; `:350` and `:872` are `cli-errors.tryscript.md:191-194`; `:683` is `cli-untrusted.tryscript.md:39-68`; `:1250` is `cli-plugins.tryscript.md:20-34` and also `tests/test_plugins_cli.py:20`.
   - `tests/test_cli_show_mode.py:87-236` (13 tests) is `cli-show.tryscript.md:44-313` and `cli-api-git.tryscript.md:390-435`.
   - `tests/test_cli_api_mode.py:21-82` (6 tests) is `cli-api.tryscript.md:29-280`.
   - `tests/test_plugins_cli.py:20, 30, 67, 75, 104, 112` is `cli-plugins.tryscript.md:20-376`.
   - `tests/test_cli_no_serve_surface.py:21, 27, 35, 51, 76, 82` is `cli-surface.tryscript.md:24`, `cli-errors.tryscript.md:83, 23, 207, 215` and `cli-cache-url-grammar.tryscript.md:108`.
2. 17 tests are CLI-observable with no golden. Move them, do not delete: `tests/test_plugins_cli.py:43, 88, 96, 124, 162` (a `--plugins-dir` fixture), `tests/test_cli_main.py:1107, 1129, 1200, 1217, 1233` (`--path` refusals), `:908` (ssh "not served yet"), `tests/test_cli_show_mode.py:120`, `tests/test_cli_api_mode.py:85`.
3. The same contract at three or four layers:
   - Below-floor Git refused with the home untouched: `tests/test_cache_acquire.py:497, 516, 532`; `tests/test_cli_acquire.py:347, 365`; `tests/test_cli_acquire_error_modes.py:143` (12 cases); `tests/golden/cli-cache-unsupported-git.txt:6, 11`.
   - Read-only home hit: `tests/test_cache_acquire.py:589`; `tests/test_cli_acquire.py:401`; `cli-cache-readonly-hit.txt`; `cli-cache-readonly-miss.txt`.
   - Pin refusal `selection_not_found`: `tests/test_source_refresh.py:410-426`; `cli-api-source.tryscript.md:202-229`; `cli-git-refresh.txt:168-178`.
   - Git failures path-free: `tests/test_cli_acquire.py:454-487` is the "no-serve" row of `tests/test_cli_acquire_error_modes.py:78-111`.
   - ssh closed: `tests/test_cache_acquire.py:490`; `tests/test_cli_main.py:908`; `tests/test_cli_acquire.py:266`; `cli-errors.tryscript.md:207-217`.
4. Source-shape. `tests/test_cli_main.py:616-636, 639-651` read `serve.py` and assert string-index order; `:639` is covered behaviorally by `:654-667`.
5. Call assertions and a constant echo. `tests/test_cli_main.py:487-509, 511-535, 784-796` patch `os._exit` or the server and assert the call, while the real-subprocess test at `:829-839` proves exit 130 and one "Stopping". `:533` (`b"Stopping" in _STOPPING_NOTICE`) echoes a constant. Rule: "Assert Transferred Data, Not Merely That a Mock Was Called."
6. `tests/test_cli_main.py:820` sleeps a gap and `:862` loops three gaps, each a full server start.
7. tryscript cost. Each `metab` block costs about 0.5 s in CI (263 invocations, 138.8 s). Adding blocks is not free; `cli-cache-url-grammar.tryscript.md` (43 blocks, 20.5 s) and `cli-github-urls.tryscript.md` (34 blocks, 16.4 s) are trimmed in the cache and GitHub beads.

## Proposed restructuring

1. Delete the 46 tests in finding 1, naming the golden block for each.
2. Add about 17 blocks for finding 2: a new `cli-plugins-dir.tryscript.md`, plus additions to `cli-errors`, `cli-show` and `cli-api`.
3. Remove the roughly 11 golden-duplicated tests from `tests/test_cli_acquire.py`, keeping one layer per contract in finding 3.
4. Convert `tests/test_cli_main.py:616` to a behavioral test, delete `:639`, and replace the patched-exit tests with the subprocess evidence that exists.

## Expected reduction

- Tests: about −900 lines.
- Goldens: about +200 lines.
- Run time: about +8 s per job for 17 new `metab` blocks, less what the deleted in-process tests cost (`tests/test_cli_main.py` is 7.4 s today).

## Acceptance

- The epic's accept rule.
- Each deleted test names its golden block by path and line in the PR.
- The net tryscript time is reported; if it rises by more than the Python time saved, say so and justify it.

## Must NOT be removed

- Signal and subprocess tests: `tests/test_cli_main.py:228-347, 538-613, 829-869`.
- dotenv and trust security tests: `:729-781, 978-1050`.
- The two option matrices `:134-155, 205-222` (ten or more fast rows against two golden rows) and `:96` (the version golden elides the value).
- `tests/test_cli_show_mode.py:240-309` (undecodable bytes).
- All of `tests/test_cli_acquire_error_modes.py` (failure injection) and the mock-ssh tests in `tests/test_remote_cli.py`.

No release label: five of the seven files pre-date the stack, and the duplication is cost, not a correctness risk.
