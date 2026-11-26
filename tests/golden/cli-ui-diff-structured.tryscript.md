---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Rendered YAML and JSON in a Pull Request’s Changes

A pull request’s Changes opens each changed YAML or JSON file in **Rendered**, as it
opens a Markdown file: the structured plugin’s tree, the one the file view draws, with
each row in the change gutter.
The server answers the file’s merged tree, `structured-diff-v1`, from
`GET github/pull-rendered-diff`; each entry is unchanged (`context`), `added`,
`removed`, or `modified`, a mapping or list whose entries differ.
A scalar that changed is its old row removed and its new row added.

On the first draw every modified mapping and list is open, and so is a whole added or
removed value, as the file view opens a file, while the draw stays within its row budget
(`ROW_BUDGET` in `diff-structured.js`); an unchanged value is closed and shows the file
view’s preview of it, as a fold of unchanged blocks does in a Markdown file.
A click on a closed row opens it and on an open row closes it, and replaces only that
row and the rows under it; a closed modified mapping previews its new side.
An open container draws its children a page at a time (`PAGE`), and a “more” row draws
the next page. Rows are the file view’s own (`renderRowHtml` of `structured/tree.js`),
with a changed one adding its change class and a screen-reader label.
One difference: a mapping or list that is an item of a modified list reads `- `, where
the file view gives its index, since the two sides number a changed list’s items
differently.

This browserless session loads the production `builtin_plugins/diff/diff-structured.js`,
`diff-markdown.js` and the structured plugin’s `preview.js` and `tree.js` whole, and
mounts the files in `tests/fixtures/diff-structured-responses.json`, what the production
projection answers for them, through the page’s views as Changes does.
The first step is the first screen: the requests in order, how often the tree renderer
was asked for, and each file’s chooser, what its body shows, and its rows.
A file whose answer is a refusal (here a key twice in one mapping) shows only Source,
with no chooser. An alias reads as the value it names.
A file whose only change is outside the tree (here a comment) notes that Source shows
it, and one whose value changed only in type beside a drawn change (here a date that
became a string) notes that Source shows a change the tree draws as unchanged.
An added JSON file that writes a key twice draws the last value, as the file view does,
and notes that Source shows the value it hides.
The steps after it click rows of `config/app.yaml`, mount it where the tree renderer
fails to load, and dispose of the views.
Each row line is its change, its state (`open`, `closed`, `leaf`, `empty` or `more`),
and its text, indented by its level.
`tests/test_diff_structured_session.py` fails when the recording drifts.
The route itself is pinned by `tests/golden/cli-github-pull-rendered.txt`.

