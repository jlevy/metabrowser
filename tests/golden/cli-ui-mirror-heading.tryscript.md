---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Root details and mirror headings

The root menu shows file totals, the local path, and a short note about the mirror.
The main heading shows where the mirror is kept.
This session runs the production formatters and view headers on recorded server output
for a folder, a mirror, and a mirror whose path contains markup and a directional
control character.

```console
$ node tests/dom/mirror-heading-session.js
[
  {
    "subject": "folder",
    "kind": "filesystem",
    "status": {
      "name": null,
      "origin": null,
      "location": null,
      "pin": null,
      "ref_name": null
    },
    "title": {
      "served": "squares • Metabrowser",
      "afterEveryStep": "squares • Metabrowser",
      "writes": []
    },
    "navigationHeading": {
      "html": "<span class=\"path\"><span class=\"path-base\">squares</span></span>",
      "text": "squares"
    },
    "mainHeading": {
      "root": "↑ ~/wrk squares",
      "file": {
        "html": "<button type=\"button\" class=\"icon-btn folder-up\" data-tip-text=\"Open docs/\" aria-label=\"Open parent folder docs/\" data-nav-dir=\"docs\" data-mb-owner><span class=\"parent-nav-arrow\" aria-hidden=\"true\">↑</span></button><span class=\"file-header-path folder-breadcrumb\"><button type=\"button\" class=\"folder-crumb folder-crumb-root\" data-nav-dir=\"\" data-mb-owner data-tip-text=\"~/wrk/squares\"><bdi>~/wrk/squares</bdi></button><span class=\"folder-crumb-sep\">/</span><button type=\"button\" class=\"folder-crumb\" data-nav-dir=\"docs\" data-mb-owner data-tip-text=\"docs\">docs</button><span class=\"folder-crumb-sep\">/</span></span>",
        "text": "↑ ~/wrk/squares / docs /",
        "title": "guide.md"
      },
      "fileHeaders": {
        "a served file": {
          "icon": "icon-for-guide.md",
          "title": "guide.md",
          "line": "140 B · 3d ago",
          "lineParts": [
            "view-header-item",
            "view-header-item"
          ],
          "pending": false
        },
        "a compressed file": {
          "icon": "icon-for-run.log",
          "title": "run.log.gz",
          "line": "Gzip 2.0 KB · 3d ago",
          "lineParts": [
            "file-header-badge badge-compressed",
            "view-header-item",
            "view-header-item"
          ],
          "pending": false
        },
        "a pending time": {
          "icon": "icon-for-guide.md",
          "title": "guide.md",
          "line": "140 B ·",
          "lineParts": [
            "view-header-item",
            "view-header-item"
          ],
          "pending": true
        }
      }
    },
    "details": {
      "location": "~/wrk/squares",
      "source": null,
      "before": "",
      "after": "3 files 140 bytes"
    }
  },
  {
    "subject": "mirror",
    "kind": "git_revision",
    "status": {
      "name": "squares",
      "origin": "file://~/git/squares.git",
      "location": "~/.cache/metabrowser/repos/store-key-1/repository.git",
      "pin": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
      "ref_name": "topic"
    },
    "title": {
      "served": "squares • Metabrowser",
      "afterEveryStep": "squares • Metabrowser",
      "writes": []
    },
    "navigationHeading": {
      "html": "<span class=\"path\"><span class=\"path-base\">squares</span></span>",
      "text": "squares"
    },
    "mainHeading": {
      "root": "↑ mirror in ~/.cache/metabrowser/repos/store-key-1 squares",
      "file": {
        "html": "<button type=\"button\" class=\"icon-btn folder-up\" data-tip-text=\"Open docs/\" aria-label=\"Open parent folder docs/\" data-nav-dir=\"g1-ZG9jcw\" data-mb-owner><span class=\"parent-nav-arrow\" aria-hidden=\"true\">↑</span></button><span class=\"file-header-path folder-breadcrumb\"><button type=\"button\" class=\"folder-crumb folder-crumb-root\" data-nav-dir=\"\" data-mb-owner data-tip-text=\"squares\"><bdi>squares</bdi></button><span class=\"folder-crumb-sep\">/</span><button type=\"button\" class=\"folder-crumb\" data-nav-dir=\"g1-ZG9jcw\" data-mb-owner data-tip-text=\"docs\">docs</button><span class=\"folder-crumb-sep\">/</span><span class=\"file-header-mirror\"><span class=\"file-header-mirror-text\">mirror in ~/.cache/metabrowser/repos/store-key-1</span></span></span>",
        "text": "↑ squares / docs / mirror in ~/.cache/metabrowser/repos/store-key-1",
        "title": "guide.md"
      },
      "fileHeaders": {
        "a pin's file": {
          "icon": "icon-for-guide.md",
          "title": "guide.md",
          "line": "140 B",
          "lineParts": [
            "view-header-item"
          ],
          "pending": false
        }
      }
    },
    "details": {
      "location": "~/.cache/metabrowser/repos/store-key-1/repository.git",
      "source": "Bare Git mirror with no checked-out files.",
      "before": "",
      "after": "3 files 140 bytes"
    }
  },
  {
    "subject": "hostile",
    "kind": "git_revision",
    "status": {
      "name": "a<b>&�x",
      "origin": "file://~/git/a%3Cb%3E&%E2%80%AEx.git",
      "location": "~/odd\"<&>home/repos/store-key-2/repository.git",
      "pin": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
      "ref_name": "topic"
    },
    "title": {
      "served": "a<b>&�x • Metabrowser",
      "afterEveryStep": "a<b>&�x • Metabrowser",
      "writes": []
    },
    "navigationHeading": {
      "html": "<span class=\"path\"><span class=\"path-base\">a&lt;b&gt;&amp;�x</span></span>",
      "text": "a<b>&�x"
    },
    "mainHeading": {
      "root": "↑ mirror in ~/odd\"<&>home/repos/store-key-2 a<b>&�x",
      "file": {
        "html": "<button type=\"button\" class=\"icon-btn folder-up\" data-tip-text=\"Open docs/\" aria-label=\"Open parent folder docs/\" data-nav-dir=\"g1-ZG9jcw\" data-mb-owner><span class=\"parent-nav-arrow\" aria-hidden=\"true\">↑</span></button><span class=\"file-header-path folder-breadcrumb\"><button type=\"button\" class=\"folder-crumb folder-crumb-root\" data-nav-dir=\"\" data-mb-owner data-tip-text=\"a&lt;b&gt;&amp;�x\"><bdi>a&lt;b&gt;&amp;�x</bdi></button><span class=\"folder-crumb-sep\">/</span><button type=\"button\" class=\"folder-crumb\" data-nav-dir=\"g1-ZG9jcw\" data-mb-owner data-tip-text=\"docs\">docs</button><span class=\"folder-crumb-sep\">/</span><span class=\"file-header-mirror\"><span class=\"file-header-mirror-text\">mirror in ~/odd&quot;&lt;&amp;&gt;home/repos/store-key-2</span></span></span>",
        "text": "↑ a<b>&�x / docs / mirror in ~/odd\"<&>home/repos/store-key-2",
        "title": "guide.md"
      },
      "fileHeaders": {
        "a pin's file": {
          "icon": "icon-for-guide.md",
          "title": "guide.md",
          "line": "140 B",
          "lineParts": [
            "view-header-item"
          ],
          "pending": false
        }
      }
    },
    "details": {
      "location": "~/odd\"<&>home/repos/store-key-2/repository.git",
      "source": "Bare Git mirror with no checked-out files.",
      "before": "",
      "after": "3 files 140 bytes"
    }
  }
]
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
