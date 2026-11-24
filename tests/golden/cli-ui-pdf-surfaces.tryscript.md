---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: PDF Surfaces

What a reader sees of a PDF on every surface Metabrowser shows one, from what the server
serves there. Every answer the session reads is one the in-process application gave,
recorded in `tests/fixtures/pdf-surfaces-responses.json` by
`tests/test_pdf_surfaces_session.py`, which fails when the server answers differently.

The surfaces are a trusted folder, a folder served `--untrusted`, and a pinned revision,
which is what every GitHub repository and pull request is.
Each is read in a browser and in the macOS app, whose host descriptor is the only
difference. The PDFs are one with NUL bytes, as real writers’ are; one whose bytes are
all ASCII; one with no extension; and a text file named `.pdf`. The last commit of the
pin adds them, and its comparison is what a commit’s diff or a pull request’s Changes
draws.

`seen` is the transcript a reviewer reads, one line per file per surface:

- **`viewer`:** the browser’s own PDF viewer inline.
  A view draws it only on a page whose content policy admits it: a trusted folder’s.
- **`note`:** the untrusted note in its place, on every page served with
  `object-src 'none'`: an `--untrusted` folder and every pin.
  A PDF is a click away there, through Open in new tab in a browser or Open in the app.
- **Each action:** its label, and the status and type the server answers at the address
  it links to. Every one is `application/pdf`, the extensionless PDF’s too, because
  `/raw` takes a type from a file’s leading bytes when its name gives none
  (`content_sniff.media_type_from_prefix`); with `nosniff` a browser would otherwise
  download it.
- **`diff`:** a comparison shows a PDF as Git diffs it.
  A binary PDF says “Binary file; no textual diff.”, as GitHub’s Files changed does, and
  an all-ASCII one is a text diff.
  Its own view is the file bar’s View file, pinned in
  `cli-ui-diff-view-file.tryscript.md`.

A `.pdf` that is not a PDF is still drawn as one, since the `pdf` plugin claims the
name, and the browser’s viewer says it cannot open it.
In the app, Open on the extensionless PDF reaches the app’s type check, which reads a
file by its name and refuses it.
The browser’s painting of a PDF is Chrome’s (`tests/test_pdf_preview_chrome.py`).

