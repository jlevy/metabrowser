---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: A Mirror’s Heading

A folder’s page is headed by the folder’s name, and its main heading starts with the
folder’s path. A page served from a mirror showed the full commit ID in both places, and
said nowhere that its files came out of the cache.
It is now headed by the repository’s name, as a checkout of it would be called, with the
ref and the short commit beside it and a control that copies the full commit, and its
main heading ends with a note that says where the mirror is kept.

The mirror is a bare Git repository, and each page is read from a Git object at the
pinned commit, so no folder holds these files.
The note therefore stands after the address and never as its start, and the tooltip on
the name and on the note says what the directory is: the origin, the full commit, the
location, and that nothing is checked out.

This browserless session is a page for each of three subjects the in-process application
served: a folder, a mirror, and a mirror whose origin has markup and U+202E
RIGHT-TO-LEFT OVERRIDE in its name and whose application home has markup in its own.
That input is `tests/fixtures/mirror-heading-shell.json`: the tab title, the navigation
heading and its data attributes, the commit the page was rendered for, whether the shell
carried `static/mirror-heading.js`, and the `/api/source/status` fields the heading is
rendered from.
`tests/test_mirror_heading_session.py` serves all three and fails when the
recording drifts.
A store’s key is a stand-in there, because it is derived from the run’s
own directory.

Each page runs `static/mirror-heading.js` first when its shell carried it, then loads
the production SDK whole, and runs the shell’s own heading code lifted verbatim from
`app.js`: the folder header, the file header’s address, and the block that wires the
navigation heading’s tooltip.
No heading is composed here; every string is what that code returned or showed.
The steps are a page load, which mounts the commit’s copy control on a mirror; the main
heading at the root folder and at a nested file; the pointer entering the navigation
heading before and after the tree loads, then the root’s name and the note; and a click
on the copy control, through the SDK’s delegated listener.
`title` shows the tab’s title as served and after every step, with each write to
`document.title` the steps made, which must be none.

