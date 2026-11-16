---
sandbox: true
path:
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "WARNING"
before: >-
  cp -R "$TRYSCRIPT_TEST_DIR/../fixtures/render-diagnostics" docs
---
# Golden Test: Which Render Diagnostics the Reader Sees

`/api/kpress/render` answers two lists of diagnostics.
`diagnostics` is what the reader’s Diagnostics disclosure shows above the document:
faults the author can fix, such as a link to a heading that does not exist.
`sanitizer_diagnostics` records what KPress’s sanitizer removed from the document’s raw
HTML: a `<script>`, a `javascript:` link, an attribute outside its profile, or, under
the catch-all `html_sanitized`, a change it could not name.
Removing them is the safe outcome, and GitHub does the same without a word, so they are
kept for `--api` and debugging rather than shown to the reader.
A stripped comment and nh3’s reserialization, such as `&nbsp;`, are not reported at all.

`tests/fixtures/render-diagnostics` holds a README with a centered icon block and a
guideline footer comment, a guide with only the footer comment, a document with a script
and a `javascript:` link, and one with a broken anchor beside a script.

## Test: a README with a centered icon block shows the reader nothing

KPress keeps the presentational `align` on the icon’s paragraph and the title, as GitHub
does, so the block renders centered and nothing is removed.
The footer comment is stripped without a report.

```console
$ metab docs --api '/api/kpress/render?path=README.md' > README.txt
? 0
```

```console
$ grep -E '^  "(diagnostics|sanitizer_diagnostics)":|^      "(type|message)":' README.txt
  "diagnostics": [],
  "sanitizer_diagnostics": [],
? 0
```

```console
$ grep '^  "html":' README.txt | grep -oE '<(p|h1) [^>]*align=\\"center\\"'
<p align=\"center\"
<h1 align=\"center\"
? 0
```

## Test: a guide with a footer comment shows the reader nothing

KPress strips the comment without reporting it: a comment is not content.

```console
$ metab docs --api '/api/kpress/render?path=guide.md' > guide.txt
? 0
```

```console
$ grep -E '^  "(diagnostics|sanitizer_diagnostics)":|^      "(type|message)":' guide.txt
  "diagnostics": [],
  "sanitizer_diagnostics": [],
? 0
```

## Test: a removed script shows the reader nothing

The script and the `javascript:` link are gone from the HTML, and each removal is named
in `sanitizer_diagnostics`.

```console
$ metab docs --api '/api/kpress/render?path=unsafe.md' > unsafe.txt
? 0
```

```console
$ grep '^  "html":' unsafe.txt | grep -cE '<script|javascript:'
0
? 1
```

```console
$ grep -E '^  "(diagnostics|sanitizer_diagnostics)":|^      "(type|message)":' unsafe.txt
  "diagnostics": [],
  "sanitizer_diagnostics": [
      "type": "html_sanitized_tag",
      "message": "Removed raw HTML tag <script>.",
      "type": "html_sanitized_attribute",
      "message": "Removed attribute 'href' from <a>.",
? 0
```

## Test: an authoring fault still reaches the reader

A link to a heading that does not exist stays in `diagnostics`, and the script beside it
stays out.

```console
$ metab docs --api '/api/kpress/render?path=broken.md' > broken.txt
? 0
```

```console
$ grep -E '^  "(diagnostics|sanitizer_diagnostics)":|^      "(type|message)":' broken.txt
  "diagnostics": [
      "type": "broken_anchor",
      "message": "Internal link target '#nowhere' was not found.",
  "sanitizer_diagnostics": [
      "type": "html_sanitized_tag",
      "message": "Removed raw HTML tag <script>.",
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
