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
ref and the short commit beside it, and its main heading ends with a note that says
where the mirror is kept.

The mirror is a bare Git repository, and each page is read from a Git object at the
pinned commit, so no folder holds these files.
The note therefore stands after the address and never as its start, and the tooltip on
the name and on the note says what the directory is: the origin, the full commit, the
location, and that nothing is checked out.

This browserless session loads the production `static/navigation.js`, with
`static/git-path.js` ahead of it on a mirror, and runs the shell’s own heading code on
what the in-process application served for a folder, for a mirror, and for a mirror
whose origin has markup and U+202E RIGHT-TO-LEFT OVERRIDE in its name.
That input is `tests/fixtures/mirror-heading-shell.json`: the tab title, the navigation
heading and its data attributes, and the `/api/source/status` fields the heading is
rendered from.
`tests/test_mirror_heading_session.py` serves all three and fails when the
recording drifts. Two values in it are stand-ins, because they name the run’s own
directory: `/sandbox`, and each store’s key.

The transcript shows, per subject, the navigation heading, the main heading at the root
and at a nested file, and the navigation heading’s tooltip before and after the tree
loads. The session fails unless a folder’s page is unchanged, a mirror’s address starts
with the repository’s name and names neither a commit nor a path, the note follows the
last crumb, the tooltips name the origin and the full commit, the hostile name is
escaped wherever it is written, and no script sets the tab title.

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
    "title": "Metabrowser",
    "navigationHeading": {
      "html": "<span class=\"path\"><span class=\"path-base\">squares</span></span>",
      "text": "squares"
    },
    "mainHeading": {
      "root": "~/wrk/squares /",
      "file": {
        "html": "<span class=\"file-header-root\"><bdi>~/wrk/squares</bdi></span><button type=\"button\" class=\"folder-crumb folder-crumb-root\" data-nav-dir=\"\" data-tip-text=\"Served root\">/</button><button type=\"button\" class=\"folder-crumb\" data-nav-dir=\"docs\" data-tip-text=\"docs\">docs</button><span class=\"folder-crumb-sep\">/</span><button type=\"button\" class=\"folder-crumb folder-crumb-current\" data-nav-file=\"docs/guide.md\" data-tip-text=\"docs/guide.md\">guide.md</button>",
        "text": "~/wrk/squares / docs / guide.md",
        "tooltips": [
          "Served root",
          "docs",
          "docs/guide.md"
        ]
      }
    },
    "navigationTooltip": {
      "served": "~/wrk/squares Jump to root",
      "afterTreeLoad": "~/wrk/squares 3 files 140 bytes Jump to root"
    }
  },
  {
    "subject": "mirror",
    "kind": "git_revision",
    "status": {
      "name": "squares",
      "origin": "file:///sandbox/user/git/squares.git",
      "location": "~/.metabrowser/cache/repository-stores/store-key-1/repository.git",
      "pin": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
      "ref_name": "topic"
    },
    "title": "Metabrowser",
    "navigationHeading": {
      "html": "<span class=\"path\"><span class=\"path-base\">squares</span></span><span class=\"header-revision header-ref\">topic</span><span class=\"header-revision\">42382ea2303b</span>",
      "text": "squares topic 42382ea2303b"
    },
    "mainHeading": {
      "root": "squares / mirror in ~/.metabrowser/cache/repository-stores/store-key-1/repository.git",
      "file": {
        "html": "<span class=\"file-header-root\" data-tip-text=\"Mirror of file:///sandbox/user/git/squares.git at 42382ea2303b733e1e21b4bd6ddb974ca4e775eb, stored in ~/.metabrowser/cache/repository-stores/store-key-1/repository.git: a bare Git repository, with no checked-out files.\"><bdi>squares</bdi></span><button type=\"button\" class=\"folder-crumb folder-crumb-root\" data-nav-dir=\"\" data-tip-text=\"Served root\">/</button><button type=\"button\" class=\"folder-crumb\" data-nav-dir=\"g1-ZG9jcw\" data-tip-text=\"docs\">docs</button><span class=\"folder-crumb-sep\">/</span><button type=\"button\" class=\"folder-crumb folder-crumb-current\" data-nav-file=\"g1-ZG9jcw/g1-Z3VpZGUubWQ\" data-tip-text=\"docs/guide.md\">guide.md</button><span class=\"file-header-mirror\" data-tip-text=\"Mirror of file:///sandbox/user/git/squares.git at 42382ea2303b733e1e21b4bd6ddb974ca4e775eb, stored in ~/.metabrowser/cache/repository-stores/store-key-1/repository.git: a bare Git repository, with no checked-out files.\">mirror in ~/.metabrowser/cache/repository-stores/store-key-1/repository.git</span>",
        "text": "squares / docs / guide.md mirror in ~/.metabrowser/cache/repository-stores/store-key-1/repository.git",
        "tooltips": [
          "Mirror of file:///sandbox/user/git/squares.git at 42382ea2303b733e1e21b4bd6ddb974ca4e775eb, stored in ~/.metabrowser/cache/repository-stores/store-key-1/repository.git: a bare Git repository, with no checked-out files.",
          "Served root",
          "docs",
          "docs/guide.md"
        ]
      }
    },
    "navigationTooltip": {
      "served": "squares Mirror of file:///sandbox/user/git/squares.git at 42382ea2303b733e1e21b4bd6ddb974ca4e775eb, stored in ~/.metabrowser/cache/repository-stores/store-key-1/repository.git: a bare Git repository, with no checked-out files. Jump to root",
      "afterTreeLoad": "squares 3 files 140 bytes Mirror of file:///sandbox/user/git/squares.git at 42382ea2303b733e1e21b4bd6ddb974ca4e775eb, stored in ~/.metabrowser/cache/repository-stores/store-key-1/repository.git: a bare Git repository, with no checked-out files. Jump to root"
    }
  },
  {
    "subject": "hostile",
    "kind": "git_revision",
    "status": {
      "name": "a<b>&�x",
      "origin": "file:///sandbox/user/git/a%3Cb%3E&%E2%80%AEx.git",
      "location": "~/odd\"<&>home/cache/repository-stores/store-key-2/repository.git",
      "pin": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
      "ref_name": "topic"
    },
    "title": "Metabrowser",
    "navigationHeading": {
      "html": "<span class=\"path\"><span class=\"path-base\">a&lt;b&gt;&amp;�x</span></span><span class=\"header-revision header-ref\">topic</span><span class=\"header-revision\">42382ea2303b</span>",
      "text": "a<b>&�x topic 42382ea2303b"
    },
    "mainHeading": {
      "root": "a<b>&�x / mirror in ~/odd\"<&>home/cache/repository-stores/store-key-2/repository.git",
      "file": {
        "html": "<span class=\"file-header-root\" data-tip-text=\"Mirror of file:///sandbox/user/git/a%3Cb%3E&amp;%E2%80%AEx.git at 42382ea2303b733e1e21b4bd6ddb974ca4e775eb, stored in ~/odd&quot;&lt;&amp;&gt;home/cache/repository-stores/store-key-2/repository.git: a bare Git repository, with no checked-out files.\"><bdi>a&lt;b&gt;&amp;�x</bdi></span><button type=\"button\" class=\"folder-crumb folder-crumb-root\" data-nav-dir=\"\" data-tip-text=\"Served root\">/</button><button type=\"button\" class=\"folder-crumb\" data-nav-dir=\"g1-ZG9jcw\" data-tip-text=\"docs\">docs</button><span class=\"folder-crumb-sep\">/</span><button type=\"button\" class=\"folder-crumb folder-crumb-current\" data-nav-file=\"g1-ZG9jcw/g1-Z3VpZGUubWQ\" data-tip-text=\"docs/guide.md\">guide.md</button><span class=\"file-header-mirror\" data-tip-text=\"Mirror of file:///sandbox/user/git/a%3Cb%3E&amp;%E2%80%AEx.git at 42382ea2303b733e1e21b4bd6ddb974ca4e775eb, stored in ~/odd&quot;&lt;&amp;&gt;home/cache/repository-stores/store-key-2/repository.git: a bare Git repository, with no checked-out files.\">mirror in ~/odd&quot;&lt;&amp;&gt;home/cache/repository-stores/store-key-2/repository.git</span>",
        "text": "a<b>&�x / docs / guide.md mirror in ~/odd\"<&>home/cache/repository-stores/store-key-2/repository.git",
        "tooltips": [
          "Mirror of file:///sandbox/user/git/a%3Cb%3E&%E2%80%AEx.git at 42382ea2303b733e1e21b4bd6ddb974ca4e775eb, stored in ~/odd\"<&>home/cache/repository-stores/store-key-2/repository.git: a bare Git repository, with no checked-out files.",
          "Served root",
          "docs",
          "docs/guide.md"
        ]
      }
    },
    "navigationTooltip": {
      "served": "a<b>&�x Mirror of file:///sandbox/user/git/a%3Cb%3E&%E2%80%AEx.git at 42382ea2303b733e1e21b4bd6ddb974ca4e775eb, stored in ~/odd\"<&>home/cache/repository-stores/store-key-2/repository.git: a bare Git repository, with no checked-out files. Jump to root",
      "afterTreeLoad": "a<b>&�x 3 files 140 bytes Mirror of file:///sandbox/user/git/a%3Cb%3E&%E2%80%AEx.git at 42382ea2303b733e1e21b4bd6ddb974ca4e775eb, stored in ~/odd\"<&>home/cache/repository-stores/store-key-2/repository.git: a bare Git repository, with no checked-out files. Jump to root"
    }
  }
]
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
