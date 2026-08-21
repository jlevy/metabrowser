from __future__ import annotations

import re

from devtools.public_hygiene import (
    COMMON_DOC_FOOTER,
    ROOT,
    _git_ignored,
    _text_files,
    find_documentation_findings,
    find_hygiene_findings,
)


def test_public_issue_tracking_language_is_allowed() -> None:
    text = "Track this work as an mb-abcd bead and sync it before handoff."

    assert find_hygiene_findings("AGENTS.md", text) == []


def test_public_project_plan_path_is_allowed() -> None:
    public_plan_path = "docs" + "/project/specs/active/plan-2026-07-17-scalable-file-search.md"

    assert find_hygiene_findings("README.md", public_plan_path) == []


def test_private_guidance_path_is_rejected() -> None:
    private_guidance_path = "docs" + "/general/guidelines/example.md"

    assert find_hygiene_findings("README.md", private_guidance_path) == [
        "README.md:1: private guidance path"
    ]


def test_dangling_legacy_documentation_names_are_rejected() -> None:
    names = (
        "browser-smoke" + ".playbook.md",
        "realtime-debugging" + ".runbook.md",
        "metabrowser" + "-plugins.md",
        "see kpress" + "-design.md",
    )
    for name in names:
        assert find_hygiene_findings("src/metabrowser/example.py", name) == [
            "src/metabrowser/example.py:1: dangling legacy documentation name"
        ]

    public_url = "https://github.com/jlevy/kpress/blob/v0.2.2/docs/kpress" + "-design.md"
    assert find_hygiene_findings("src/metabrowser/example.py", public_url) == []


def test_terminal_private_home_paths_are_rejected() -> None:
    home_paths = (
        "/" + "Users/alice",
        "/" + "home/alice",
        "/" + "Users/alice/project",
        "/" + "home/alice/project",
    )
    sources = ("README.md", "metabrowser-0.1.0/README.md")

    for source in sources:
        for home_path in home_paths:
            assert find_hygiene_findings(source, home_path) == [f"{source}:1: private home path"]


def test_implementation_plan_markers_are_rejected() -> None:
    markers = (
        "Implemented under P1.13.",
        "Phase 5 wires this behavior.",
        "Matches origin/main.",
        "Tracked in the design-system consolidation plan.",
        "A follow-up spec can wire it.",
    )

    for source in ("src/metabrowser/example.py", "tests/test_example.py"):
        for marker in markers:
            assert find_hygiene_findings(source, marker) == [
                f"{source}:1: stale implementation-plan marker"
            ]


def test_public_hygiene_marker_fixtures_are_explicitly_excluded() -> None:
    assert (
        find_hygiene_findings("tests/test_public_hygiene.py", "Phase 5 wires this behavior.") == []
    )


def test_production_property_names_are_not_plan_markers() -> None:
    for expression in ("value.p0.parsed.y", "value.P0.parsed.y"):
        assert find_hygiene_findings("src/metabrowser/example.js", expression) == []


def test_generated_tbd_content_is_not_scanned() -> None:
    tbd_docs = ROOT / ".tbd" / "docs"
    tbd_workspaces = ROOT / ".tbd" / "workspaces"
    text_files = _text_files()

    assert all(not path.is_relative_to(tbd_docs) for path in text_files)
    assert all(not path.is_relative_to(tbd_workspaces) for path in text_files)


def test_project_markdown_requires_common_document_footer() -> None:
    project_doc = ROOT / "docs" / "example.md"

    assert find_documentation_findings(project_doc, "# Example\n") == [
        "docs/example.md: missing common-doc-guidelines footer"
    ]
    assert find_documentation_findings(project_doc, COMMON_DOC_FOOTER) == []
    assert find_documentation_findings(ROOT / "src" / "example.py", "") == []


def test_generated_skills_and_rendering_fixtures_are_footer_exempt() -> None:
    generated_skill = ROOT / ".agents" / "skills" / "tbd" / "SKILL.md"
    rendering_fixture = ROOT / "tests" / "manual-fixtures" / "overview.md"

    assert find_documentation_findings(generated_skill, "") == []
    assert find_documentation_findings(rendering_fixture, "") == []


def test_git_ignored_local_residue_is_excluded_but_tracked_files_kept() -> None:
    # Claude Code writes .claude/settings.local.json with absolute home paths;
    # it is git-ignored and never published, so the scan must skip it while
    # still covering tracked files. git check-ignore needs no file on disk.
    ignored = ROOT / ".claude" / "settings.local.json"
    tracked = ROOT / "AGENTS.md"

    result = _git_ignored([ignored, tracked])

    assert ignored in result
    assert tracked not in result


def test_git_ignored_preserves_unusual_filenames() -> None:
    ignored = ROOT / "ignored\nname.pyc"

    assert _git_ignored([ignored]) == {ignored}


SKILL_PATH = "skills/metabrowser/SKILL.md"
# Worked "pin the release" examples live in these docs; the release workflow
# keeps them on the current version. The skill is deliberately absent.
PINNED_EXAMPLE_DOCS = ("README.md", "docs/installation.md")
_METABROWSER_PIN = re.compile(r"metabrowser[@=]=?(\d+\.\d+\.\d+)")


def test_agent_skill_runner_tracks_the_latest_release() -> None:
    # A version frozen in the skill goes stale on every release and cannot be
    # updated in already-installed copies. The cool-off is enforced by uv
    # configuration instead, so the runner deliberately stays unpinned.
    skill = (ROOT / SKILL_PATH).read_text(encoding="utf-8")

    assert "uvx metabrowser@latest" in skill
    assert not _METABROWSER_PIN.search(skill), "SKILL.md froze a Metabrowser version"


def test_agent_skill_routes_to_uv_cool_off_configuration() -> None:
    # Dropping the pin only stays safe while the skill names the mechanism that
    # replaced it.
    skill = (ROOT / SKILL_PATH).read_text(encoding="utf-8")

    assert "exclude-newer" in skill or "UV_EXCLUDE_NEWER" in skill


def test_documented_pin_examples_agree_across_docs() -> None:
    found = {
        relative: sorted(
            set(_METABROWSER_PIN.findall((ROOT / relative).read_text(encoding="utf-8")))
        )
        for relative in PINNED_EXAMPLE_DOCS
    }

    versions = {version for versions in found.values() for version in versions}
    assert len(versions) <= 1, f"documented pin examples disagree: {found}"


def test_agent_skill_prefers_the_local_command_over_the_runner() -> None:
    # The zero-install fallback must stay a fallback: an agent that already has
    # metab should not pay a uvx resolve, per cli-agent-skill-patterns (L1).
    skill = (ROOT / SKILL_PATH).read_text(encoding="utf-8")

    assert "command -v metab" in skill
    assert skill.index("command -v metab") < skill.index("uvx metabrowser@")
