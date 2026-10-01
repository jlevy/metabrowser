---
type: is
id: is-01m3tecqkz4nc7e17rqtpmfj2z
title: "Tests: GitHub pull-request suite — one copy of each record, no grep slices, and drop tests the goldens already carry"
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
created_at: 2026-10-01T00:38:53.293Z
updated_at: 2026-10-01T14:41:41.496Z
started_at: 2026-10-01T10:30:12.343Z
closed_at: 2026-10-01T14:41:41.495Z
close_reason: "PR #258: pull-request recording 2,203 -> 1,370 lines (off the oversized allowlist), four goldens 3,114 -> 2,185, tryscript commands 66 -> 45; a repeated identical record prints as a back-reference, compared by exact serialized text. Independent review restored six lost detections and added security evidence: a hostile-link corpus fed to both inert layers, record validation on read, a 401 typed not_logged_in, Git's text kept out of messages. 111 of 117 mutations fail a test; the rest are mb-3ulm and one equivalent. CI green on the head merged above #256; full local make test passed."
resolution: null
duplicate_of: null
---
Part of the test-suite review epic. Survey of a896d8fe, 2026-09-30, read-only. All files are new since `origin/main`. The oracle and `tests/test_github_coverage.py` are handled by the Hosted Review cleanup bead.

## Scope

- Tests: `tests/test_github_pulls.py` (1,457 lines, 59 functions, 74 cases, 20.4 s in CI), `test_github_url_reducer.py` (503), `test_github_pull_page_session.py` (421), `test_github_serve.py` (341), `test_github_live_smoke.py` (241), `test_github_pull_live_smoke.py` (177), `test_github_credentials.py` (217), `test_github_provider.py` (170), `test_github_check_tones.py` (117), `test_pull_page_route.py` (85).
- Helpers and fixtures: `tests/github_pull_fixture.py` (667), `tests/github_origin.py` (124), `tests/fixtures/github-pull/responses.json` (122, the one authored source), `tests/fixtures/github-pull-page-responses.json` (2,203, recorded).
- Goldens: `cli-github-pull.tryscript.md` (1,153, 24 commands, 18.6 s), `cli-github-pull-refresh.txt` (977), `cli-ui-github-pull-page.tryscript.md` (703), `cli-github-url-open.txt` (487), `cli-github-urls.tryscript.md` (267, 34 commands, 16.4 s), `cli-github-url-waits.txt` (163).

## Findings

1. A live test that can never run. `tests/test_github_pull_live_smoke.py:33-37` lacks `pytest.mark.live_github` (compare `tests/test_github_live_smoke.py:40-47`). `tests/conftest.py:73-80` lifts the failing stand-in `gh` only for tests carrying that marker, so with `METABROWSER_LIVE_GITHUB=1` both tests reach the stand-in and skip with "gh is not signed in". `docs/qa-v012-repository-library.md:672` gives this command with a pass criterion it cannot meet. Rule: "It must never silently skip a test the suite is believed to run." (The skip path was read, not executed.)
2. One 122-line source printed as about 18 full record copies. The recording holds 11 full records; adjacent 184-line envelopes differ by 2–5 lines (`github-pull-page-responses.json:62-245` vs `303-486`). `cli-github-pull.tryscript.md` repeats the PR 7 record at `:69-231` and `:653-815`; `cli-github-pull-refresh.txt` repeats it at `:23, 255, 810` although its driver already asserts equality (`tests/test_cli_github_pull_golden.py:145, 245`). Rule: "Keep fixture diffs reviewable. One enormous input hides the behavior that changed." Keys `absent_unchanged` and `refresh_third` are recorded but never read by the session.
3. Narrow slices in the golden. `cli-github-pull.tryscript.md:939, 960, 984, 1089, 1101, 1147` pipe through `grep`. `:1089`'s pattern lists `type`, a key the route does not send, so that alternative matches nothing, silently. Golden anti-pattern 2: "Narrow extractions pass silently even when the data has unexpected content." They exist because every envelope embeds the 160-line record.
4. Tests fully restated by goldens in `tests/test_github_pulls.py`: `:259` (in `cli-github-pull-refresh.txt:630-655, 760-787`), `:280` (`cli-github-pull.tryscript.md:47-233`), `:312` (`cli-github-pull-refresh.txt:200-219`), `:588` (`cli-github-pull.tryscript.md:849-873`), `:622` (`:1089-1139`), `:649` (`tests/test_github_pull_page_session.py:356` runs the real route on the same input), `:717` (`cli-github-pull-refresh.txt:684-697`), `:571-585` (`tests/test_git_revision_diff.py:138-156`), `:476` (inferred from `cli-github-pull.tryscript.md:1141-1153`).
5. A second copy of a golden as Python asserts. `tests/test_github_pull_page_session.py:375-421` runs the same `node tests/dom/github-pull-page-session.js` the tryscript runs and re-asserts about 20 values that are verbatim in `cli-ui-github-pull-page.tryscript.md:636-664`.
6. Call assertions. `tests/test_github_pulls.py:1247-1257` replaces `track_process_group` / `forget_process_group` with list-appenders and asserts `tracked == forgotten`; `:1224-1244` fakes `restore_mirror_refs` and asserts the fake was called; `:908-922` asserts `--atomic` in argv and `len(fetches) == 2`. Rule: "Assert Transferred Data, Not Merely That a Mock Was Called."
7. Repeated examples. `tests/test_github_pulls.py:1006-1028` and `:1260-1277` end in the same four assertions; `:1412-1426` and `:1429-1457` cover the same bound. `_settle` is defined three times (`tests/test_github_pulls.py:1041`, `tests/test_github_serve.py:86`, `tests/test_github_pull_page_session.py:161`).
8. URL grammar. All 26 refusals in `cli-github-urls.tryscript.md` are rows of the unit table in `tests/test_github_url_reducer.py` (for example golden `:71` = unit `:182`). The seven accepted-spelling blocks (`:38-66, 191-201`) all print the identical `--walk` error and show no selection; `cli-github-url-open.txt:1-24` covers them.
9. Per-test cost. 50 of 59 tests use the function-scoped `stand` (`tests/test_github_pulls.py:131-147`): about 11 git spawns plus an acquisition per test, and each refresh starts about 8 Python interpreters because the fake `gh` is a Python script (`tests/github_pull_fixture.py:53`).

