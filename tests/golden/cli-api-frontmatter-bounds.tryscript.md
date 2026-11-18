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
`src/metabrowser/frontmatter_yaml.py`, on every path: a served folder, a compressed
file, and a pinned revision.
YAML aliases let a few hundred bytes stand for millions of values, so the loader refuses
front matter that, written out without its aliases, is larger than
`FRONTMATTER_MAX_EXPANDED_SIZE` characters, and an alias inside the value it names.
A refused front matter is not metadata: the file still answers as text, with
`frontmatter_error` saying why, and its rendered document carries the same reason.

`tests/fixtures/frontmatter-bounds` holds `bomb.md`, seven anchors of nine aliases each
(9**7 values in 310 bytes of YAML); `loop.md`, an alias inside its own anchor;
`shared.md`, an anchor used twice within the bound; and `tags.md`, the tags JSON has no
type for.

## Test: an alias bomb answers as text with the reason

The answer has the file’s text and kind, no `frontmatter`, and the reason.

```console
$ metab docs --api '/api/file?path=bomb.md' > bomb.txt
? 0
```

```console
$ grep -E '^  "(type|kind|frontmatter|frontmatter_error)":' bomb.txt
  "type": "text",
  "kind": "markdown",
  "frontmatter_error": "Front matter not parsed: written out without its YAML aliases it is larger than 1,048,576 characters"
? 0
```

## Test: under the untrusted profile the document renders with the reason

The inert render shows the body, and names the refusal in its diagnostics and in the
document, where the Frontmatter disclosure would be.

```console
$ metab docs --untrusted --api '/api/kpress/render?path=bomb.md&view=document' > render.txt
? 0
```

```console
$ grep -E '^  "(type|inert)":|^      "(type|message)":' render.txt
  "type": "kpress-rendered-document",
      "type": "frontmatter_error",
      "message": "Front matter not parsed: written out without its YAML aliases it is larger than 1,048,576 characters",
  "inert": true,
? 0
```

```console
$ grep '^  "html":' render.txt
  "html": "\n<strong>Frontmatter error</strong><span>Front matter not parsed: written out without its YAML aliases it is larger than 1,048,576 characters</span><div><div><h1 id=\"user-content-seven-alias-levels\">Seven Alias Levels</h1>\n<p>The body still renders.</p></div></div>",
? 0
```

## Test: an alias inside its own anchor is refused

```console
$ metab docs --api '/api/file?path=loop.md' > loop.txt
? 0
```

```console
$ grep -E '^  "frontmatter' loop.txt
  "frontmatter_error": "Front matter not parsed: a YAML alias refers to a value that contains it"
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
