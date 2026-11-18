---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: The View Header’s GitHub Toggle

On a page whose repository is on github.com, a file’s or a folder’s view header ends its
heading row in a toggle of two marks: Metabrowser’s, gray, the view every page opens in,
and GitHub’s, a link to the same item’s page on github.com.
A plain folder, a checkout whose `origin` is on another host or that has no remote, and
a mirror of a repository that is not on github.com have no toggle.

The input is `tests/fixtures/github-page-shell.json`: the repository context the server
writes into each page’s shell, from the functions that decide the Pulls tab,
`discover_repository_context` for a checkout and `repository_context_for` for a mirror,
recorded by `tests/test_github_page_session.py` for checkouts on github.com over HTTPS
on a branch origin has, over SSH detached, and served from a subfolder on a branch
origin lacks; origins on GitLab and on a GitHub Enterprise host; a repository with no
remote; a plain folder; and mirrors of a github.com repository and of a `file://` one.

This browserless session loads the production `static/github-page.js` into a page of
fakes for each context and commits a view header for each page a folder or a pin can be
on, as `app.js` does: the served root, a folder, a file, and names with a space, a
character outside ASCII, parentheses, a literal percent, and a byte that is not UTF-8.
It records the toggle as a reader meets it, whether each page drew it in the Metabrowser
view, and the GitHub link for each page: a folder’s tree or a file’s blob at the branch
the page is on, or at its commit where it is on none, under the served root’s place in
the repository.

