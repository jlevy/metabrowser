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
  cp -R "$TRYSCRIPT_TEST_DIR/../fixtures/frontmatter-bounds" docs
---
# Golden Test: Front Matter Past Its Bounds

A Markdown file’s YAML front matter is parsed by one loader,
`src/metabrowser/frontmatter_yaml.py`. YAML aliases let a few hundred bytes stand for
millions of values, so the loader measures the composed document and then builds it
itself, and refuses front matter that, written out without its aliases, is larger than
`FRONTMATTER_MAX_EXPANDED_SIZE` characters, and an alias inside the value it names.
A refused front matter is not metadata: the file still answers as text, with
`frontmatter_error` the sentence a page shows and `frontmatter_error_detail` saying why,
and its rendered document shows the same sentence.

This transcript runs a served folder.
The compressed reader and a pinned revision share the loader and have their own fence
readers; `tests/test_frontmatter_bounds.py` and
`tests/test_git_revision_content_routes.py` pin those.

`tests/fixtures/frontmatter-bounds` holds `bomb.md`, seven anchors of nine aliases each
(9**7 values in 310 bytes of YAML); `merge.md`, twelve mappings each merging nine
aliases of the one before; `duplicate.md`, the seven alias levels and a key repeated
with them as its value; `loop.md`, an alias inside its own anchor; `badtag.md`, a tag
its constructor refuses; `shared.md`, an anchor used twice within the bound; and
`tags.md`, the tags JSON has no type for.

## Test: an alias bomb answers as text with the reason

The answer has the file’s text and kind, no `frontmatter`, the page’s sentence, and the
reason.

```console
$ metab docs --api '/api/file?path=bomb.md' > bomb.txt
? 0
```

```console
$ grep -E '^  "(type|kind|frontmatter|frontmatter_error|frontmatter_error_detail)":' bomb.txt
  "type": "text",
  "kind": "markdown",
  "frontmatter_error": "The frontmatter could not be read.",
  "frontmatter_error_detail": "Front matter not parsed: written out without its YAML aliases it is larger than 1,048,576 characters"
? 0
```

## Test: under the untrusted profile the document renders with the reason

The inert render shows the body and names the refusal in its diagnostics; the answer
carries the reason. KPress’s Frontmatter error notice leaves the inert HTML, whose
allowlist would keep only its words, and the page draws the notice from the diagnostic
where the Frontmatter disclosure would be
(`cli-ui-markdown-frontmatter-error.tryscript.md`).

```console
$ metab docs --untrusted --api '/api/kpress/render?path=bomb.md&view=document' > render.txt
? 0
```

```console
$ grep -E '^  "(type|inert|frontmatter_error_detail)":|^      "(type|message)":' render.txt
  "type": "kpress-rendered-document",
      "type": "frontmatter_error",
      "message": "The frontmatter could not be read.",
  "inert": true,
  "frontmatter_error_detail": "Front matter not parsed: written out without its YAML aliases it is larger than 1,048,576 characters",
? 0
```

```console
$ grep '^  "html":' render.txt
  "html": "\n<div><div><h1 id=\"user-content-seven-alias-levels\">Seven Alias Levels</h1>\n<p>The body still renders.</p></div></div>",
? 0
```

## Test: merge keys and a duplicated key are refused before they expand

A merge key copies the mappings it names into the one that holds it, and a duplicated
key would write both its values into the reason.
Both are measured on the composed document, and refused with the same short reason.

```console
$ metab docs --api '/api/file?path=merge.md' > merge.txt
? 0
```

```console
$ grep -E '^  "frontmatter' merge.txt
  "frontmatter_error": "The frontmatter could not be read.",
  "frontmatter_error_detail": "Front matter not parsed: written out without its YAML aliases it is larger than 1,048,576 characters"
? 0
```

```console
$ metab docs --api '/api/file?path=duplicate.md' > duplicate.txt
? 0
```

```console
$ grep -E '^  "frontmatter' duplicate.txt
  "frontmatter_error": "The frontmatter could not be read.",
  "frontmatter_error_detail": "Front matter not parsed: written out without its YAML aliases it is larger than 1,048,576 characters"
? 0
```

## Test: a tag its constructor refuses is a reason, not an internal error

```console
$ metab docs --api '/api/file?path=badtag.md' > badtag.txt
? 0
```

```console
$ grep -E '^  "(type|frontmatter|frontmatter_error|frontmatter_error_detail)":' badtag.txt
  "type": "text",
  "frontmatter_error": "The frontmatter could not be read.",
  "frontmatter_error_detail": "Error parsing YAML metadata: line 1: not a valid !!bool"
? 0
```

## Test: an alias inside its own anchor is refused

```console
$ metab docs --api '/api/file?path=loop.md' > loop.txt
? 0
```

```console
$ grep -E '^  "frontmatter' loop.txt
  "frontmatter_error": "The frontmatter could not be read.",
  "frontmatter_error_detail": "Front matter not parsed: a YAML alias refers to a value that contains it"
? 0
```

## Test: an anchor within the bound is written out

Each use of the anchor is its own copy of the value.

```console
$ metab docs --api '/api/file?path=shared.md' > shared.txt
? 0
```

```console
$ sed -n '/^  "frontmatter": {/,/^  }/p' shared.txt
  "frontmatter": {
    "author": {
      "name": "Ada",
      "tags": [
        "math",
        "engines"
      ]
    },
    "reviewer": {
      "name": "Ada",
      "tags": [
        "math",
        "engines"
      ]
    }
  }
? 0
```

## Test: tags JSON has no type for answer as JSON values

Binary is its base64 text, a set is its sorted members, pairs are two-item lists, a
float JSON cannot hold is its YAML spelling, a date is ISO 8601, and a key that is not a
string is its JSON text.

```console
$ metab docs --api '/api/file?path=tags.md' > tags.txt
? 0
```

```console
$ sed -n '/^  "frontmatter": {/,/^  }/p' tags.txt
  "frontmatter": {
    "binary": "aGVsbG8=",
    "set": [
      "a",
      "b"
    ],
    "pairs": [
      [
        "a",
        1
      ],
      [
        "a",
        2
      ]
    ],
    "nan": ".nan",
    "inf": "-.inf",
    "date": "2026-11-17",
    "[\"a\", \"b\"]": "tuple key",
    "1": "int key"
  }
? 0
```
