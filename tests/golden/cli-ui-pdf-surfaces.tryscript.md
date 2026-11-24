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

- **`viewer`:** the browser’s own PDF viewer inline, on every surface’s file page.
  A view draws it only on a page whose content policy admits it, which `embedPolicy`
  names: a trusted folder’s page has no policy, and an `--untrusted` folder’s and every
  pin’s admit an object from `/raw` alone (`object-src <origin>/raw`), whose every
  answer carries its own sandbox.
  The threat this answers is in `docs/project/architecture/arch-threat-model.md`.
- **Each action:** its label, and the status and type the server answers at the address
  it links to. Every one is `application/pdf`, the extensionless PDF’s too, because
  `/raw` takes a type from a file’s leading bytes when its name gives none
  (`content_sniff.media_type_from_prefix`); with `nosniff` a browser would otherwise
  download it.
- **`another view`:** a file the `pdf` plugin does not claim, with its kind and view.
  A text file named `.pdf` is text: the plugin claims a `.pdf` that sniffs as text only
  when it starts with `%PDF-`, so the reader gets its source, not a viewer that cannot
  open it.
- **`diff`:** a comparison shows a PDF as Git diffs it.
  A binary PDF says “Binary file; no textual diff.”, as GitHub’s Files changed does, and
  an all-ASCII one is a text diff.
  Its own view is the file bar’s View file, pinned in
  `cli-ui-diff-view-file.tryscript.md`.

A diff draws no PDF viewer at all, so a heavy comparison never grows one per changed
PDF: the last line says the mounted diff holds no embed, object, or iframe, which the
session asserts. In the app, Open on the extensionless PDF reaches the app’s type check,
which reads a file by its name and refuses it.
The browser’s painting of a PDF is Chrome’s (`tests/test_pdf_preview_chrome.py`).

```console
$ node tests/dom/pdf-surfaces-session.js
{
  "seen": [
    "folder · browser · papers/report.pdf: viewer. Download → 200 application/pdf; Open in new tab → 200 application/pdf",
    "folder · browser · papers/ascii.pdf: viewer. Download → 200 application/pdf; Open in new tab → 200 application/pdf",
    "folder · browser · scans/untitled: viewer. Download → 200 application/pdf; Open in new tab → 200 application/pdf",
    "folder · browser · notes/not-really.pdf: another view (text, the source view)",
    "folder · app · papers/report.pdf: viewer. Open → 200 application/pdf; Download → 200 application/pdf",
    "folder · app · papers/ascii.pdf: viewer. Open → 200 application/pdf; Download → 200 application/pdf",
    "folder · app · scans/untitled: viewer. Open → 200 application/pdf; Download → 200 application/pdf",
    "folder · app · notes/not-really.pdf: another view (text, the source view)",
    "folderUntrusted · browser · papers/report.pdf: viewer. Download → 200 application/pdf; Open in new tab → 200 application/pdf",
    "folderUntrusted · browser · papers/ascii.pdf: viewer. Download → 200 application/pdf; Open in new tab → 200 application/pdf",
    "folderUntrusted · browser · scans/untitled: viewer. Download → 200 application/pdf; Open in new tab → 200 application/pdf",
    "folderUntrusted · browser · notes/not-really.pdf: another view (text, the source view)",
    "folderUntrusted · app · papers/report.pdf: viewer. Open → 200 application/pdf; Download → 200 application/pdf",
    "folderUntrusted · app · papers/ascii.pdf: viewer. Open → 200 application/pdf; Download → 200 application/pdf",
    "folderUntrusted · app · scans/untitled: viewer. Open → 200 application/pdf; Download → 200 application/pdf",
    "folderUntrusted · app · notes/not-really.pdf: another view (text, the source view)",
    "pin · browser · papers/report.pdf: viewer. Download → 200 application/pdf; Open in new tab → 200 application/pdf",
    "pin · browser · papers/ascii.pdf: viewer. Download → 200 application/pdf; Open in new tab → 200 application/pdf",
    "pin · browser · scans/untitled: viewer. Download → 200 application/pdf; Open in new tab → 200 application/pdf",
    "pin · browser · notes/not-really.pdf: another view (text, the source view)",
    "pin · app · papers/report.pdf: viewer. Open → 200 application/pdf; Download → 200 application/pdf",
    "pin · app · papers/ascii.pdf: viewer. Open → 200 application/pdf; Download → 200 application/pdf",
    "pin · app · scans/untitled: viewer. Open → 200 application/pdf; Download → 200 application/pdf",
    "pin · app · notes/not-really.pdf: another view (text, the source view)",
    "diff · modified README.md: text diff",
    "diff · added notes/not-really.pdf: text diff",
    "diff · added papers/ascii.pdf: text diff",
    "diff · added papers/report.pdf: Binary file; no textual diff.",
    "diff · added scans/untitled: Binary file; no textual diff.",
    "diff · draws no embed, object, or iframe"
  ],
  "surfaces": [
    {
      "surface": "folder",
      "host": "browser",
      "served": {
        "sourceKind": "filesystem",
        "activeContent": true,
        "embedPolicy": "admits this origin"
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
          "kind": "text",
          "view": "source",
          "shows": "another view"
        }
      }
    },
    {
      "surface": "folder",
      "host": "app",
      "served": {
        "sourceKind": "filesystem",
        "activeContent": true,
        "embedPolicy": "admits this origin"
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
          "kind": "text",
          "view": "source",
          "shows": "another view"
        }
      }
    },
    {
      "surface": "folderUntrusted",
      "host": "browser",
      "served": {
        "sourceKind": "filesystem",
        "activeContent": false,
        "embedPolicy": "admits /raw only"
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
          "kind": "text",
          "view": "source",
          "shows": "another view"
        }
      }
    },
    {
      "surface": "folderUntrusted",
      "host": "app",
      "served": {
        "sourceKind": "filesystem",
        "activeContent": false,
        "embedPolicy": "admits /raw only"
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
          "kind": "text",
          "view": "source",
          "shows": "another view"
        }
      }
    },
    {
      "surface": "pin",
      "host": "browser",
      "served": {
        "sourceKind": "git_revision",
        "activeContent": false,
        "embedPolicy": "admits /raw only"
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
          "shows": "viewer",
          "policyAdmitsViewer": true,
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
          "shows": "viewer",
          "policyAdmitsViewer": true,
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
          "kind": "text",
          "view": "source",
          "shows": "another view"
        }
      }
    },
    {
      "surface": "pin",
      "host": "app",
      "served": {
        "sourceKind": "git_revision",
        "activeContent": false,
        "embedPolicy": "admits /raw only"
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
          "shows": "viewer",
          "policyAdmitsViewer": true,
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
          "shows": "viewer",
          "policyAdmitsViewer": true,
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
          "kind": "text",
          "view": "source",
          "shows": "another view"
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
