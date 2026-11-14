---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Markdown Image Re-entry

This browserless session runs the production pieces together, as the page does: the
shell’s inventory stream handlers and file store, extracted from `app.js`; the plugin
SDK’s `onInventoryChange`; the Markdown plugin’s `index.js`, which subscribes
`forgetHeldImages`; and the link enhancer, imported from its file, on images as KPress
writes them: lazy, at the address the author wrote.
The stream frames are shaped as the server sends them on the shell’s `root-depth-2`
stream, and the engine’s loads are events the session fires.
It pins which images a document entered again makes eager, the order of each image’s
attribute changes, the load listener’s lifecycle, that any change and any reconnect,
even with the same snapshot, forget every held image, that a load assigned before a
change is not remembered, that an image under a hidden name is never held, and the
record’s bound and least recently loaded eviction.
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
          "src": "/raw?path=docs%2Fimages%2Fshown.png",
          "changes": [
            "src=/raw?path=docs%2Fimages%2Fshown.png"
          ]
        },
        {
          "loading": "lazy",
          "src": "/raw?path=docs%2Fimages%2Ffar.png",
          "changes": [
            "src=/raw?path=docs%2Fimages%2Ffar.png"
          ]
        },
        {
          "loading": "lazy",
          "src": "https://example.com/remote.png",
          "changes": []
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
          "src": "/raw?path=docs%2Fimages%2Fshown.png",
          "changes": [
            "remove src",
            "loading=eager",
            "src=/raw?path=docs%2Fimages%2Fshown.png"
          ]
        },
        {
          "loading": "lazy",
          "src": "/raw?path=docs%2Fimages%2Ffar.png",
          "changes": [
            "src=/raw?path=docs%2Fimages%2Ffar.png"
          ]
        },
        {
          "loading": "lazy",
          "src": "https://example.com/remote.png",
          "changes": []
        }
      ]
    },
    {
      "step": "a reconnect sends the same snapshot",
      "before": "eager",
      "after": "lazy"
    },
    {
      "step": "the Markdown changes",
      "before": "eager",
      "after": "lazy"
    },
    {
      "step": "an image under docs/images is replaced",
      "before": "eager",
      "after": "lazy"
    },
    {
      "step": "a load assigned before a change finishes after it",
      "before": "lazy",
      "after": "lazy"
    },
    {
      "step": "a load assigned after the change",
      "before": "lazy",
      "after": "eager"
    },
    {
      "step": "images under hidden names load",
      "loading": {
        ".assets/logo.png": "lazy",
        "images/.cache/thumb.png": "lazy"
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