The session fails unless a folder’s page is unchanged and shows nothing of a mirror, a
mirror’s address starts with the repository’s name and names neither a commit nor a
path, each heading holds one note after its last crumb, the three tooltips say what the
mirror is in a line of their own, the click copies the full commit from an owner-stamped
control, and the hostile name, origin, and location are escaped wherever they are
written.

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
      "served": "Metabrowser",
      "afterEveryStep": "Metabrowser",
      "writes": []
    },
    "navigationHeading": {
      "html": "<span class=\"path\"><span class=\"path-base\">squares</span></span>",
      "text": "squares",
      "commitCopy": null
    },
    "mainHeading": {
      "root": "↑ ~/wrk/squares /",
      "file": {
        "html": "<span class=\"file-header-root\"><bdi>~/wrk/squares</bdi></span><button type=\"button\" class=\"folder-crumb folder-crumb-root\" data-nav-dir=\"\" data-mb-owner data-tip-text=\"Served root\">/</button><button type=\"button\" class=\"folder-crumb\" data-nav-dir=\"docs\" data-mb-owner data-tip-text=\"docs\">docs</button><span class=\"folder-crumb-sep\">/</span><button type=\"button\" class=\"folder-crumb folder-crumb-current\" data-nav-file=\"docs/guide.md\" data-mb-owner data-tip-text=\"docs/guide.md\">guide.md</button>",
        "text": "~/wrk/squares / docs / guide.md"
      }
    },
    "tooltips": {
      "navigationHeading": {
        "served": "~/wrk/squares Jump to root",
        "afterTreeLoad": "~/wrk/squares 3 files 140 bytes Jump to root"
      },
      "rootName": null,
      "note": null
    }
  },
  {
    "subject": "mirror",
    "kind": "git_revision",
    "status": {
      "name": "squares",
      "origin": "file://~/git/squares.git",
      "location": "~/.metabrowser/cache/repository-stores/store-key-1/repository.git",
      "pin": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
      "ref_name": "topic"
    },
    "title": {
      "served": "Metabrowser",
      "afterEveryStep": "Metabrowser",
      "writes": []
    },
    "navigationHeading": {
      "html": "<span class=\"path\"><span class=\"path-base\">squares</span></span><span class=\"header-revision header-ref\">topic</span><span class=\"header-revision\">42382ea2303b</span>",
      "text": "squares topic 42382ea2303b",
      "commitCopy": {
        "attributes": {
          "type": "button",
          "class": "icon-btn icon-btn-reveal header-copy copied",
          "data-mb-copy": "text",
          "data-mb-copy-text": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
          "data-mb-copy-label": "Copy commit",
          "data-tip-text": "Copied!",
          "aria-label": "Copy commit 42382ea2303b733e1e21b4bd6ddb974ca4e775eb"
        },
        "ownerStamped": true,
        "copied": [
          "42382ea2303b733e1e21b4bd6ddb974ca4e775eb"
        ]
      }
    },
    "mainHeading": {
      "root": "↑ squares / mirror in ~/.metabrowser/cache/repository-stores/store-key-1/repository.git",
      "file": {
        "html": "<span class=\"file-header-root\"><bdi>squares</bdi></span><button type=\"button\" class=\"folder-crumb folder-crumb-root\" data-nav-dir=\"\" data-mb-owner data-tip-text=\"Served root\">/</button><button type=\"button\" class=\"folder-crumb\" data-nav-dir=\"g1-ZG9jcw\" data-mb-owner data-tip-text=\"docs\">docs</button><span class=\"folder-crumb-sep\">/</span><button type=\"button\" class=\"folder-crumb folder-crumb-current\" data-nav-file=\"g1-ZG9jcw/g1-Z3VpZGUubWQ\" data-mb-owner data-tip-text=\"docs/guide.md\">guide.md</button><span class=\"file-header-mirror\"><span class=\"file-header-mirror-text\">mirror in ~/.metabrowser/cache/repository-stores/store-key-1/repository.git</span></span>",
        "text": "squares / docs / guide.md mirror in ~/.metabrowser/cache/repository-stores/store-key-1/repository.git"
      }
    },
    "tooltips": {
      "navigationHeading": {
        "served": "squares Mirror of file://~/git/squares.git at 42382ea2303b733e1e21b4bd6ddb974ca4e775eb, stored in ~/.metabrowser/cache/repository-stores/store-key-1/repository.git: a bare Git repository, with no checked-out files. Jump to root",
        "afterTreeLoad": "squares 3 files 140 bytes Mirror of file://~/git/squares.git at 42382ea2303b733e1e21b4bd6ddb974ca4e775eb, stored in ~/.metabrowser/cache/repository-stores/store-key-1/repository.git: a bare Git repository, with no checked-out files. Jump to root"
      },
      "rootName": "Mirror of file://~/git/squares.git at 42382ea2303b733e1e21b4bd6ddb974ca4e775eb, stored in ~/.metabrowser/cache/repository-stores/store-key-1/repository.git: a bare Git repository, with no checked-out files.",
      "note": "Mirror of file://~/git/squares.git at 42382ea2303b733e1e21b4bd6ddb974ca4e775eb, stored in ~/.metabrowser/cache/repository-stores/store-key-1/repository.git: a bare Git repository, with no checked-out files."
    }
  },
  {
    "subject": "hostile",
    "kind": "git_revision",
    "status": {
      "name": "a<b>&�x",
      "origin": "file://~/git/a%3Cb%3E&%E2%80%AEx.git",
      "location": "~/odd\"<&>home/cache/repository-stores/store-key-2/repository.git",
      "pin": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
      "ref_name": "topic"
    },
    "title": {
      "served": "Metabrowser",
      "afterEveryStep": "Metabrowser",
      "writes": []
    },
    "navigationHeading": {
      "html": "<span class=\"path\"><span class=\"path-base\">a&lt;b&gt;&amp;�x</span></span><span class=\"header-revision header-ref\">topic</span><span class=\"header-revision\">42382ea2303b</span>",
      "text": "a<b>&�x topic 42382ea2303b",
      "commitCopy": {
        "attributes": {
          "type": "button",
          "class": "icon-btn icon-btn-reveal header-copy copied",
          "data-mb-copy": "text",
          "data-mb-copy-text": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
          "data-mb-copy-label": "Copy commit",
          "data-tip-text": "Copied!",
          "aria-label": "Copy commit 42382ea2303b733e1e21b4bd6ddb974ca4e775eb"
        },
        "ownerStamped": true,
        "copied": [
          "42382ea2303b733e1e21b4bd6ddb974ca4e775eb"
        ]
      }
    },
    "mainHeading": {
      "root": "↑ a<b>&�x / mirror in ~/odd\"<&>home/cache/repository-stores/store-key-2/repository.git",
      "file": {
        "html": "<span class=\"file-header-root\"><bdi>a&lt;b&gt;&amp;�x</bdi></span><button type=\"button\" class=\"folder-crumb folder-crumb-root\" data-nav-dir=\"\" data-mb-owner data-tip-text=\"Served root\">/</button><button type=\"button\" class=\"folder-crumb\" data-nav-dir=\"g1-ZG9jcw\" data-mb-owner data-tip-text=\"docs\">docs</button><span class=\"folder-crumb-sep\">/</span><button type=\"button\" class=\"folder-crumb folder-crumb-current\" data-nav-file=\"g1-ZG9jcw/g1-Z3VpZGUubWQ\" data-mb-owner data-tip-text=\"docs/guide.md\">guide.md</button><span class=\"file-header-mirror\"><span class=\"file-header-mirror-text\">mirror in ~/odd&quot;&lt;&amp;&gt;home/cache/repository-stores/store-key-2/repository.git</span></span>",
        "text": "a<b>&�x / docs / guide.md mirror in ~/odd\"<&>home/cache/repository-stores/store-key-2/repository.git"
      }
    },
    "tooltips": {
      "navigationHeading": {
        "served": "a<b>&�x Mirror of file://~/git/a%3Cb%3E&%E2%80%AEx.git at 42382ea2303b733e1e21b4bd6ddb974ca4e775eb, stored in ~/odd\"<&>home/cache/repository-stores/store-key-2/repository.git: a bare Git repository, with no checked-out files. Jump to root",
        "afterTreeLoad": "a<b>&�x 3 files 140 bytes Mirror of file://~/git/a%3Cb%3E&%E2%80%AEx.git at 42382ea2303b733e1e21b4bd6ddb974ca4e775eb, stored in ~/odd\"<&>home/cache/repository-stores/store-key-2/repository.git: a bare Git repository, with no checked-out files. Jump to root"
      },
      "rootName": "Mirror of file://~/git/a%3Cb%3E&%E2%80%AEx.git at 42382ea2303b733e1e21b4bd6ddb974ca4e775eb, stored in ~/odd\"<&>home/cache/repository-stores/store-key-2/repository.git: a bare Git repository, with no checked-out files.",
      "note": "Mirror of file://~/git/a%3Cb%3E&%E2%80%AEx.git at 42382ea2303b733e1e21b4bd6ddb974ca4e775eb, stored in ~/odd\"<&>home/cache/repository-stores/store-key-2/repository.git: a bare Git repository, with no checked-out files."
    }
  }
]
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
