"""A Markdown document entered again takes the images the page holds from that copy.

``tests/dom/markdown-image-reentry-session.js`` runs the production link enhancer on
images as KPress writes them, lazy and at the authored address, and fires the engine's
loads itself. Entering a file again builds its document again. In WebKit, the macOS app's
engine, a new lazy image asks the network again even for an image the page holds, which
left a re-entered document's first images blank for the round trip. So an image whose
served address has loaded in this page is made eager, its authored address removed first,
before that address is set; the rest stay lazy. This checks attributes, their order, and
listeners, not loading or paint; docs/design-system.md, "A Repaint Keeps Its Images", has
the measurements.
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
    assert result == {
        "steps": [
            # The page holds nothing yet, so every image waits for the reader.
            {
                "step": "first entry",
                "listens": {"load": "capture"},
                "images": [_lazy(SHOWN), _lazy(FAR), _lazy(REMOTE)],
            },
            {"step": "left", "listening": []},
            # The image the reader saw loaded; the far one did not, and the outside one
            # is not the enhancer's to serve.
            {
                "step": "entered again",
                "images": [_eager(SHOWN), _lazy(FAR), _lazy(REMOTE)],
            },
            {
                "step": "entered after reaching the far image",
                "images": [_eager(SHOWN), _eager(FAR), _lazy(REMOTE)],
            },
            # Held by its served address, whichever document shows it.
            {"step": "another document shows the same image", "images": [_eager(SHOWN)]},
            # As many images as one document admits loaded since: the oldest wait again.
            {
                "step": "entered after 4,096 other images loaded",
                "images": [_lazy(SHOWN), _lazy(FAR), _lazy(REMOTE)],
            },
        ]
    }
