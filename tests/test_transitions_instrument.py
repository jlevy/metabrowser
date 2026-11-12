"""The transition-navigation instrument (explorations/performance-loop/transitions*.mjs).

Its pure logic runs browserless: request classes, cache disposition over recorded DevTools
event sequences, frame accounting, region movement, every refusal and verdict of
``compare`` over fixture rows, and process cleanup. Its recorder runs in a real headless
Chrome on synthetic pages, because what it measures is paint and the frame clock:
readiness against the input, the presentation of the ready frame, content on screen, and
304s a server logged.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from tests.required_tools import require_chrome, require_git, require_node

ROOT = Path(__file__).resolve().parents[1]
DOM = Path(__file__).parent / "dom"
TRANSITIONS = ROOT / "explorations" / "performance-loop" / "transitions.mjs"


def test_transition_instrument_logic() -> None:
    result = subprocess.run(
        [require_node(), str(DOM / "transitions-instrument-behavior.mjs")],
        capture_output=True,
        check=False,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "transitions instrument: 36 checks passed\n"


@pytest.mark.parametrize(
    ("group", "count"), [("frames", 4), ("frames2", 3), ("content", 8), ("network", 1)]
)
def test_transition_recorder_in_chrome(group: str, count: int) -> None:
    chrome = require_chrome()
    result = subprocess.run(
        [require_node(), str(DOM / "transitions-recorder-chrome.mjs"), group],
        capture_output=True,
        check=False,
        text=True,
        timeout=50,
        env={**os.environ, "CHROME_BIN": chrome},
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout == f"transitions recorder {group}: {count} checks passed\n"


# A stand-in `metab`: it reports a version, then serves a complete inventory and drops
# every other request, so the start fails after the process exists. Each one records
# whether the one before it is still running when it starts.
STAND_IN = """#!{node}
const fs = require("node:fs");
const http = require("node:http");
const pidFile = {pid_file}, overlap = {overlap};
if (process.argv.includes("--version")) {{ console.log("metab stand-in 1.0"); process.exit(0); }}
if (fs.existsSync(pidFile)) {{
  const before = Number(fs.readFileSync(pidFile, "utf8"));
  try {{ process.kill(before, 0); fs.writeFileSync(overlap, String(before)); }} catch (_error) {{}}
}}
fs.writeFileSync(pidFile, String(process.pid));
const port = Number(process.argv[process.argv.indexOf("--port") + 1]);
http.createServer((req, res) => {{
  if (req.url.startsWith("/api/index/progress")) {{
    res.end(JSON.stringify({{ complete: true, indexed_files: 1 }}));
  }} else {{
    req.socket.destroy();
  }}
}}).listen(port, "127.0.0.1");
"""


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_a_server_that_fails_after_its_spawn_is_stopped(tmp_path: Path) -> None:
    git = require_git()
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "README.md").write_text("# corpus\n", encoding="utf-8")
    for args in (
        ["init", "-q"],
        ["add", "README.md"],
        ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "c"],
    ):
        subprocess.run([git, "-C", str(corpus), *args], check=True, timeout=20)
    metab = tmp_path / "env" / "bin" / "metab"
    metab.parent.mkdir(parents=True)
    pid_file = tmp_path / "server.pid"
    overlap = tmp_path / "overlap"
    metab.write_text(
        STAND_IN.format(
            node=require_node(),
            pid_file=json.dumps(str(pid_file)),
            overlap=json.dumps(str(overlap)),
        ),
        encoding="utf-8",
    )
    metab.chmod(0o755)
    out = tmp_path / "runs.jsonl"
    result = subprocess.run(
        [
            require_node(),
            str(TRANSITIONS),
            "run",
            "--exp",
            "exp-999",
            "--corpus",
            str(corpus),
            "--condition",
            f"standin={metab}",
            "--runs",
            "2",
            "--out",
            str(out),
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=45,
        env={**os.environ, "TRANSITIONS_BENCH": str(tmp_path / "bench")},
    )
    assert result.returncode == 1, result.stderr
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    for row in rows:
        assert row["valid"] is False
        assert any(guard == "run_error" for guard, _ in row["refusals"]), row["refusals"]
    assert not overlap.exists(), "run 1's server was still running when run 2 started"
    assert not _alive(int(pid_file.read_text(encoding="utf-8")))