```console
$ node tests/dom/github-page-session.js
[
  {
    "context": "github-https",
    "toggle": {
      "label": "View",
      "role": "group",
      "options": [
        {
          "element": "span",
          "class": "view-header-toggle-option view-header-toggle-metabrowser",
          "current": "page",
          "label": "Metabrowser view, shown",
          "tip": "Metabrowser view, shown"
        },
        {
          "element": "a",
          "class": "view-header-toggle-option view-header-toggle-github",
          "current": null,
          "label": "View on GitHub",
          "tip": "View on GitHub: github.com/octo/demo/tree/main",
          "href": "https://github.com/octo/demo/tree/main",
          "target": "_blank",
          "rel": "noopener noreferrer"
        }
      ]
    },
    "pagesShowingMetabrowser": 6,
    "pages": 6,
    "urls": {
      "(root)": "https://github.com/octo/demo/tree/main",
      "docs": "https://github.com/octo/demo/tree/main/docs",
      "docs/guide.md": "https://github.com/octo/demo/blob/main/docs/guide.md",
      "docs/a b/雪 (1).md": "https://github.com/octo/demo/blob/main/docs/a%20b/%E9%9B%AA%20%281%29.md",
      "50%25-off.md": "https://github.com/octo/demo/blob/main/50%25-off.md",
      "raw/%FF.bin": "https://github.com/octo/demo/blob/main/raw/%FF.bin"
    }
  },
  {
    "context": "github-ssh-detached",
    "toggle": {
      "label": "View",
      "role": "group",
      "options": [
        {
          "element": "span",
          "class": "view-header-toggle-option view-header-toggle-metabrowser",
          "current": "page",
          "label": "Metabrowser view, shown",
          "tip": "Metabrowser view, shown"
        },
        {
          "element": "a",
          "class": "view-header-toggle-option view-header-toggle-github",
          "current": null,
          "label": "View on GitHub",
          "tip": "View on GitHub: github.com/octo/demo/tree/0123456789abcdef0123456789abcdef01234567",
          "href": "https://github.com/octo/demo/tree/0123456789abcdef0123456789abcdef01234567",
          "target": "_blank",
          "rel": "noopener noreferrer"
        }
      ]
    },
    "pagesShowingMetabrowser": 6,
    "pages": 6,
    "urls": {
      "(root)": "https://github.com/octo/demo/tree/0123456789abcdef0123456789abcdef01234567",
      "docs": "https://github.com/octo/demo/tree/0123456789abcdef0123456789abcdef01234567/docs",
      "docs/guide.md": "https://github.com/octo/demo/blob/0123456789abcdef0123456789abcdef01234567/docs/guide.md",
      "docs/a b/雪 (1).md": "https://github.com/octo/demo/blob/0123456789abcdef0123456789abcdef01234567/docs/a%20b/%E9%9B%AA%20%281%29.md",
      "50%25-off.md": "https://github.com/octo/demo/blob/0123456789abcdef0123456789abcdef01234567/50%25-off.md",
      "raw/%FF.bin": "https://github.com/octo/demo/blob/0123456789abcdef0123456789abcdef01234567/raw/%FF.bin"
    }
  },
  {
    "context": "github-subfolder-unpushed",
    "toggle": {
      "label": "View",
      "role": "group",
      "options": [
        {
          "element": "span",
          "class": "view-header-toggle-option view-header-toggle-metabrowser",
          "current": "page",
          "label": "Metabrowser view, shown",
          "tip": "Metabrowser view, shown"
        },
        {
          "element": "a",
          "class": "view-header-toggle-option view-header-toggle-github",
          "current": null,
          "label": "View on GitHub",
          "tip": "View on GitHub: github.com/octo/demo/tree/0123456789abcdef0123456789abcdef01234567/docs. feature/x is not pushed, so this commit may not be on github.com either",
          "href": "https://github.com/octo/demo/tree/0123456789abcdef0123456789abcdef01234567/docs",
          "target": "_blank",
          "rel": "noopener noreferrer"
        }
      ]
    },
    "pagesShowingMetabrowser": 6,
    "pages": 6,
    "urls": {
      "(root)": "https://github.com/octo/demo/tree/0123456789abcdef0123456789abcdef01234567/docs",
      "docs": "https://github.com/octo/demo/tree/0123456789abcdef0123456789abcdef01234567/docs/docs",
      "docs/guide.md": "https://github.com/octo/demo/blob/0123456789abcdef0123456789abcdef01234567/docs/docs/guide.md",
      "docs/a b/雪 (1).md": "https://github.com/octo/demo/blob/0123456789abcdef0123456789abcdef01234567/docs/docs/a%20b/%E9%9B%AA%20%281%29.md",
      "50%25-off.md": "https://github.com/octo/demo/blob/0123456789abcdef0123456789abcdef01234567/docs/50%25-off.md",
      "raw/%FF.bin": "https://github.com/octo/demo/blob/0123456789abcdef0123456789abcdef01234567/docs/raw/%FF.bin"
    }
  },
  {
    "context": "gitlab",
    "toggle": null,
    "pagesShowingMetabrowser": 0,
    "pages": 6,
    "urls": {
      "(root)": null,
      "docs": null,
      "docs/guide.md": null,
      "docs/a b/雪 (1).md": null,
      "50%25-off.md": null,
      "raw/%FF.bin": null
    }
  },
  {
    "context": "github-enterprise",
    "toggle": null,
    "pagesShowingMetabrowser": 0,
    "pages": 6,
    "urls": {
      "(root)": null,
      "docs": null,
      "docs/guide.md": null,
      "docs/a b/雪 (1).md": null,
      "50%25-off.md": null,
      "raw/%FF.bin": null
    }
  },
  {
    "context": "no-remote",
    "toggle": null,
    "pagesShowingMetabrowser": 0,
    "pages": 6,
    "urls": {
      "(root)": null,
      "docs": null,
      "docs/guide.md": null,
      "docs/a b/雪 (1).md": null,
      "50%25-off.md": null,
      "raw/%FF.bin": null
    }
  },
  {
    "context": "plain-folder",
    "toggle": null,
    "pagesShowingMetabrowser": 0,
    "pages": 6,
    "urls": {
      "(root)": null,
      "docs": null,
      "docs/guide.md": null,
      "docs/a b/雪 (1).md": null,
      "50%25-off.md": null,
      "raw/%FF.bin": null
    }
  },
  {
    "context": "mirror-github",
    "toggle": {
      "label": "View",
      "role": "group",
      "options": [
        {
          "element": "span",
          "class": "view-header-toggle-option view-header-toggle-metabrowser",
          "current": "page",
          "label": "Metabrowser view, shown",
          "tip": "Metabrowser view, shown"
        },
        {
          "element": "a",
          "class": "view-header-toggle-option view-header-toggle-github",
          "current": null,
          "label": "View on GitHub",
          "tip": "View on GitHub: github.com/octo/demo/tree/main",
          "href": "https://github.com/octo/demo/tree/main",
          "target": "_blank",
          "rel": "noopener noreferrer"
        }
      ]
    },
    "pagesShowingMetabrowser": 4,
    "pages": 4,
    "urls": {
      "(root)": "https://github.com/octo/demo/tree/main",
      "g1-ZG9jcw": "https://github.com/octo/demo/tree/main/docs",
      "g1-ZG9jcw/g1-Z3VpZGUubWQ": "https://github.com/octo/demo/blob/main/docs/guide.md",
      "g1-ZG9jcw/g1-YSBi/g1-6ZuqICgxKS5tZA": "https://github.com/octo/demo/blob/main/docs/a%20b/%E9%9B%AA%20%281%29.md"
    }
  },
  {
    "context": "mirror-file",
    "toggle": null,
    "pagesShowingMetabrowser": 0,
    "pages": 4,
    "urls": {
      "(root)": null,
      "g1-ZG9jcw": null,
      "g1-ZG9jcw/g1-Z3VpZGUubWQ": null,
      "g1-ZG9jcw/g1-YSBi/g1-6ZuqICgxKS5tZA": null
    }
  }
]
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