```console
$ node tests/dom/diff-structured-session.js
{
  "row budget": 1000,
  "page": 500,
  "steps": [
    {
      "step": "the first screen: each file asked for in turn, and a tree's renderer once",
      "renderer asked before the first answer": 1,
      "renderer asked in all": 1,
      "requests": [
        "config/app.yaml",
        "package.json",
        "data/swap.json",
        "deploy/anchors.yaml",
        "deploy/duplicate.yaml",
        "config/comments.yaml",
        "config/dates.yaml",
        "tools/package.json"
      ],
      "files": {
        "config/app.yaml": {
          "chooser": "YAML diff format: *Rendered | Source",
          "shows": "rendered",
          "rows": [
            "modified open {4 keys}",
            "  context leaf name: \"demo\"",
            "  removed leaf version: 3",
            "  added leaf version: 4",
            "  modified open services: {1 keys}",
            "    modified open web: {2 keys}",
            "      context leaf image: \"nginx\"",
            "      modified open ports: [2 items]",
            "        context leaf - 80",
            "        added leaf - 443",
            "    removed open db: {2 keys}",
            "      removed leaf image: \"postgres\"",
            "      removed leaf port: 5432",
            "  context closed flags: [\"fast\", \"safe\"]"
          ]
        },
        "package.json": {
          "chooser": "JSON diff format: *Rendered | Source",
          "shows": "rendered",
          "rows": [
            "added open {2 keys}",
            "  added leaf name: \"demo\"",
            "  added open scripts: {1 keys}",
            "    added leaf test: \"make\""
          ]
        },
        "data/swap.json": {
          "chooser": "JSON diff format: *Rendered | Source",
          "shows": "rendered",
          "rows": [
            "removed open [2 items]",
            "  removed leaf - 1",
            "  removed leaf - 2",
            "added leaf \"text\""
          ]
        },
        "deploy/anchors.yaml": {
          "chooser": "YAML diff format: *Rendered | Source",
          "shows": "rendered",
          "rows": [
            "modified open {2 keys}",
            "  modified open base: {1 keys}",
            "    removed leaf replicas: 1",
            "    added leaf replicas: 2",
            "  modified open worker: {1 keys}",
            "    removed leaf replicas: 1",
            "    added leaf replicas: 2"
          ]
        },
        "deploy/duplicate.yaml": {
          "chooser": "YAML diff format: Rendered | *Source",
          "shows": "source"
        },
        "config/comments.yaml": {
          "chooser": "YAML diff format: *Rendered | Source",
          "shows": "rendered",
          "rows": [
            "note: The tree shows no change. Source shows what changed in the text.",
            "context closed {mode: \"fast\", retries: 3}"
          ]
        },
        "config/dates.yaml": {
          "chooser": "YAML diff format: *Rendered | Source",
          "shows": "rendered",
          "rows": [
            "note: Source shows a change the tree draws as unchanged.",
            "modified open {2 keys}",
            "  context leaf released: \"2026-11-18\"",
            "  removed leaf retries: 3",
            "  added leaf retries: 4"
          ]
        },
        "tools/package.json": {
          "chooser": "JSON diff format: *Rendered | Source",
          "shows": "rendered",
          "rows": [
            "note: Source shows a value the tree does not draw: a later one under the same key hides it.",
            "added open {2 keys}",
            "  added empty scripts: {}",
            "  added leaf name: \"demo\""
          ]
        }
      }
    },
    {
      "step": "Excerpt keeps changed paths and a marker for removed values",
      "rows": [
        "modified open {4 keys}",
        "  removed leaf version: removed",
        "  added leaf version: 4",
        "  modified open services: {1 keys}",
        "    modified open web: {2 keys}",
        "      modified open ports: [2 items]",
        "        added leaf - 443",
        "    removed leaf db: removed"
      ]
    },
    {
      "step": "Full includes unchanged values in the new tree",
      "rows": [
        "modified open {4 keys}",
        "  context leaf name: \"demo\"",
        "  added leaf version: 4",
        "  modified open services: {1 keys}",
        "    modified open web: {2 keys}",
        "      context leaf image: \"nginx\"",
        "      modified open ports: [2 items]",
        "        context leaf - 80",
        "        added leaf - 443",
        "  context closed flags: [\"fast\", \"safe\"]"
      ]
    },
    {
      "step": "a click on a closed unchanged list opens it, as the file view's tree does",
      "rows": [
        "modified open {4 keys}",
        "  context leaf name: \"demo\"",
        "  removed leaf version: 3",
        "  added leaf version: 4",
        "  modified open services: {1 keys}",
        "    modified open web: {2 keys}",
        "      context leaf image: \"nginx\"",
        "      modified open ports: [2 items]",
        "        context leaf - 80",
        "        added leaf - 443",
        "    removed open db: {2 keys}",
        "      removed leaf image: \"postgres\"",
        "      removed leaf port: 5432",
        "  context open flags: [2 items]",
        "    context leaf - \"fast\"",
        "    context leaf - \"safe\""
      ]
    },
    {
      "step": "a click on an open modified mapping closes it, previewing its new side",
      "rows": [
        "modified open {4 keys}",
        "  context leaf name: \"demo\"",
        "  removed leaf version: 3",
        "  added leaf version: 4",
        "  modified closed services: {web: {…}}",
        "  context open flags: [2 items]",
        "    context leaf - \"fast\"",
        "    context leaf - \"safe\""
      ]
    },
    {
      "step": "opened again, it keeps open what was open inside it",
      "rows": [
        "modified open {4 keys}",
        "  context leaf name: \"demo\"",
        "  removed leaf version: 3",
        "  added leaf version: 4",
        "  modified open services: {1 keys}",
        "    modified open web: {2 keys}",
        "      context leaf image: \"nginx\"",
        "      modified open ports: [2 items]",
        "        context leaf - 80",
        "        added leaf - 443",
        "    removed open db: {2 keys}",
        "      removed leaf image: \"postgres\"",
        "      removed leaf port: 5432",
        "  context open flags: [2 items]",
        "    context leaf - \"fast\"",
        "    context leaf - \"safe\""
      ]
    },
    {
      "step": "a tree renderer that failed to load leaves the file in Source, its chooser kept",
      "files": {
        "config/app.yaml": {
          "chooser": "YAML diff format: Rendered | *Source",
          "shows": "source"
        }
      },
      "warnings": [
        "metabrowser diff: a rendered file failed; showing Source"
      ]
    },
    {
      "step": "disposal removes each tree's click listener",
      "listeners": 0
    }
  ]
}
? 0
```
