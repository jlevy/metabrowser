from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from devtools.public_hygiene import ROOT, _git_ignored, _text_files, find_hygiene_findings


def test_public_issue_tracking_language_is_allowed() -> None:
    text = "Track this work as an mb-abcd bead and sync it before handoff."

    assert find_hygiene_findings("AGENTS.md", text) == []


def test_private_plan_path_is_rejected() -> None:
    private_plan_path = "docs" + "/project/specs/active/example.md"

    assert find_hygiene_findings("README.md", private_plan_path) == [
        "README.md:1: private plan path"
    ]


def test_private_guidance_path_is_rejected() -> None:
    private_guidance_path = "docs" + "/general/guidelines/example.md"

    assert find_hygiene_findings("README.md", private_guidance_path) == [
        "README.md:1: private plan path"
    ]


def test_generated_tbd_document_cache_is_not_scanned() -> None:
    tbd_docs = ROOT / ".tbd" / "docs"

    assert all(not path.is_relative_to(tbd_docs) for path in _text_files())


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


def test_codex_hook_commands_anchor_to_repository_root() -> None:
    payload = json.loads((ROOT / ".codex" / "hooks.json").read_text())
    commands = [
        hook["command"]
        for groups in payload["hooks"].values()
        for group in groups
        for hook in group["hooks"]
    ]

    assert commands
    assert all("$(git rev-parse --show-toplevel)" in command for command in commands)
    assert all("bash .codex/" not in command for command in commands)


def test_claude_hook_commands_anchor_to_project_root() -> None:
    payload = json.loads((ROOT / ".claude" / "settings.json").read_text())
    commands = [
        hook["command"]
        for groups in payload["hooks"].values()
        for group in groups
        for hook in group["hooks"]
    ]

    assert commands
    assert all('"$CLAUDE_PROJECT_DIR"' in command for command in commands)
    assert all("bash .claude/" not in command for command in commands)


def test_agent_tbd_skills_use_repository_version_pin() -> None:
    for relative in (".agents/skills/tbd/SKILL.md", ".claude/skills/tbd/SKILL.md"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "get-tbd@0.4.0" in text
        assert "@latest" not in text


def test_gh_setup_skips_unsupported_platform_without_failing(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_uname = fake_bin / "uname"
    fake_uname.write_text(
        "#!/bin/bash\n"
        'if [ "${1:-}" = "-s" ]; then\n'
        '  printf "Windows_NT\\n"\n'
        "else\n"
        '  printf "x86_64\\n"\n'
        "fi\n",
        encoding="utf-8",
    )
    fake_uname.chmod(0o755)
    bash_env = tmp_path / "bash-env"
    bash_env.write_text(
        "command() {\n"
        '  if [ "${1:-}" = "-v" ] && [ "${2:-}" = "gh" ]; then return 1; fi\n'
        '  builtin command "$@"\n'
        "}\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update(
        {
            "BASH_ENV": str(bash_env),
            "HOME": str(tmp_path / "home"),
            "PATH": f"{fake_bin}:{env['PATH']}",
        }
    )

    for relative in (".claude/scripts/ensure-gh-cli.sh", ".codex/ensure-gh-cli.sh"):
        result = subprocess.run(
            ["/bin/bash", str(ROOT / relative)],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        assert "skipping automatic installation" in result.stdout