## Proposed restructuring

1. Add the `live_github` marker to `tests/test_github_pull_live_smoke.py` and document the live tier (how it is selected, when it runs) in `docs/e2e-testing.md`.
2. Store each distinct record once in the recording and drop the two unread keys; replace repeat full-envelope reads in the two CLI goldens with the `--show /pull/<n>` summary line where the driver or an earlier block already pins the full record; then replace the six `grep` slices with full output.
3. Delete the nine tests in finding 4, cut finding 5 to its three `allowlist_violations` invariants (`:393-395`), merge the pairs in finding 7, and convert the three call-assertion tests to assert the observable result (the process group is gone; the refs are back).
4. Trim the seven accepted-spelling blocks from `cli-github-urls.tryscript.md`; keep one refusal per reason class there and leave the full table in the unit test.
5. Build the deterministic origin once per session and copy it per test.

## Expected reduction

- Tests: about −300 to −350 lines.
- Fixtures: about −900 lines.
- Goldens: about −180 (`cli-github-pull`), −330 (`cli-github-pull-refresh`), −45 or more (`cli-github-urls`).
- Run time: not estimated for step 5; step 4 saves about 0.5 s per removed command.

## Acceptance

- The epic's accept rule.
- `METABROWSER_LIVE_GITHUB=1` runs both live files (shown in the PR with `-rs`).
- A one-field change to the PR record produces a diff a reviewer can read in one screen.

## Must NOT be removed

- `tests/test_github_credentials.py`: the only proof that the gh helper answers solely for `https://github.com`.
- In `tests/test_github_pulls.py`: `:322` (ETags not replayed for another reader), `:360-417, 735-877` (bounds and truncation), `:954-1003` (fetch lock), `:1084` (origin, 415, 413 and `pin_changed` refusals), `:1145, 1196, 1383` (serve mode), `:224` (path refusal).
- `tests/test_github_pull_page_session.py:322-372`: the only link making the JS session's inputs real server output.
- The `--- gh ---` sections of `cli-github-pull-refresh.txt`: the only evidence of which gh calls each command makes.
- `tests/test_github_serve.py`, `tests/test_github_url_reducer.py:296-438`, the tone table in `tests/test_github_check_tones.py`, `tests/test_pull_page_route.py:26-48`, and `tests/fixtures/github-pull/responses.json`.

Labelled `release:v0.12.0`: the files are new in the stack, and finding 1 is a QA-runbook step that cannot pass as written.
