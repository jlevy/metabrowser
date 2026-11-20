---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden test: block remote images

Untrusted Markdown shows an image from the web, over `https` with no referrer sent, as
github.com does, unless the reader has turned that off in the Metabrowser menu.
The choice is one host-wide preference cookie, which the server reads from the page
request: the page’s `img-src` and `METABROWSER_SETTINGS.BLOCK_REMOTE_IMAGES` follow it,
so a change takes effect as the page loads again.

This session loads the exact production `static/remote-images.js`. `stored` is what each
value the browser can hold reads as, and only `1` blocks, which is what
`src/metabrowser/settings.py` reads (`tests/test_remote_images_js.py` holds the two to
the same answers). `choices` is each change the checkbox can make from each state the
page can be served under: a change writes the cookie and loads the page again, once, and
a click that changes nothing does neither.
`checkbox` is the menu’s box, which the server draws ticked or not as it read the
cookie, wired as the page wires it when the menu opens: ticking it from a page served
off is that choice, unticking it again from there changes nothing, and a page with no
box is not wired. `static/inert-html.js` applies the setting to the images themselves,
which `cli-ui-inert-markdown.tryscript.md` pins.

```console
$ node tests/dom/remote-images-session.js
{
  "authority": {
    "key": "metabrowser.blockRemoteImages",
    "inputId": "block-remote-images-input",
    "serverKey": "metabrowser.blockRemoteImages",
    "frozen": true
  },
  "stored": {
    "null": false,
    "\"1\"": true,
    "\"0\"": false,
    "\"\"": false,
    "\"true\"": false,
    "\"yes\"": false,
    "\"11\"": false,
    "\" 1\"": false
  },
  "choices": {
    "off, stays off": {
      "changed": false,
      "writes": [],
      "reloads": 0
    },
    "off, turned on": {
      "changed": true,
      "writes": [
        {
          "key": "metabrowser.blockRemoteImages",
          "value": "1"
        }
      ],
      "reloads": 1
    },
    "on, stays on": {
      "changed": false,
      "writes": [],
      "reloads": 0
    },
    "on, turned off": {
      "changed": true,
      "writes": [
        {
          "key": "metabrowser.blockRemoteImages",
          "value": "0"
        }
      ],
      "reloads": 1
    }
  },
  "checkbox": {
    "a page with no box": false,
    "served off, ticked": {
      "writes": [
        {
          "key": "metabrowser.blockRemoteImages",
          "value": "1"
        }
      ],
      "reloads": 1
    },
    "served off, ticked and unticked": {
      "writes": [
        {
          "key": "metabrowser.blockRemoteImages",
          "value": "1"
        }
      ],
      "reloads": 1
    },
    "served on, unticked": {
      "writes": [
        {
          "key": "metabrowser.blockRemoteImages",
          "value": "0"
        }
      ],
      "reloads": 1
    }
  }
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
