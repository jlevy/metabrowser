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
removed value, as the file view opens a file; an unchanged value is closed, and shows
the file view’s preview of it, as a fold of unchanged blocks does in a Markdown file.
A click on a closed row opens it and on an open row closes it; a closed modified mapping
previews its new side.
Rows are the file view’s own (`renderRowHtml` of `structured/tree.js`): an unchanged row
is the file view’s row exactly, and a changed one adds its change class and a
screen-reader label.

This browserless session loads the production `builtin_plugins/diff/diff-structured.js`
and the structured plugin’s `preview.js` and `tree.js` whole, and draws the trees in
`tests/fixtures/diff-structured-responses.json`: what the production projection answers
for these files.
`tests/test_diff_structured_session.py` fails when the recording drifts.
The route itself is pinned by `tests/golden/cli-github-pull-rendered.txt`. Each line is
a row: its change, its kind, and its text, indented by its level.

```console
$ node tests/dom/diff-structured-session.js
{
  "config/app.yaml": {
    "opens": [
      "$",
      "$.services",
      "$.services.db",
      "$.services.web",
      "$.services.web.ports"
    ],
    "first draw": [
      "modified open {4 keys}",
      "  context kv name: \"demo\"",
      "  removed kv version: 3",
      "  added kv version: 4",
      "  modified open services: {1 keys}",
      "    modified open web: {2 keys}",
      "      context kv image: \"nginx\"",
      "      modified open ports: [2 items]",
      "        context item - 80",
      "        added item - 443",
      "    removed open db: {2 keys}",
      "      removed kv image: \"postgres\"",
      "      removed kv port: 5432",
      "  context open flags: [\"fast\", \"safe\"]"
    ],
    "after opening $.flags": [
      "modified open {4 keys}",
      "  context kv name: \"demo\"",
      "  removed kv version: 3",
      "  added kv version: 4",
      "  modified open services: {1 keys}",
      "    modified open web: {2 keys}",
      "      context kv image: \"nginx\"",
      "      modified open ports: [2 items]",
      "        context item - 80",
      "        added item - 443",
      "    removed open db: {2 keys}",
      "      removed kv image: \"postgres\"",
      "      removed kv port: 5432",
      "  context open flags: [2 items]",
      "    context item - \"fast\"",
      "    context item - \"safe\""
    ],
    "after closing $.services": [
      "modified open {4 keys}",
      "  context kv name: \"demo\"",
      "  removed kv version: 3",
      "  added kv version: 4",
      "  modified open services: {web: {…}}",
      "  context open flags: [2 items]",
      "    context item - \"fast\"",
      "    context item - \"safe\""
    ]
  },
  "package.json": {
    "opens": [
      "$",
      "$.scripts"
    ],
    "first draw": [
      "added open {2 keys}",
      "  added kv name: \"demo\"",
      "  added open scripts: {1 keys}",
      "    added kv test: \"make\""
    ],
    "after closing $.scripts": [
      "added open {2 keys}",
      "  added kv name: \"demo\"",
      "  added open scripts: {test: \"make\"}"
    ]
  },
  "data/swap.json": {
    "opens": [
      "$"
    ],
    "first draw": [
      "removed open [2 items]",
      "  removed item - 1",
      "  removed item - 2",
      "added kv \"text\""
    ]
  }
}
? 0
```
