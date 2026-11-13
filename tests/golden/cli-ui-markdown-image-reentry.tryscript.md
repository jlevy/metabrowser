---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Markdown Image Re-entry

This browserless session executes the production Markdown link enhancer, imported from
its file with every module it imports, on images as KPress writes them: lazy, at the
address the author wrote.
The engine’s loads are events the session fires, and filesystem changes are calls to
`forgetChangedImages`, as the plugin’s `onInventoryChange` subscription makes them.
It pins which images a document entered again makes eager, the order of each image’s
attribute changes, the load listener’s lifecycle, the record’s bound and least recently
loaded eviction, and which held images a change or a reconnect forgets.
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
      "step": "after a reconnect",
      "loading": {
        "images/shown.png": "lazy"
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
    },
    {
      "step": "the Markdown changes",
      "loading": {
        "images/shown.png": "eager",
        "images/far.png": "eager",
        "deep/x/y/pic.png": "eager",
        "deep/z.png": "eager"
      }
    },
    {
      "step": "images/shown.png is replaced",
      "loading": {
        "images/shown.png": "lazy",
        "images/far.png": "eager",
        "deep/x/y/pic.png": "eager",
        "deep/z.png": "eager"
      }
    },
    {
      "step": "a change somewhere under deep/x",
      "loading": {
        "images/shown.png": "lazy",
        "images/far.png": "eager",
        "deep/x/y/pic.png": "lazy",
        "deep/z.png": "eager"
      }
    },
    {
      "step": "a reconnect",
      "loading": {
        "images/shown.png": "lazy",
        "images/far.png": "lazy",
        "deep/x/y/pic.png": "lazy",
        "deep/z.png": "lazy"
      }
    }
  ]
}
? 0
```