```console
$ node tests/dom/pdf-surfaces-session.js
{
  "seen": [
    "folder · browser · papers/report.pdf: viewer. Download → 200 application/pdf; Open in new tab → 200 application/pdf",
    "folder · browser · papers/ascii.pdf: viewer. Download → 200 application/pdf; Open in new tab → 200 application/pdf",
    "folder · browser · scans/untitled: viewer. Download → 200 application/pdf; Open in new tab → 200 application/pdf",
    "folder · browser · notes/not-really.pdf: viewer. Download → 200 application/pdf; Open in new tab → 200 application/pdf",
    "folder · app · papers/report.pdf: viewer. Open → 200 application/pdf; Download → 200 application/pdf",
    "folder · app · papers/ascii.pdf: viewer. Open → 200 application/pdf; Download → 200 application/pdf",
    "folder · app · scans/untitled: viewer. Open → 200 application/pdf; Download → 200 application/pdf",
    "folder · app · notes/not-really.pdf: viewer. Open → 200 application/pdf; Download → 200 application/pdf",
    "folderUntrusted · browser · papers/report.pdf: note. Download → 200 application/pdf; Open in new tab → 200 application/pdf",
    "folderUntrusted · browser · papers/ascii.pdf: note. Download → 200 application/pdf; Open in new tab → 200 application/pdf",
    "folderUntrusted · browser · scans/untitled: note. Download → 200 application/pdf; Open in new tab → 200 application/pdf",
    "folderUntrusted · browser · notes/not-really.pdf: note. Download → 200 application/pdf; Open in new tab → 200 application/pdf",
    "folderUntrusted · app · papers/report.pdf: note. Open → 200 application/pdf; Download → 200 application/pdf",
    "folderUntrusted · app · papers/ascii.pdf: note. Open → 200 application/pdf; Download → 200 application/pdf",
    "folderUntrusted · app · scans/untitled: note. Open → 200 application/pdf; Download → 200 application/pdf",
    "folderUntrusted · app · notes/not-really.pdf: note. Open → 200 application/pdf; Download → 200 application/pdf",
    "pin · browser · papers/report.pdf: note. Download → 200 application/pdf; Open in new tab → 200 application/pdf",
    "pin · browser · papers/ascii.pdf: note. Download → 200 application/pdf; Open in new tab → 200 application/pdf",
    "pin · browser · scans/untitled: note. Download → 200 application/pdf; Open in new tab → 200 application/pdf",
    "pin · browser · notes/not-really.pdf: note. Download → 200 application/pdf; Open in new tab → 200 application/pdf",
    "pin · app · papers/report.pdf: note. Open → 200 application/pdf; Download → 200 application/pdf",
    "pin · app · papers/ascii.pdf: note. Open → 200 application/pdf; Download → 200 application/pdf",
    "pin · app · scans/untitled: note. Open → 200 application/pdf; Download → 200 application/pdf",
    "pin · app · notes/not-really.pdf: note. Open → 200 application/pdf; Download → 200 application/pdf",
    "diff · modified README.md: text diff",
    "diff · added notes/not-really.pdf: text diff",
    "diff · added papers/ascii.pdf: text diff",
    "diff · added papers/report.pdf: Binary file; no textual diff.",
    "diff · added scans/untitled: Binary file; no textual diff."
  ],
  "surfaces": [
    {
      "surface": "folder",
      "host": "browser",
      "served": {
        "sourceKind": "filesystem",
        "activeContent": true,
        "objectPolicy": "admits /raw"
      },
      "files": {
        "papers/report.pdf": {
          "kind": "pdf",
          "view": "preview",
          "shows": "viewer",
          "policyAdmitsViewer": true,
          "actions": [
            {
              "label": "Download",
              "href": "/raw?path=papers%2Freport.pdf",
              "download": "report.pdf",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.4"
              }
            },
            {
              "label": "Open in new tab",
              "href": "/raw?path=papers%2Freport.pdf",
              "target": "_blank",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.4"
              }
            }
          ]
        },
        "papers/ascii.pdf": {
          "kind": "pdf",
          "view": "preview",
          "shows": "viewer",
          "policyAdmitsViewer": true,
          "actions": [
            {
              "label": "Download",
              "href": "/raw?path=papers%2Fascii.pdf",
              "download": "ascii.pdf",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.7"
              }
            },
            {
              "label": "Open in new tab",
              "href": "/raw?path=papers%2Fascii.pdf",
              "target": "_blank",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.7"
              }
            }
          ]
        },
        "scans/untitled": {
          "kind": "pdf",
          "view": "preview",
          "shows": "viewer",
          "policyAdmitsViewer": true,
          "actions": [
            {
              "label": "Download",
              "href": "/raw?path=scans%2Funtitled",
              "download": "untitled",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.4"
              }
            },
            {
              "label": "Open in new tab",
              "href": "/raw?path=scans%2Funtitled",
              "target": "_blank",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.4"
              }
            }
          ]
        },
        "notes/not-really.pdf": {
          "kind": "pdf",
          "view": "preview",
          "shows": "viewer",
          "policyAdmitsViewer": true,
          "actions": [
            {
              "label": "Download",
              "href": "/raw?path=notes%2Fnot-really.pdf",
              "download": "not-really.pdf",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "a text f"
              }
            },
            {
              "label": "Open in new tab",
              "href": "/raw?path=notes%2Fnot-really.pdf",
              "target": "_blank",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "a text f"
              }
            }
          ]
        }
      }
    },
    {
      "surface": "folder",
      "host": "app",
      "served": {
        "sourceKind": "filesystem",
        "activeContent": true,
        "objectPolicy": "admits /raw"
      },
      "files": {
        "papers/report.pdf": {
          "kind": "pdf",
          "view": "preview",
          "shows": "viewer",
          "policyAdmitsViewer": true,
          "actions": [
            {
              "label": "Open",
              "href": "/raw?path=papers%2Freport.pdf",
              "download": "report.pdf",
              "opensInApp": "filesystem",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.4"
              }
            },
            {
              "label": "Download",
              "href": "/raw?path=papers%2Freport.pdf",
              "download": "report.pdf",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.4"
              }
            }
          ]
        },
        "papers/ascii.pdf": {
          "kind": "pdf",
          "view": "preview",
          "shows": "viewer",
          "policyAdmitsViewer": true,
          "actions": [
            {
              "label": "Open",
              "href": "/raw?path=papers%2Fascii.pdf",
              "download": "ascii.pdf",
              "opensInApp": "filesystem",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.7"
              }
            },
            {
              "label": "Download",
              "href": "/raw?path=papers%2Fascii.pdf",
              "download": "ascii.pdf",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.7"
              }
            }
          ]
        },
        "scans/untitled": {
          "kind": "pdf",
          "view": "preview",
          "shows": "viewer",
          "policyAdmitsViewer": true,
          "actions": [
            {
              "label": "Open",
              "href": "/raw?path=scans%2Funtitled",
              "download": "untitled",
              "opensInApp": "filesystem",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.4"
              }
            },
            {
              "label": "Download",
              "href": "/raw?path=scans%2Funtitled",
              "download": "untitled",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.4"
              }
            }
          ]
        },
        "notes/not-really.pdf": {
          "kind": "pdf",
          "view": "preview",
          "shows": "viewer",
          "policyAdmitsViewer": true,
          "actions": [
            {
              "label": "Open",
              "href": "/raw?path=notes%2Fnot-really.pdf",
              "download": "not-really.pdf",
              "opensInApp": "filesystem",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "a text f"
              }
            },
            {
              "label": "Download",
              "href": "/raw?path=notes%2Fnot-really.pdf",
              "download": "not-really.pdf",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "a text f"
              }
            }
          ]
        }
      }
    },
    {
      "surface": "folderUntrusted",
      "host": "browser",
      "served": {
        "sourceKind": "filesystem",
        "activeContent": false,
        "objectPolicy": "blocks embedding"
      },
      "files": {
        "papers/report.pdf": {
          "kind": "pdf",
          "view": "preview",
          "shows": "note",
          "note": "This source is untrusted, so its PDFs are not shown inline. Open in new tab shows this one.",
          "actions": [
            {
              "label": "Download",
              "href": "/raw?path=papers%2Freport.pdf",
              "download": "report.pdf",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.4"
              }
            },
            {
              "label": "Open in new tab",
              "href": "/raw?path=papers%2Freport.pdf",
              "target": "_blank",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.4"
              }
            }
          ]
        },
        "papers/ascii.pdf": {
          "kind": "pdf",
          "view": "preview",
          "shows": "note",
          "note": "This source is untrusted, so its PDFs are not shown inline. Open in new tab shows this one.",
          "actions": [
            {
              "label": "Download",
              "href": "/raw?path=papers%2Fascii.pdf",
              "download": "ascii.pdf",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.7"
              }
            },
            {
              "label": "Open in new tab",
              "href": "/raw?path=papers%2Fascii.pdf",
              "target": "_blank",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.7"
              }
            }
          ]
        },
        "scans/untitled": {
          "kind": "pdf",
          "view": "preview",
          "shows": "note",
          "note": "This source is untrusted, so its PDFs are not shown inline. Open in new tab shows this one.",
          "actions": [
            {
              "label": "Download",
              "href": "/raw?path=scans%2Funtitled",
              "download": "untitled",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.4"
              }
            },
            {
              "label": "Open in new tab",
              "href": "/raw?path=scans%2Funtitled",
              "target": "_blank",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.4"
              }
            }
          ]
        },
        "notes/not-really.pdf": {
          "kind": "pdf",
          "view": "preview",
          "shows": "note",
          "note": "This source is untrusted, so its PDFs are not shown inline. Open in new tab shows this one.",
          "actions": [
            {
              "label": "Download",
              "href": "/raw?path=notes%2Fnot-really.pdf",
              "download": "not-really.pdf",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "a text f"
              }
            },
            {
              "label": "Open in new tab",
              "href": "/raw?path=notes%2Fnot-really.pdf",
              "target": "_blank",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "a text f"
              }
            }
          ]
        }
      }
    },
    {
      "surface": "folderUntrusted",
      "host": "app",
      "served": {
        "sourceKind": "filesystem",
        "activeContent": false,
        "objectPolicy": "blocks embedding"
      },
      "files": {
        "papers/report.pdf": {
          "kind": "pdf",
          "view": "preview",
          "shows": "note",
          "note": "This source is untrusted, so its PDFs are not shown inline. Open shows this one.",
          "actions": [
            {
              "label": "Open",
              "href": "/raw?path=papers%2Freport.pdf",
              "download": "report.pdf",
              "opensInApp": "filesystem",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.4"
              }
            },
            {
              "label": "Download",
              "href": "/raw?path=papers%2Freport.pdf",
              "download": "report.pdf",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.4"
              }
            }
          ]
        },
        "papers/ascii.pdf": {
          "kind": "pdf",
          "view": "preview",
          "shows": "note",
          "note": "This source is untrusted, so its PDFs are not shown inline. Open shows this one.",
          "actions": [
            {
              "label": "Open",
              "href": "/raw?path=papers%2Fascii.pdf",
              "download": "ascii.pdf",
              "opensInApp": "filesystem",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.7"
              }
            },
            {
              "label": "Download",
              "href": "/raw?path=papers%2Fascii.pdf",
              "download": "ascii.pdf",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.7"
              }
            }
          ]
        },
        "scans/untitled": {
          "kind": "pdf",
          "view": "preview",
          "shows": "note",
          "note": "This source is untrusted, so its PDFs are not shown inline. Open shows this one.",
          "actions": [
            {
              "label": "Open",
              "href": "/raw?path=scans%2Funtitled",
              "download": "untitled",
              "opensInApp": "filesystem",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.4"
              }
            },
            {
              "label": "Download",
              "href": "/raw?path=scans%2Funtitled",
              "download": "untitled",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.4"
              }
            }
          ]
        },
        "notes/not-really.pdf": {
          "kind": "pdf",
          "view": "preview",
          "shows": "note",
          "note": "This source is untrusted, so its PDFs are not shown inline. Open shows this one.",
          "actions": [
            {
              "label": "Open",
              "href": "/raw?path=notes%2Fnot-really.pdf",
              "download": "not-really.pdf",
              "opensInApp": "filesystem",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "a text f"
              }
            },
            {
              "label": "Download",
              "href": "/raw?path=notes%2Fnot-really.pdf",
              "download": "not-really.pdf",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "a text f"
              }
            }
          ]
        }
      }
    },
    {
      "surface": "pin",
      "host": "browser",
      "served": {
        "sourceKind": "git_revision",
        "activeContent": false,
        "objectPolicy": "blocks embedding"
      },
      "files": {
        "papers/report.pdf": {
          "kind": "pdf",
          "view": "preview",
          "shows": "note",
          "note": "This source is untrusted, so its PDFs are not shown inline. Open in new tab shows this one.",
          "actions": [
            {
              "label": "Download",
              "href": "/raw?path=g1-cGFwZXJz%2Fg1-cmVwb3J0LnBkZg",
              "download": "report.pdf",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.4"
              }
            },
            {
              "label": "Open in new tab",
              "href": "/raw?path=g1-cGFwZXJz%2Fg1-cmVwb3J0LnBkZg",
              "target": "_blank",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.4"
              }
            }
          ]
        },
        "papers/ascii.pdf": {
          "kind": "pdf",
          "view": "preview",
          "shows": "note",
          "note": "This source is untrusted, so its PDFs are not shown inline. Open in new tab shows this one.",
          "actions": [
            {
              "label": "Download",
              "href": "/raw?path=g1-cGFwZXJz%2Fg1-YXNjaWkucGRm",
              "download": "ascii.pdf",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.7"
              }
            },
            {
              "label": "Open in new tab",
              "href": "/raw?path=g1-cGFwZXJz%2Fg1-YXNjaWkucGRm",
              "target": "_blank",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.7"
              }
            }
          ]
        },
        "scans/untitled": {
          "kind": "pdf",
          "view": "preview",
          "shows": "note",
          "note": "This source is untrusted, so its PDFs are not shown inline. Open in new tab shows this one.",
          "actions": [
            {
              "label": "Download",
              "href": "/raw?path=g1-c2NhbnM%2Fg1-dW50aXRsZWQ",
              "download": "untitled",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.4"
              }
            },
            {
              "label": "Open in new tab",
              "href": "/raw?path=g1-c2NhbnM%2Fg1-dW50aXRsZWQ",
              "target": "_blank",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.4"
              }
            }
          ]
        },
        "notes/not-really.pdf": {
          "kind": "pdf",
          "view": "preview",
          "shows": "note",
          "note": "This source is untrusted, so its PDFs are not shown inline. Open in new tab shows this one.",
          "actions": [
            {
              "label": "Download",
              "href": "/raw?path=g1-bm90ZXM%2Fg1-bm90LXJlYWxseS5wZGY",
              "download": "not-really.pdf",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "a text f"
              }
            },
            {
              "label": "Open in new tab",
              "href": "/raw?path=g1-bm90ZXM%2Fg1-bm90LXJlYWxseS5wZGY",
              "target": "_blank",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "a text f"
              }
            }
          ]
        }
      }
    },
    {
      "surface": "pin",
      "host": "app",
      "served": {
        "sourceKind": "git_revision",
        "activeContent": false,
        "objectPolicy": "blocks embedding"
      },
      "files": {
        "papers/report.pdf": {
          "kind": "pdf",
          "view": "preview",
          "shows": "note",
          "note": "This source is untrusted, so its PDFs are not shown inline. Open shows this one.",
          "actions": [
            {
              "label": "Open",
              "href": "/raw?path=g1-cGFwZXJz%2Fg1-cmVwb3J0LnBkZg",
              "download": "report.pdf",
              "opensInApp": "git_revision",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.4"
              }
            },
            {
              "label": "Download",
              "href": "/raw?path=g1-cGFwZXJz%2Fg1-cmVwb3J0LnBkZg",
              "download": "report.pdf",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.4"
              }
            }
          ]
        },
        "papers/ascii.pdf": {
          "kind": "pdf",
          "view": "preview",
          "shows": "note",
          "note": "This source is untrusted, so its PDFs are not shown inline. Open shows this one.",
          "actions": [
            {
              "label": "Open",
              "href": "/raw?path=g1-cGFwZXJz%2Fg1-YXNjaWkucGRm",
              "download": "ascii.pdf",
              "opensInApp": "git_revision",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.7"
              }
            },
            {
              "label": "Download",
              "href": "/raw?path=g1-cGFwZXJz%2Fg1-YXNjaWkucGRm",
              "download": "ascii.pdf",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.7"
              }
            }
          ]
        },
        "scans/untitled": {
          "kind": "pdf",
          "view": "preview",
          "shows": "note",
          "note": "This source is untrusted, so its PDFs are not shown inline. Open shows this one.",
          "actions": [
            {
              "label": "Open",
              "href": "/raw?path=g1-c2NhbnM%2Fg1-dW50aXRsZWQ",
              "download": "untitled",
              "opensInApp": "git_revision",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.4"
              }
            },
            {
              "label": "Download",
              "href": "/raw?path=g1-c2NhbnM%2Fg1-dW50aXRsZWQ",
              "download": "untitled",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "%PDF-1.4"
              }
            }
          ]
        },
        "notes/not-really.pdf": {
          "kind": "pdf",
          "view": "preview",
          "shows": "note",
          "note": "This source is untrusted, so its PDFs are not shown inline. Open shows this one.",
          "actions": [
            {
              "label": "Open",
              "href": "/raw?path=g1-bm90ZXM%2Fg1-bm90LXJlYWxseS5wZGY",
              "download": "not-really.pdf",
              "opensInApp": "git_revision",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "a text f"
              }
            },
            {
              "label": "Download",
              "href": "/raw?path=g1-bm90ZXM%2Fg1-bm90LXJlYWxseS5wZGY",
              "download": "not-really.pdf",
              "answer": {
                "status": 200,
                "type": "application/pdf",
                "head": "a text f"
              }
            }
          ]
        }
      }
    }
  ],
  "pinComparison": [
    {
      "path": "README.md",
      "change": "modified",
      "binary": false,
      "availability": "ready",
      "lines": "+2 −0",
      "body": "text diff"
    },
    {
      "path": "notes/not-really.pdf",
      "change": "added",
      "binary": false,
      "availability": "ready",
      "lines": "+1 −0",
      "body": "text diff"
    },
    {
      "path": "papers/ascii.pdf",
      "change": "added",
      "binary": false,
      "availability": "ready",
      "lines": "+5 −0",
      "body": "text diff"
    },
    {
      "path": "papers/report.pdf",
      "change": "added",
      "binary": true,
      "availability": "binary",
      "lines": null,
      "body": "Binary file; no textual diff."
    },
    {
      "path": "scans/untitled",
      "change": "added",
      "binary": true,
      "availability": "binary",
      "lines": null,
      "body": "Binary file; no textual diff."
    }
  ]
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
