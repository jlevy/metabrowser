---
sandbox: true
path:
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "WARNING"
  GIT_CONFIG_GLOBAL: "/dev/null"
  GIT_CONFIG_SYSTEM: "/dev/null"
  GIT_AUTHOR_NAME: "Test"
  GIT_AUTHOR_EMAIL: "test@example.com"
  GIT_COMMITTER_NAME: "Test"
  GIT_COMMITTER_EMAIL: "test@example.com"
  GIT_AUTHOR_DATE: "2020-01-01T00:00:00Z"
  GIT_COMMITTER_DATE: "2020-01-01T00:00:00Z"
before: >-
  unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_PREFIX GIT_NAMESPACE GIT_CEILING_DIRECTORIES &&
  mkdir -p gitroot &&
  cd gitroot &&
  git init -q --initial-branch=main . &&
  awk 'BEGIN { for (n = 1; n <= 40; n++) print "line " n }' > app.py &&
  printf 'first\nsecond\n' > gone.py &&
  printf '\000\001\002' > logo.bin &&
  git add -A &&
  git commit -q -m 'base' &&
  awk 'NR == 5 { $0 = "line 5, changed" } NR == 30 { $0 = "line 30, changed" } { print }' app.py > app.next &&
  mv app.next app.py &&
  rm gone.py &&
  printf '\000\001\003' > logo.bin &&
  git add -A &&
  git commit -q -m 'edit two lines far apart, delete a file, change a binary'
---
# Golden tests: a comparison’s unchanged lines, by range

A code file’s diff shows each change with three lines of context, and the page opens the
unchanged lines between its hunks, above the first, and below the last behind the diff’s
fold bar (docs/design-system.md, “Fold Expanders”). It reads them here: `view=lines` on
the comparison route answers a run of one changed file’s new side, from `start`
(1-based), or before `end` for a gap the page opens upward to a hunk, `count` lines long
and at most `DIFF_GAP_LINES` (settings.py).
A run of long lines stops at `MAX_LINES_ANSWER_BYTES` of text (`diff/side_lines.py`),
keeping the lines nearest the line it was asked from, so `start` says where an answer
begins. The answer says how many lines the side has and whether it ends in a newline,
which is how the page learns where the file ends below its last hunk.
A pull request’s comparison route (`/api/plugin/github/pull-comparison`) answers the
same view, as it answers the comparison itself.

The commit edits `app.py`, 40 lines, at lines 5 and 30, so its hunks leave lines 1, 9 to
26, and 34 to 40 out.
The fixture pins identity and dates, so the comparison’s ID is the same on every
machine.

## Test: Full source at the reviewed revision

Full uses the same pinned comparison route.
A short file’s answer includes lines before, between, and after the hunks.

```console
$ metab gitroot --api '/api/plugin/diff/comparison?revision=HEAD&file=app.py&view=lines&whole=1'
api: /api/plugin/diff/comparison?revision=HEAD&file=app.py&view=lines&whole=1
status: 200
{
  "comparison_id": "git:e46d73d09b6c9e6f",
  "file_id": "f1",
  "path": "app.py",
  "start": 1,
  "lines": [
    "line 1",
    "line 2",
    "line 3",
    "line 4",
    "line 5, changed",
    "line 6",
    "line 7",
    "line 8",
    "line 9",
    "line 10",
    "line 11",
    "line 12",
    "line 13",
    "line 14",
    "line 15",
    "line 16",
    "line 17",
    "line 18",
    "line 19",
    "line 20",
    "line 21",
    "line 22",
    "line 23",
    "line 24",
    "line 25",
    "line 26",
    "line 27",
    "line 28",
    "line 29",
    "line 30, changed",
    "line 31",
    "line 32",
    "line 33",
    "line 34",
    "line 35",
    "line 36",
    "line 37",
    "line 38",
    "line 39",
    "line 40"
  ],
  "line_count": 40,
  "ends_with_newline": true
}
? 0
```

## Test: the lines between two hunks

```console
$ metab gitroot --api '/api/plugin/diff/comparison?revision=HEAD&file=app.py&view=lines&start=9&count=3'
api: /api/plugin/diff/comparison?revision=HEAD&file=app.py&view=lines&start=9&count=3
status: 200
{
  "comparison_id": "git:e46d73d09b6c9e6f",
  "file_id": "f1",
  "path": "app.py",
  "start": 9,
  "lines": [
    "line 9",
    "line 10",
    "line 11"
  ],
  "line_count": 40,
  "ends_with_newline": true
}
? 0
```

