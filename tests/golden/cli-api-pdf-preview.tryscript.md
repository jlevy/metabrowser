---
sandbox: true
path:
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "WARNING"
  METABROWSER_SLOW_SERVER_MS: "60000"
  GIT_CONFIG_GLOBAL: "/dev/null"
  GIT_CONFIG_SYSTEM: "/dev/null"
before: >-
  unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_PREFIX GIT_NAMESPACE GIT_CEILING_DIRECTORIES &&
  mkdir -p papers &&
  printf '%%PDF-1.4\n%%\342\343\317\323\000\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Contents 4 0 R >>\nendobj\n4 0 obj\n<< /Length 33 >>\nstream\n0.2 0.4 0.8 rg 30 30 240 140 re f\nendstream\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%%%EOF\n' > papers/report.pdf &&
  cp papers/report.pdf papers/copy.pdf &&
  printf 'a text file named like a PDF\n' > papers/not-really.pdf &&
  printf '%%PDF-1.4\n%%\342\343\317\323\000\nnot an object at all\n' > papers/broken.pdf
---
# Golden tests: the PDF plugin’s preview routes

`/api/plugin/pdf/preview` says whether a PDF’s first-page preview is ready and where its
PNG is; `/api/plugin/pdf/preview-image` serves the PNG from the cache by the key the
first answered. The preview is drawn by PDFium in a child process
(`builtin_plugins/pdf/render_child.py`) and kept in the cache’s `plugins/pdf/previews/`
area under a key that hashes the content, the renderer’s version, and the size it was
fitted to.

Every command here serves a trusted folder, whose previews are drawn on every platform:
inside the macOS sandbox where the platform has one, and bare where it has none, which
is what threat model T7 admits for a trusted folder.
An untrusted source’s answer depends on the platform’s sandbox, so it is pinned in
`cli-ui-pdf-surfaces.tryscript.md`, recorded with the sandbox probe replaced, and in
`tests/test_pdf_preview_routes.py`.

Each render starts a child process, and the first request of each command probes the
sandbox with another, so how long a request takes is the machine’s load: at a load
average of 270 they took 2.5 to 7.9 s, past the slow-request warning’s threshold
(`METABROWSER_SLOW_SERVER_MS`), which this transcript raises so it pins the answers
alone. The render times are measured beside `PREVIEW_BOX` in
`builtin_plugins/pdf/preview.py`.

A key changes with every PDFium release, so each answer is saved and then printed with
its key as `<key>`; which answers share a key is what the shell comparisons say.
The PNG’s bytes are PDFium’s and are not pinned here: `tests/test_pdf_preview_routes.py`
decodes one.

## Test: a PDF’s first preview is drawn, and the next is the cache’s

The first answer was drawn by this request (`rendered`), fitted inside the 480 by 640
box; a second process finds it in the cache under the same key, and so does a file with
the same bytes under another name.

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab . --api '/api/plugin/pdf/preview?path=papers/report.pdf' > first.txt
? 0
```

```console
$ sed -E 's/[0-9a-f]{64}/<key>/g' first.txt
api: /api/plugin/pdf/preview?path=papers/report.pdf
status: 200
{
  "status": "ready",
  "key": "<key>",
  "width": 480,
  "height": 320,
  "pages": 1,
  "image": "/api/plugin/pdf/preview-image?key=<key>",
  "rendered": true
}
? 0
```

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab . --api '/api/plugin/pdf/preview?path=papers/copy.pdf' > copy.txt
? 0
```

```console
$ sed -E 's/[0-9a-f]{64}/<key>/g' copy.txt
api: /api/plugin/pdf/preview?path=papers/copy.pdf
status: 200
{
  "status": "ready",
  "key": "<key>",
  "width": 480,
  "height": 320,
  "pages": 1,
  "image": "/api/plugin/pdf/preview-image?key=<key>",
  "rendered": false
}
? 0
```

```console
$ [ "$(grep '"key"' first.txt)" = "$(grep '"key"' copy.txt)" ] && echo "one key for the same bytes" && ls cache/plugins/pdf/previews | sed -E 's/[0-9a-f]{64}/<key>/g'
one key for the same bytes
<key>.png
? 0
```

## Test: a changed file is a new preview under a new key

