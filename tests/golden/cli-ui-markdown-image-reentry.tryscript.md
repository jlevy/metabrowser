---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Markdown Image Re-entry

This browserless session runs the Markdown plugin’s placement, `place-rendered.js`, and
its link enhancer together, as a mount runs them, on renders shaped as the server sends
them: images as KPress writes them, lazy and at the address the author wrote, and
`raw_versions`, the version of each served file the document embeds.
The engine’s loads are events the session fires.
It pins which images a document entered again makes eager, the order of each image’s
attribute changes and its placement, and the load listener’s lifecycle: a served image
is held at its versioned address and made eager before that address is set, an image
from another origin, a scheme-relative one included, is held and made eager before the
page adopts it, a replaced file’s new version is a new address that loads lazily, an
unversioned served address and an absolute or scheme-relative address on the page’s own
origin are never held, a pinned revision’s images are held, and the record keeps its
bound and evicts the least recently loaded.
When an image is fetched and painted is the engine’s; see “A Repaint Keeps Its Images”
in `docs/design-system.md`.

```console
$ node tests/dom/markdown-image-reentry-session.js
{
  "bound": 1024,
  "steps": [
    {
      "step": "first entry",
      "listens": {
        "load": "capture"
      },
      "images": [
        {
          "loading": "lazy",
          "src": "/raw?path=docs%2Fimages%2Fshown.png&v=a1b2c3d4e5f60718",
          "changes": [
            "placed",
            "src=/raw?path=docs%2Fimages%2Fshown.png&v=a1b2c3d4e5f60718"
          ]
        },
        {
          "loading": "lazy",
          "src": "/raw?path=docs%2Fimages%2Ffar.png&v=a1b2c3d4e5f60718",
          "changes": [
            "placed",
            "src=/raw?path=docs%2Fimages%2Ffar.png&v=a1b2c3d4e5f60718"
          ]
        },
        {
          "loading": "lazy",
          "src": "/raw?path=docs%2Fimages%2Fpast-the-bound.png",
          "changes": [
            "placed",
            "src=/raw?path=docs%2Fimages%2Fpast-the-bound.png"
          ]
        },
        {
          "loading": "lazy",
          "src": "https://example.com/remote.png",
          "changes": [
            "placed"
          ]
        },
        {
          "loading": "lazy",
          "src": "//cdn.example.com/badge.svg",
          "changes": [
            "placed"
          ]
        },
        {
          "loading": "lazy",
          "src": "//127.0.0.1:8000/own.png",
          "changes": [
            "placed"
          ]
        }
      ]
    },
    {
      "step": "left",
      "listening": []
    },
    {
      "step": "entered again",
      "images": [
        {
          "loading": "eager",
          "src": "/raw?path=docs%2Fimages%2Fshown.png&v=a1b2c3d4e5f60718",
          "changes": [
            "placed",
            "remove src",
            "loading=eager",
            "src=/raw?path=docs%2Fimages%2Fshown.png&v=a1b2c3d4e5f60718"
          ]
        },
        {
          "loading": "lazy",
          "src": "/raw?path=docs%2Fimages%2Ffar.png&v=a1b2c3d4e5f60718",
          "changes": [
            "placed",
            "src=/raw?path=docs%2Fimages%2Ffar.png&v=a1b2c3d4e5f60718"
          ]
        },
        {
          "loading": "lazy",
          "src": "/raw?path=docs%2Fimages%2Fpast-the-bound.png",
          "changes": [
            "placed",
            "src=/raw?path=docs%2Fimages%2Fpast-the-bound.png"
          ]
        },
        {
          "loading": "eager",
          "src": "https://example.com/remote.png",
          "changes": [
            "loading=eager",
            "placed"
          ]
        },
        {
          "loading": "eager",
          "src": "//cdn.example.com/badge.svg",
          "changes": [
            "loading=eager",
            "placed"
          ]
        },
        {
          "loading": "lazy",
          "src": "//127.0.0.1:8000/own.png",
          "changes": [
            "placed"
          ]
        }
      ]
    },
    {
      "step": "the image is replaced",
      "images": [
        {
          "loading": "lazy",
          "src": "/raw?path=docs%2Fimages%2Fshown.png&v=0f1e2d3c4b5a6978",
          "changes": [
            "placed",
            "src=/raw?path=docs%2Fimages%2Fshown.png&v=0f1e2d3c4b5a6978"
          ]
        }
      ]
    },
    {
      "step": "its new address loaded, then entered again",
      "loading": {
        "images/shown.png": "eager"
      }
    },
    {
      "step": "an absolute address on the page's origin loads",
      "loading": {
        "http://127.0.0.1:8000/raw?path=docs%2Fimages%2Fshown.png": "lazy"
      }
    },
    {
      "step": "a pinned revision's image loads",
      "loading": {
        "images/pinned.png": "eager"
      }
    },
    {
      "step": "1024 images loaded: the bound",
      "loading": {
        "gallery/0.png": "eager",
        "gallery/1023.png": "eager"
      }
    },
    {
      "step": "one more loads: the least recently loaded is forgotten",
      "loading": {
        "gallery/0.png": "lazy",
        "gallery/1.png": "eager",
        "extra/0.png": "eager"
      }
    },
    {
      "step": "gallery/1.png loads again, then one more loads",
      "loading": {
        "gallery/1.png": "eager",
        "gallery/2.png": "lazy",
        "gallery/3.png": "eager",
        "extra/1.png": "eager"
      }
    }
  ]
}
? 0
```