## Test: the rest of the file, past which there is nothing

The page asks below the last hunk without knowing where the file ends; the answer stops
at its last line and says how many it has.

```console
$ metab gitroot --api '/api/plugin/diff/comparison?revision=HEAD&file=app.py&view=lines&start=34&count=1000'
api: /api/plugin/diff/comparison?revision=HEAD&file=app.py&view=lines&start=34&count=1000
status: 200
{
  "comparison_id": "git:e46d73d09b6c9e6f",
  "file_id": "f1",
  "path": "app.py",
  "start": 34,
  "lines": [
    "line 34",
    "line 35",
    "line 36",
    "line 37",
    "line 38",
    "line 39",
    "line 40"
  ],
  "line_count": 40,
  "ends_with_newline": true
}
? 0
```

## Test: the lines up to a hunk, by their end

The page opens the gap above a hunk from the hunk upward, so it asks for the lines
before the hunk’s first, here the 3 above line 27.

```console
$ metab gitroot --api '/api/plugin/diff/comparison?revision=HEAD&file=app.py&view=lines&end=27&count=3'
api: /api/plugin/diff/comparison?revision=HEAD&file=app.py&view=lines&end=27&count=3
status: 200
{
  "comparison_id": "git:e46d73d09b6c9e6f",
  "file_id": "f1",
  "path": "app.py",
  "start": 24,
  "lines": [
    "line 24",
    "line 25",
    "line 26"
  ],
  "line_count": 40,
  "ends_with_newline": true
}
? 0
```

## Test: a deleted file has no new side to read

The page shows a separator it cannot open as it always did, so a refusal is a 409 with
the sentence the page would say, and the reason beside it for an agent.

```console
$ metab gitroot --api '/api/plugin/diff/comparison?revision=HEAD&file=gone.py&view=lines&start=1&count=5'
api: /api/plugin/diff/comparison?revision=HEAD&file=gone.py&view=lines&start=1&count=5
status: 409
{
  "error": "diff_lines",
  "message": "These lines cannot be shown.",
  "path": "gone.py",
  "detail": "this change has no new side",
  "code": "no_side"
}
Error: /api/plugin/diff/comparison?revision=HEAD&file=gone.py&view=lines&start=1&count=5 returned HTTP 409
? 1
```

## Test: a binary file has no lines to give

```console
$ metab gitroot --api '/api/plugin/diff/comparison?revision=HEAD&file=logo.bin&view=lines&start=1&count=5'
api: /api/plugin/diff/comparison?revision=HEAD&file=logo.bin&view=lines&start=1&count=5
status: 409
{
  "error": "diff_lines",
  "message": "These lines cannot be shown.",
  "path": "logo.bin",
  "detail": "the new side is not a file's text",
  "code": "not_text"
}
Error: /api/plugin/diff/comparison?revision=HEAD&file=logo.bin&view=lines&start=1&count=5 returned HTTP 409
? 1
```

## Test: an ask the route cannot read

A run is named by its start or its end, not both.

```console
$ metab gitroot --api '/api/plugin/diff/comparison?revision=HEAD&file=app.py&view=lines&start=1&end=4&count=5'
api: /api/plugin/diff/comparison?revision=HEAD&file=app.py&view=lines&start=1&end=4&count=5
status: 400
{
  "error": "diff_lines",
  "message": "view=lines names a start or an end, not both.",
  "path": "app.py"
}
Error: /api/plugin/diff/comparison?revision=HEAD&file=app.py&view=lines&start=1&end=4&count=5 returned HTTP 400
? 1
```

```console
$ metab gitroot --api '/api/plugin/diff/comparison?revision=HEAD&file=app.py&view=lines&start=0&count=5'
api: /api/plugin/diff/comparison?revision=HEAD&file=app.py&view=lines&start=0&count=5
status: 400
{
  "error": "diff_lines",
  "message": "start and count are whole numbers from 1.",
  "path": "app.py"
}
Error: /api/plugin/diff/comparison?revision=HEAD&file=app.py&view=lines&start=0&count=5 returned HTTP 400
? 1
```
