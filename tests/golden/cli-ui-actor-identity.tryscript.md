---
cwd: ../..
sandbox: false
---
# Golden Test: A Person, Drawn as One Identity

A page names a person through one component: `actorIdentity` in
`static/plugin-sdk-views.js`, as nodes, and `actorIdentityHtml` beside it, as markup,
which the plugin SDK exposes as `metabrowser.actorIdentity` and
`metabrowser.actorIdentityHtml`. It is an avatar’s box, then the bold name in
`strong.actor-name`. A commit’s page draws its author through the markup form, and the
GitHub plugin’s `authorLabel` draws every author on a pull request’s page and in a Pulls
row through the nodes form, so the box is one size on both pages.

This browserless session runs the real plugin SDK against a recording document and
records what each case draws.
The transcript pins these behaviors:

- The box holds the avatar where the caller has an https address for one, its image’s
  size and privacy attributes set before the address it asks for, and lazy unless the
  caller asks for eager.
- An image that fails to load gives its box to the person glyph, Lucide’s
  `circle-user-round`, and the box stays where it was.
- A person with no avatar keeps the box, with the glyph in it.
  An address that is not https is never asked for, and the glyph stands in for it.
- A dense list row passes `placeholder: false` and draws no box for a person with no
  avatar.
- A placement adds its own classes to the identity and to the name.
- A name is its text in both forms, and the markup form is what the nodes form draws.

```console
$ node tests/dom/actor-identity-session.js
{
  "an avatar, eager": {
    "tag": "span",
    "class": "actor-identity",
    "children": [
      {
        "tag": "span",
        "class": "actor-avatar",
        "attributes": {
          "aria-hidden": "true"
        },
        "children": [
          {
            "tag": "img",
            "class": "actor-avatar-image",
            "attributes": {
              "alt": "",
              "width": "18",
              "height": "18",
              "loading": "eager",
              "decoding": "async",
              "fetchpriority": "low",
              "crossorigin": "anonymous",
              "referrerpolicy": "no-referrer",
              "src": "https://avatars.githubusercontent.com/u/1242887?s=40"
            }
          }
        ]
      },
      {
        "tag": "strong",
        "class": "actor-name",
        "text": "octo"
      }
    ]
  },
  "the avatar fails to load": {
    "tag": "span",
    "class": "actor-identity",
    "children": [
      {
        "tag": "span",
        "class": "actor-avatar",
        "attributes": {
          "aria-hidden": "true"
        },
        "inner": "the person glyph"
      },
      {
        "tag": "strong",
        "class": "actor-name",
        "text": "octo"
      }
    ]
  },
  "an avatar, by default": {
    "alt": "",
    "width": "18",
    "height": "18",
    "loading": "lazy",
    "decoding": "async",
    "fetchpriority": "low",
    "crossorigin": "anonymous",
    "referrerpolicy": "no-referrer",
    "src": "https://avatars.githubusercontent.com/u/1242887?s=40"
  },
  "no avatar": {
    "tag": "span",
    "class": "actor-identity",
    "children": [
      {
        "tag": "span",
        "class": "actor-avatar",
        "attributes": {
          "aria-hidden": "true"
        },
        "inner": "the person glyph"
      },
      {
        "tag": "strong",
        "class": "actor-name",
        "text": "Jane Author"
      }
    ]
  },
  "an address that is not https": {
    "http://avatars.githubusercontent.com/u/1?s=40": "the person glyph",
    "javascript:alert(1)": "the person glyph",
    "data:image/svg+xml,<svg/>": "the person glyph",
    "//avatars.githubusercontent.com/u/1": "the person glyph",
    "": "the person glyph"
  },
  "a list row, no avatar": {
    "tag": "span",
    "class": "actor-identity",
    "children": [
      {
        "tag": "strong",
        "class": "actor-name github-pulls-author",
        "text": "ghost"
      }
    ]
  },
  "a list row, an avatar": [
    "actor-avatar",
    "actor-name"
  ],
  "a placement's classes": {
    "tag": "span",
    "class": "actor-identity github-pull-identity",
    "children": [
      {
        "tag": "span",
        "class": "actor-avatar",
        "attributes": {
          "aria-hidden": "true"
        },
        "inner": "the person glyph"
      },
      {
        "tag": "strong",
        "class": "actor-name github-pull-author",
        "text": "forker"
      }
    ]
  },
  "markup, a name with markup in it": "<span class=\"actor-identity\"><span class=\"actor-avatar\" aria-hidden=\"true\">{the person glyph}</span><strong class=\"actor-name git-commit-author\">Ada &lt;b&gt;&quot;Lovelace&quot;&lt;/b&gt; &amp; co</strong></span>"
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
