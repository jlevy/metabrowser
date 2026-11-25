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
  cp -R "$TRYSCRIPT_TEST_DIR/../fixtures/pin-frontmatter/notes" checkout &&
  cp "$TRYSCRIPT_TEST_DIR"/../fixtures/pin-frontmatter/*.json . &&
  git -C checkout init -q --initial-branch=main . &&
  git -C checkout add -A &&
  git -C checkout commit -q -m notes
---
# Golden Test: A Pinned Markdown File’s Front Matter Is the File’s Own

A Markdown file’s front matter is parsed from the file’s own bytes, on a served folder
and on a pinned revision: `/api/file` reports it, and `/api/kpress/render` hands it to
KPress. The Document view posts the text it renders as `source_text`, after its wiki
preprocessing, and that text is never read as the file’s front matter.
Before, a pinned revision parsed the posted text, and the preprocessor wrote a heading
anchor into the front matter’s last line (which, over the closing `---`, reads as a
setext heading), so a file whose YAML is valid was reported as a YAML error quoting the
`</span>` the page wrote.

`tests/fixtures/pin-frontmatter` holds an invented note, `harbor.md`, of seven plain
keys, the last a short ID; `broken.md`, whose description holds a second `: `; and the
render requests: `harbor-pin.json` and `harbor-folder.json` post `harbor.md` as the
preprocessor sent it before, anchor and all, and `broken-pin.json` posts `broken.md`
with its description mended.
`--ref main` opens the checkout at its commit, read from its Git objects, as a mirror of
a GitHub branch is read; a pinned revision always renders under the untrusted profile.
`g1-aGFyYm9yLm1k` and `g1-YnJva2VuLm1k` are the two files’ names as Git paths.

## Test: the pinned file’s front matter parses

```console
$ metab checkout --ref main --api '/api/file?path=g1-aGFyYm9yLm1k' > harbor-file.txt
? 0
```

```console
$ grep -E '^  "(kind|frontmatter_error)":|^    "[a-z_]+":' harbor-file.txt
  "kind": "markdown",
    "title": "Tide Tables for a Small Harbor",
    "description": "A working note on how the harbor office reads its tide tables and posts them for skippers each morning",
    "author": "Harbor Office",
    "date": "2026-03-02",
    "as_of": "2026-03-02",
    "status": "draft",
    "bead": "tide-k7m2"
? 0
```

## Test: the pinned render reads the blob, not the posted text

The posted front matter carries the anchor; the render reports no error, and its
Frontmatter disclosure holds the file’s keys.

```console
$ metab checkout --ref main --api /api/kpress/render --data harbor-pin.json > harbor-pin.txt
? 0
```

```console
$ grep -E '^  "(type|inert|diagnostics)":|^      "(type|message)":' harbor-pin.txt
  "type": "kpress-rendered-document",
  "diagnostics": [],
  "inert": true
? 0
```

```console
$ grep -o '<dt>bead</dt><dd>[^<]*</dd>' harbor-pin.txt
<dt>bead</dt><dd>tide-k7m2</dd>
? 0
```

## Test: a served folder reads the file the same way

The same request against the working tree, a trusted folder, parses the file too.

```console
$ metab checkout --api /api/kpress/render --data harbor-folder.json > harbor-folder.txt
? 0
```

```console
$ grep -E '^  "diagnostics":' harbor-folder.txt
  "diagnostics": [],
? 0
```

## Test: a pinned file’s own error stands, though the posted text parses

`/api/file` and the render say what the reader sees, that the front matter could not be
read, and carry the parser’s reason beside it, quoting the file’s own line, as
`frontmatter_error_detail`. The inert HTML has no Frontmatter error notice; the page
draws one from the diagnostic (`cli-ui-markdown-frontmatter-error.tryscript.md`).

```console
$ metab checkout --ref main --api '/api/file?path=g1-YnJva2VuLm1k' > broken-file.txt
? 0
```

```console
$ grep -E '^  "(kind|frontmatter|frontmatter_error|frontmatter_error_detail)":' broken-file.txt
  "kind": "markdown",
  "frontmatter_error": "The frontmatter could not be read.",
  "frontmatter_error_detail": "Error parsing YAML metadata: mapping values are not allowed here\n  in \"<unicode string>\", line 2, column 19:\n    description: Tides: how the harbor office reads it ... \n                      ^ (line: 2)"
? 0
```

```console
$ metab checkout --ref main --api /api/kpress/render --data broken-pin.json > broken-pin.txt
? 0
```

```console
$ grep -E '^  "frontmatter_error_detail":|^      "(type|message)":' broken-pin.txt
      "type": "frontmatter_error",
      "message": "The frontmatter could not be read.",
  "frontmatter_error_detail": "Error parsing YAML metadata: mapping values are not allowed here\n  in \"<unicode string>\", line 2, column 19:\n    description: Tides: how the harbor office reads it ... \n                      ^ (line: 2)"
? 0
```

```console
$ grep -c 'Frontmatter error' broken-pin.txt
0
? 1
```
