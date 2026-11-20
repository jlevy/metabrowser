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
  printf '# Repo\n' > README.md &&
  git add README.md &&
  git commit -q -m root &&
  seq 1 2000 > numbers.txt &&
  git add numbers.txt &&
  git commit -q -m numbers &&
  git checkout -q -b topic &&
  awk '{ if ($0 == "1000") print "one thousand"; else print }' numbers.txt > edited.txt &&
  mv edited.txt numbers.txt &&
  git commit -q -am 'one line' &&
  printf 'a note\n' > notes.txt &&
  git add notes.txt &&
  git commit -q -m 'a note' &&
  git checkout -q main &&
  git merge -q --no-ff -m 'merge topic' topic
---
# Golden Test: A Commit’s Size

`/api/git/commit-size/<rev>` answers a commit’s size against its first parent: the thin
pack `git push` sends for it (`pushed_bytes`) and its patch, `git diff --binary`
(`diff_bytes`), with the commits the change holds
(`src/metabrowser/git/change_size.py`). The pushed size is zlib’s output, which can
differ by a few bytes between zlib builds, so it is elided;
`tests/test_git_change_size.py` checks it against the pack Git writes.
The patch’s size is Git’s text and is pinned.
The commit IDs are fixed by the pinned identity and dates.

## Test: the fixture’s commits

```console
$ git -C gitroot log --format='%H %s' --topo-order
22b5b3cf41936cb318a96262722330de511b03cc merge topic
53c57335f8d028dfd03bc70f28e0d1a846f35238 a note
02d65e27706aa66549bb364b4996284d62752ee5 one line
237c0f29afc06aa81c5cdb266096b5f4e6cc438a numbers
c16a4b38b7896429af7726c6ac42c069728e570e root
? 0
```

## Test: a one-line edit of a large file pushes a delta, not the file

```console
$ metab gitroot --api /api/git/commit-size/$(git -C gitroot rev-parse topic~1)
api: /api/git/commit-size/02d65e27706aa66549bb364b4996284d62752ee5
status: 200
{
  "is_repo": true,
  "size": {
    "base": "237c0f29afc06aa81c5cdb266096b5f4e6cc438a",
    "head": "02d65e27706aa66549bb364b4996284d62752ee5",
    "state": "measured",
    "reason": null,
    "commits": 1,
    "pushed_bytes": [..],
    "diff_bytes": 178
  }
}
? 0
```

## Test: a root commit is measured against nothing

```console
$ metab gitroot --api /api/git/commit-size/$(git -C gitroot rev-parse main~1~1)
api: /api/git/commit-size/[..]
status: 200
{
  "is_repo": true,
  "size": {
    "base": null,
    "head": "[..]",
    "state": "measured",
    "reason": null,
    "commits": 1,
    "pushed_bytes": [..],
    "diff_bytes": 131
  }
}
? 0
```

## Test: a merge holds the commits it brought in

Measured against its first parent, as the commit’s own view shows it.

```console
$ metab gitroot --api /api/git/commit-size/$(git -C gitroot rev-parse main)
api: /api/git/commit-size/22b5b3cf41936cb318a96262722330de511b03cc
status: 200
{
  "is_repo": true,
  "size": {
    "base": "237c0f29afc06aa81c5cdb266096b5f4e6cc438a",
    "head": "22b5b3cf41936cb318a96262722330de511b03cc",
    "state": "measured",
    "reason": null,
    "commits": 3,
    "pushed_bytes": [..],
    "diff_bytes": 309
  }
}
? 0
```

## Test: a commit the repository does not have, and a revision that is not an ID

```console
$ metab gitroot --api /api/git/commit-size/0000000000000000000000000000000000000000
api: /api/git/commit-size/0000000000000000000000000000000000000000
status: 404
{
  "error": "unknown revision",
  "code": "commit_not_found"
}
Error: /api/git/commit-size/0000000000000000000000000000000000000000 returned HTTP 404
? 1
```

```console
$ metab gitroot --api /api/git/commit-size/main
api: /api/git/commit-size/main
status: 400
{
  "error": "revision must be a full 40- or 64-character object id",
  "code": "revision_not_full"
}
Error: /api/git/commit-size/main returned HTTP 400
? 1
```
