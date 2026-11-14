"""A Markdown document entered again takes the images the page holds from that copy.

``tests/dom/markdown-image-reentry-session.js`` runs the shell's inventory stream
handlers and file store from ``app.js``, the plugin SDK, the Markdown plugin's
``index.js``, and the link enhancer together, on images as KPress writes them, lazy and
at the authored address, and fires the engine's loads itself. Entering a file again
builds its document again. In WebKit, the macOS app's engine, a new lazy image asks the
network again even for an image the page holds, which left a re-entered document's first
images blank for the round trip. So an image whose served address has loaded in this page
since the last filesystem change is made eager, its authored address removed first,
before that address is set; the rest stay lazy.

Any filesystem change, and any reconnect, even one whose snapshot is unchanged, forgets
every held image, so a replaced image is fetched again; a load assigned before a change
is not remembered; an image under a hidden name, where the watcher reports nothing, is
never held; and the record keeps ``MAX_HELD_IMAGES`` images, forgetting the least
recently loaded past that. This checks attributes, their order, listeners, and the
record, not loading or paint; docs/design-system.md, "A Repaint Keeps Its Images", has
the measurements, and ``tests/golden/cli-ui-markdown-image-reentry.tryscript.md`` the
transcript.
"""

from __future__ import annotations

from tests.golden_harness import run_session

SHOWN = "/raw?path=docs%2Fimages%2Fshown.png"
FAR = "/raw?path=docs%2Fimages%2Ffar.png"
REMOTE = "https://example.com/remote.png"


def _lazy(src: str) -> dict[str, object]:
    """An image left lazy: its served address set, or an outside one untouched."""

    changes = [] if src == REMOTE else [f"src={src}"]
    return {"loading": "lazy", "src": src, "changes": changes}


def _eager(src: str) -> dict[str, object]:
    """An image the page holds: the authored address removed, then eager, then served."""

    return {
        "loading": "eager",
        "src": src,
        "changes": ["remove src", "loading=eager", f"src={src}"],
    }


def test_a_reentered_document_takes_the_images_the_page_holds() -> None:
    result = run_session("markdown-image-reentry-session.js")
    assert result["bound"] == 1024
    assert result["steps"] == [
        # The page holds nothing yet, so every image waits for the reader.
        {
            "step": "first entry",
            "listens": {"load": "capture"},
            "images": [_lazy(SHOWN), _lazy(FAR), _lazy(REMOTE)],
        },
        {"step": "left", "listening": []},
        # The image the reader saw loaded; the far one did not, and the outside one is not
        # the enhancer's to serve.
        {"step": "entered again", "images": [_eager(SHOWN), _lazy(FAR), _lazy(REMOTE)]},
        # Every change and every reconnect forgets the held images, whatever its paths.
        {"step": "a reconnect sends the same snapshot", "before": "eager", "after": "lazy"},
        {"step": "the Markdown changes", "before": "eager", "after": "lazy"},
        {"step": "an image under docs/images is replaced", "before": "eager", "after": "lazy"},
        # A load assigned before a change may carry the bytes the change replaced.
        {
            "step": "a load assigned before a change finishes after it",
            "before": "lazy",
            "after": "lazy",
        },
        {"step": "a load assigned after the change", "before": "lazy", "after": "eager"},
        # No change under a hidden name would be heard.
        {
            "step": "images under hidden names load",
            "loading": {".assets/logo.png": "lazy", "images/.cache/thumb.png": "lazy"},
        },
        # Exactly at the bound, the least recently loaded is still held.
        {
            "step": "1024 images loaded: the bound",
            "loading": {"gallery/0.png": "eager", "gallery/1023.png": "eager"},
        },
        {
            "step": "one more loads: the least recently loaded is forgotten",
            "loading": {"gallery/0.png": "lazy", "gallery/1.png": "eager", "extra/0.png": "eager"},
        },
        # A load makes an older image the most recently loaded, so the next one goes.
        {
            "step": "gallery/1.png loads again, then one more loads",
            "loading": {
                "gallery/1.png": "eager",
                "gallery/2.png": "lazy",
                "gallery/3.png": "eager",
                "extra/1.png": "eager",
            },
        },
    ]