```console
$ sed -i.bak 's/0.2 0.4 0.8 rg/0.8 0.4 0.2 rg/' papers/report.pdf && rm papers/report.pdf.bak
? 0
```

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab . --api '/api/plugin/pdf/preview?path=papers/report.pdf' > after.txt
? 0
```

```console
$ grep '"rendered"' after.txt && [ "$(grep '"key"' first.txt)" != "$(grep '"key"' after.txt)" ] && echo "a new key" && ls cache/plugins/pdf/previews | wc -l | tr -d ' '
  "rendered": true
a new key
2
? 0
```

## Test: a file that is no PDF, or one PDFium cannot read, has no preview, and says why

The card then shows no image and still names and opens the file.

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab . --api '/api/plugin/pdf/preview?path=papers/not-really.pdf'
api: /api/plugin/pdf/preview?path=papers/not-really.pdf
status: 200
{
  "status": "unavailable",
  "reason": "not_a_pdf",
  "message": "This file does not begin as a PDF does."
}
? 0
```

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab . --api '/api/plugin/pdf/preview?path=papers/broken.pdf'
api: /api/plugin/pdf/preview?path=papers/broken.pdf
status: 200
{
  "status": "unavailable",
  "reason": "unreadable",
  "message": "This PDF could not be read."
}
? 0
```

## Test: a request that names nothing, or something that is not there, is refused

A preview names a served file by `path` or a blob of the served repository by `oid`,
exactly one of them; this folder is no repository, so it holds no blob.

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab . --api '/api/plugin/pdf/preview'
api: /api/plugin/pdf/preview
status: 400
{
  "code": "invalid_request",
  "message": "Name a file with path, or a blob with oid."
}
Error: /api/plugin/pdf/preview returned HTTP 400
? 1
```

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab . --api '/api/plugin/pdf/preview?path=papers/missing.pdf'
api: /api/plugin/pdf/preview?path=papers/missing.pdf
status: 404
{
  "code": "not_found",
  "message": "No file is there."
}
Error: /api/plugin/pdf/preview?path=papers/missing.pdf returned HTTP 404
? 1
```

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab . --api '/api/plugin/pdf/preview?oid=0123456789abcdef0123456789abcdef01234567'
api: /api/plugin/pdf/preview?oid=0123456789abcdef0123456789abcdef01234567
status: 404
{
  "code": "not_found",
  "message": "No blob is there."
}
Error: /api/plugin/pdf/preview?oid=0123456789abcdef0123456789abcdef01234567 returned HTTP 404
? 1
```

## Test: the image route serves a kept preview, and only a key of its form

The PNG follows the status line, as `--api` prints a body that is not JSON: as text,
with each byte that is not UTF-8 replaced.
Its signature’s `PNG` and its header chunk’s name read through.
Its headers (an image type, `nosniff`, a policy that runs and frames nothing, an
immutable cache life) are `tests/test_pdf_preview_routes.py`’s.

```console
$ sed -n -E 's/.*"key": "([0-9a-f]{64})".*/\1/p' copy.txt > key.txt && wc -l < key.txt | tr -d ' '
1
? 0
```

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab . --api "/api/plugin/pdf/preview-image?key=$(cat key.txt)" > image.txt
? 0
```

```console
$ sed -n '1,2p' image.txt | sed -E 's/[0-9a-f]{64}/<key>/g' && sed -n '3,$p' image.txt | grep -a -o -E 'PNG|IHDR' | head -2
api: /api/plugin/pdf/preview-image?key=<key>
status: 200
PNG
IHDR
? 0
```

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab . --api '/api/plugin/pdf/preview-image?key=not-a-key'
api: /api/plugin/pdf/preview-image?key=not-a-key
status: 400
This preview address is invalid.
Error: /api/plugin/pdf/preview-image?key=not-a-key returned HTTP 400
? 1
```

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab . --api '/api/plugin/pdf/preview-image?key=0000000000000000000000000000000000000000000000000000000000000000'
api: /api/plugin/pdf/preview-image?key=0000000000000000000000000000000000000000000000000000000000000000
status: 404
No preview is kept under this key.
Error: /api/plugin/pdf/preview-image?key=0000000000000000000000000000000000000000000000000000000000000000 returned HTTP 404
? 1
```
