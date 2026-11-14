"""A Markdown document entered again takes the images the page holds from that copy.

``tests/dom/markdown-image-reentry-session.js`` runs the Markdown plugin's placement
(``place-rendered.js``) and link enhancer together, on renders shaped as the server sends
them: images as KPress writes them, lazy and at the authored address, and
``raw_versions``, the version of each served file the document embeds. It fires the
engine's loads itself. Entering a file again builds its document again. In WebKit, the
macOS app's engine, a new lazy image asks the network again even for an image the page
holds, which left a re-entered document's first images blank for the round trip.

So the page holds a loaded image at an address that names its bytes, and makes it eager
when it is entered again: a served image at its versioned address, made eager after its
authored address is removed and before its served one is set; and an image from another
origin, a scheme-relative address on another host included, made eager in the template
before the page adopts it. A replaced file has a new
version, so a new address, and loads lazily there; an unversioned served address and an
absolute address on the page's own origin are never held; on a pinned revision every
served image is held. The record keeps ``MAX_HELD_IMAGES`` images, forgetting the least
recently loaded past that. This checks attributes, their order, listeners, and the
record, not loading or paint; docs/design-system.md, "A Repaint Keeps Its Images", has the
measurements, and ``tests/golden/cli-ui-markdown-image-reentry.tryscript.md`` the
transcript.
"""

from __future__ import annotations

from tests.golden_harness import run_session

VERSION = "a1b2c3d4e5f60718"
SHOWN = f"/raw?path=docs%2Fimages%2Fshown.png&v={VERSION}"
FAR = f"/raw?path=docs%2Fimages%2Ffar.png&v={VERSION}"
UNVERSIONED = "/raw?path=docs%2Fimages%2Fpast-the-bound.png"
REMOTE = "https://example.com/remote.png"
# Scheme-relative: another host's, and the page's own (the session's page is 127.0.0.1:8000).
SCHEMELESS = "//cdn.example.com/badge.svg"
OWN_SCHEMELESS = "//127.0.0.1:8000/own.png"
OUTSIDE = (REMOTE, SCHEMELESS, OWN_SCHEMELESS)


def _lazy(src: str) -> dict[str, object]:
    """An image left lazy: its served address set after placement, or an outside one."""

    changes = ["placed"] if src in OUTSIDE else ["placed", f"src={src}"]
    return {"loading": "lazy", "src": src, "changes": changes}


def _eager(src: str) -> dict[str, object]:
    """A served image the page holds: the authored address removed, then eager, then served."""

    return {
        "loading": "eager",
        "src": src,
        "changes": ["placed", "remove src", "loading=eager", f"src={src}"],
    }


def test_a_reentered_document_takes_the_images_the_page_holds() -> None:
    result = run_session("markdown-image-reentry-session.js")
    assert result["bound"] == 1024
    assert result["steps"] == [
        # The page holds nothing yet, so every image waits for the reader; a served file
        # the render versioned carries its version.
        {
            "step": "first entry",
            "listens": {"load": "capture"},
            "images": [
                _lazy(SHOWN),
                _lazy(FAR),
                _lazy(UNVERSIONED),
                _lazy(REMOTE),
                _lazy(SCHEMELESS),
                _lazy(OWN_SCHEMELESS),
            ],
        },
        {"step": "left", "listening": []},
        # All but the far image loaded. The shown and the two outside images are held; an
        # unversioned address, and a scheme-relative one on the page's own origin, can
        # change under the page (review A of #426, A2). An outside image is eager before
        # it is placed.
        {
            "step": "entered again",
            "images": [
                _eager(SHOWN),
                _lazy(FAR),
                _lazy(UNVERSIONED),
                {"loading": "eager", "src": REMOTE, "changes": ["loading=eager", "placed"]},
                {"loading": "eager", "src": SCHEMELESS, "changes": ["loading=eager", "placed"]},
                _lazy(OWN_SCHEMELESS),
            ],
        },
        # A replaced file's new version is a new address, which the page does not hold.
        {
            "step": "the image is replaced",
            "images": [_lazy("/raw?path=docs%2Fimages%2Fshown.png&v=0f1e2d3c4b5a6978")],
        },
        {
            "step": "its new address loaded, then entered again",
            "loading": {"images/shown.png": "eager"},
        },
        {
            "step": "an absolute address on the page's origin loads",
            "loading": {"http://127.0.0.1:8000/raw?path=docs%2Fimages%2Fshown.png": "lazy"},
        },
        {"step": "a pinned revision's image loads", "loading": {"images/pinned.png": "eager"}},
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
