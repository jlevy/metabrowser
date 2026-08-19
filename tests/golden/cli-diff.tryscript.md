---
sandbox: true
path:
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  GIT_AUTHOR_NAME: "Fixture Author"
  GIT_AUTHOR_EMAIL: "author@example.invalid"
  GIT_COMMITTER_NAME: "Fixture Author"
  GIT_COMMITTER_EMAIL: "author@example.invalid"
  GIT_CONFIG_GLOBAL: "/dev/null"
  GIT_CONFIG_SYSTEM: "/dev/null"
  GIT_AUTHOR_DATE: "2026-01-01T00:00:00 +0000"
  GIT_COMMITTER_DATE: "2026-01-01T00:00:00 +0000"
---
# Golden tests: --diff

The diff data plane end to end from the CLI, with no server running: manifest text,
single-file hunks, the hydrated JSON document, the apply oracle, a standalone patch
file, and the error paths.
Identity and both git dates are pinned in the frontmatter, so commit ids and tree hashes
are literal — a changed id here means the fixture or the model changed, which is exactly
what a golden is for.

## Test: build the fixture repository

Two commits whose delta covers modify, rename-with-edit, and add.
The second commit re-pins the dates so both ids stay deterministic.

```console
$ git init -q -b main repo \
>   && cd repo \
>   && printf 'def f():\n    return 1\n' > a.py \
>   && printf 'x = 1\n' > u.py \
>   && git add -A && git commit -qm base \
>   && export GIT_AUTHOR_DATE='2026-01-02T00:00:00 +0000' \
>   && export GIT_COMMITTER_DATE='2026-01-02T00:00:00 +0000' \
>   && printf 'def f():\n    return 2\n' > a.py \
>   && mkdir h && git mv u.py h/u.py \
>   && printf 'x = 1\ny = 2\n' > h/u.py \
>   && printf 'hello\n' > new.md \
>   && git add -A && git commit -qm target
? 0
```

## Test: manifest summary in text

```console
$ metab repo --diff 'HEAD^..HEAD'
comparison git:10e5320d75eeeaf3 (direct)
left  ac107eaa9009cb6012a76154510bfdd9927b5fc2
right cde4cdc5bf066da46253dae484db273f8d35cb70
files 3  +3 -1  (exact)
M    a.py  [+1 -1]
R50  u.py -> h/u.py  [+1 -0]
A    new.md  [+1 -0]
? 0
```

## Test: one revision compares against its first parent

```console
$ metab repo --diff HEAD
comparison git:10e5320d75eeeaf3 (first_parent)
left  ac107eaa9009cb6012a76154510bfdd9927b5fc2
right cde4cdc5bf066da46253dae484db273f8d35cb70
files 3  +3 -1  (exact)
M    a.py  [+1 -1]
R50  u.py -> h/u.py  [+1 -0]
A    new.md  [+1 -0]
? 0
```

## Test: one file’s hunks

```console
$ metab repo --diff 'HEAD^..HEAD' --diff-patch a.py
@@ -1,2 +1,2 @@
 def f():
-    return 1
+    return 2
? 0
```

## Test: the apply oracle from the CLI

The produced hash is the change set applied to the base tree; the target hash is git’s
own tree. Equal hashes are the completeness proof.

```console
$ metab repo --diff 'HEAD^..HEAD' --diff-check
produced f478561cac77f02927fc25b25e35c321c86a71e934524059e3dcc589e37227f8
target   f478561cac77f02927fc25b25e35c321c86a71e934524059e3dcc589e37227f8
apply: clean
? 0
```

## Test: the hydrated JSON document is format-valid on the wire

The full ChangeSetDocument for the same comparison, exactly what /api/diff/ serves and
the browser model validates.

```console
$ metab repo --diff 'HEAD^..HEAD' --format json | head -24
{
  "manifest": {
    "files": [
      {
        "additions": 1,
        "availability": "ready",
        "binary": false,
        "deletions": 1,
        "id": "f1",
        "kind": "modified",
        "new": {
          "content": {
            "kind": "git_object",
            "oid": "ea743618ff6e9efc040fe434725239c7c5ebf113"
          },
          "entry_type": "file",
          "mode": "100644",
          "path": "a.py"
        },
        "old": {
          "content": {
            "kind": "git_object",
            "oid": "b8595995dba30b1cf7ee90f336b3e3356ee99e1b"
          },
? 0
```

## Test: a standalone patch file needs no repository

```console
$ printf 'diff --git a/x.txt b/x.txt\n--- a/x.txt\n+++ b/x.txt\n@@ -1,1 +1,1 @@\n-old\n+new\n' > standalone.patch
? 0
```

```console
$ metab . --diff standalone.patch
comparison patch:f8a380fbae536e49 (direct)
left  patch
right patch
files 1  +1 -1  (exact)
M    x.txt  [+1 -1]
? 0
```

## Test: unknown revision reports and exits 2

```console
$ metab repo --diff nosuchref 2>&1
diff error: unknown revision 'nosuchref'
? 2
```

## Test: the oracle refuses a patch-file comparison

```console
$ metab . --diff standalone.patch --diff-check 2>&1
diff error: --diff-check needs a revision comparison, not a patch file
? 2
```
