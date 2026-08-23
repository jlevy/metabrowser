"""Behavioral contracts for canonical browser navigation."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient
from typer.testing import CliRunner

from metabrowser import server
from metabrowser.cli.main import _app
from metabrowser.view_routes import format_view_href

REPO_ROOT = Path(__file__).resolve().parents[1]
ROUTE_SHIM = Path(__file__).resolve().parent / "dom" / "navigation-route-behavior.js"
runner = CliRunner()


def test_navigation_target_url_codec() -> None:
    """The strict route module safely round-trips one canonical URL shape."""

    if shutil.which("node") is None:
        pytest.skip("node not available; skipping navigation route behavioral shim")

    result = subprocess.run(
        ["node", str(ROUTE_SHIM), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        "navigation route behavioral shim failed:\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )


def test_application_has_no_hash_as_file_router() -> None:
    source = server.STATIC_DIR.joinpath("app.js").read_text()

    for removed in (
        "parseHashRoute",
        "splitHashRoute",
        "commitRoute",
        'addEventListener("hashchange"',
        "skipHistory",
    ):
        assert removed not in source
    assert "MetabrowserNavigationRoute.createController" in source
    assert "navigationController.canonicalizePath" in source
    assert 'new CustomEvent("metabrowser:navigation-fragment"' in source


def test_direct_view_routes_serve_the_shell_for_safe_targets(tmp_path: Path) -> None:
    """Root, files, missing paths, and either folder form can be refreshed."""

    folder = tmp_path / "nested folder"
    folder.mkdir()
    (folder / "雪 #1.md").write_text("# Snow")
    server._set_root_dir(tmp_path)
    try:
        client = TestClient(server.app)
        for route in (
            "/view/",
            "/view/nested%20folder",
            "/view/nested%20folder/",
            "/view/nested%20folder/%E9%9B%AA%20%231.md",
            "/view/percent%252Fname.md",
            "/view/not-yet-created.md",
        ):
            response = client.get(route)
            assert response.status_code == 200, route
            assert "<title>Metabrowser</title>" in response.text
            assert "/static/navigation.js?v=" in response.text
    finally:
        server._set_root_dir(Path())


@pytest.mark.parametrize(
    "route",
    [
        "/view/%2E%2E/secret.md",
        "/view/a%2Fb.md",
        "/view/a%5Cb.md",
        "/view/a%00b.md",
        "/view/a%2.md",
        "/view/a%FFb.md",
        "/view/docs//a.md",
    ],
)
def test_direct_view_routes_reject_malformed_or_unsafe_encodings(
    tmp_path: Path, route: str
) -> None:
    server._set_root_dir(tmp_path)
    try:
        response = TestClient(server.app).get(route)
    finally:
        server._set_root_dir(Path())
    assert response.status_code == 400


def test_direct_view_route_rejects_symlinks_outside_root(tmp_path: Path) -> None:
    served = tmp_path / "served"
    served.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("secret")
    (served / "linked.md").symlink_to(outside)
    server._set_root_dir(served)
    try:
        response = TestClient(server.app).get("/view/linked.md")
    finally:
        server._set_root_dir(Path())
    assert response.status_code == 400


def test_unprefixed_repository_paths_do_not_become_shell_routes(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Read me")
    server._set_root_dir(tmp_path)
    try:
        client = TestClient(server.app)
        assert client.get("/README.md").status_code == 404
        root_redirect = client.get("/view", follow_redirects=False)
        assert root_redirect.status_code == 307
        assert root_redirect.headers["location"].endswith("/view/")
    finally:
        server._set_root_dir(Path())


def test_bare_origin_redirects_to_the_canonical_served_root(tmp_path: Path) -> None:
    """The origin is not a second landing URL that renders an empty preview."""

    (tmp_path / "README.md").write_text("# Read me")
    server._set_root_dir(tmp_path)
    try:
        client = TestClient(server.app)
        redirect = client.get("/", follow_redirects=False)
        assert redirect.status_code == 307
        assert redirect.headers["location"] == "/view/"
        followed = client.get("/")
        assert followed.status_code == 200
        assert "<title>Metabrowser</title>" in followed.text
    finally:
        server._set_root_dir(Path())


def test_header_root_link_uses_the_canonical_view_route(tmp_path: Path) -> None:
    """`Jump to root` must select the served root, not the bare origin."""

    server._set_root_dir(tmp_path)
    try:
        response = TestClient(server.app).get("/view/")
    finally:
        server._set_root_dir(Path())
    assert '<a href="/view/" class="header-path"' in response.text
    assert '<a href="/" class="header-path"' not in response.text


def test_header_shows_the_root_folder_name_and_keeps_the_whole_path(tmp_path: Path) -> None:
    """The navigation column spends its width on the name, not the path.

    The directories above the served root are the same on every row of
    every view, and the column is the narrowest in the app. Nothing is
    lost: ``data-served-root`` is both what the file header reads back to
    draw its dimmed prefix — so the two headers cannot disagree about the
    root — and what this heading's own tooltip is built from in app.js.

    The heading carries no tooltip attribute of its own, deliberately. It
    has a richer tooltip in app.js, and an element announcing through two
    mechanisms is what the one-tooltip rule exists to prevent.
    """

    root = (tmp_path / "wrk" / "foo").resolve()
    root.mkdir(parents=True)
    server._set_root_dir(root)
    try:
        response = TestClient(server.app).get("/view/")
    finally:
        server._set_root_dir(Path())
    assert '<span class="path-base">foo</span>' in response.text
    assert '<span class="path-dir">' not in response.text
    assert f'data-served-root="{root}"' in response.text
    # One tooltip mechanism on this element, and it is app.js's own.
    header_anchor = response.text[response.text.index('class="header-path"') :][:400]
    assert "data-tip-text=" not in header_anchor
    assert "title=" not in header_anchor


def test_serve_cli_emits_segment_encoded_direct_view_url(tmp_path: Path) -> None:
    target = tmp_path / "docs" / "雪 #1%.md"
    target.parent.mkdir()
    target.write_text("# Snow")

    with (
        patch("metabrowser.cli.serve._QuietForceExitServer") as server_class,
        patch("metabrowser.cli.serve.find_available_local_port", return_value=8411),
    ):
        result = runner.invoke(
            _app,
            [str(tmp_path), "--path", "docs/雪 #1%.md", "--no-open"],
        )

    assert result.exit_code == 0, result.exception
    assert "http://127.0.0.1:8411/view/docs/%E9%9B%AA%20%231%25.md" in result.output
    server_class.assert_called_once()


def test_startup_urls_do_not_land_on_a_redirect(tmp_path: Path) -> None:
    """Readiness probes retry a redirect, so no startup URL may point at one.

    ``wait_for_http_ok_then`` opens the browser only on 2xx and gives up only on
    4xx, so a startup URL that redirects would poll until it times out.
    """

    server._set_root_dir(tmp_path)
    try:
        client = TestClient(server.app)
        for logical_path in ("", "docs/guide.md"):
            route = format_view_href(logical_path)
            assert client.get(route, follow_redirects=False).status_code == 200, route
    finally:
        server._set_root_dir(Path())


def test_serve_cli_emits_the_canonical_root_url_without_a_selected_path(
    tmp_path: Path,
) -> None:
    """A bare startup prints `/view/` rather than the redirecting origin."""

    (tmp_path / "README.md").write_text("# Read me")

    with (
        patch("metabrowser.cli.serve._QuietForceExitServer") as server_class,
        patch("metabrowser.cli.serve.find_available_local_port", return_value=8411),
    ):
        result = runner.invoke(_app, [str(tmp_path), "--no-open"])

    assert result.exit_code == 0, result.exception
    # The URL is read as a token rather than by what follows it: a checkout
    # appends a build marker after it, and the claim here is about the URL
    # ending at /view/ rather than about it ending the line.
    serving = next(line for line in result.output.splitlines() if " at http" in line)
    url = serving.split(" at ", 1)[1].split()[0]
    assert url == "http://127.0.0.1:8411/view/"
    server_class.assert_called_once()


def test_a_root_under_the_home_directory_is_shown_with_a_tilde(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The prefix is identical on every page, so every character it spends is
    width taken from the part of the address that changes.

    A shortening and not a rewrite: it happens only where it is a fact, and
    falls through to the absolute path everywhere else.
    """

    home = (tmp_path / "home" / "someone").resolve()
    (home / "wrk" / "project").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    server._set_root_dir(home / "wrk" / "project")
    try:
        assert server._display_root_str() == str(Path("~") / "wrk" / "project")
        # The absolute root is still what the API reports and paths resolve on.
        assert server._served_root_str() == str(home / "wrk" / "project")

        server._set_root_dir(home)
        assert server._display_root_str() == "~"

        outside = (tmp_path / "elsewhere").resolve()
        outside.mkdir()
        server._set_root_dir(outside)
        assert server._display_root_str() == str(outside)
    finally:
        server._set_root_dir(Path())


def test_the_header_prefix_gives_way_from_its_start_and_reads_at_row_weight() -> None:
    """Two properties of the dimmed prefix, both about what survives.

    It truncates from the START, because the end of a path is the half that
    says where you are and the beginning is the same on every page. And it is
    bold like the crumbs after it: grey already carries "this is context",
    so the weight does not need to say it a second time, and one address at
    two weights reads as two things.
    """

    css = (Path(server.STATIC_DIR) / "styles.css").read_text()
    start = css.index(".file-header-root {")
    block = css[start : css.index("}", start)]
    assert "direction: rtl" in block
    assert "text-overflow: ellipsis" in block
    assert "font-weight" not in block, (
        "the prefix inherits the container's weight rather than setting its own"
    )
