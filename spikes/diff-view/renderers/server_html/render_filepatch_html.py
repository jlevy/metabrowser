"""Spike: server-side HTML projection of FilePatch (GitLab Rapid Diffs pattern).

Renders the same table markup as the custom client renderer, as an HTML string in
Python, so the client only inserts it. Records server render time per fixture.
"""

from __future__ import annotations

import html
import json
import time
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "fixtures" / "out"


def render(patch: dict) -> str:
    parts: list[str] = ['<table class="dv-table"><tbody>']
    for hunk in patch["hunks"]:
        section = html.escape(hunk.get("section", ""))
        parts.append(
            f'<tr class="dv-hunk"><td colspan="4">@@ -{hunk["oldStart"]},{hunk["oldLines"]}'
            f' +{hunk["newStart"]},{hunk["newLines"]} @@ {section}</td></tr>'
        )
        old_no = hunk["oldStart"]
        new_no = hunk["newStart"]
        for group in hunk["groups"]:
            kind = group["type"]
            for line in group["lines"]:
                code = html.escape(line)
                if kind == "context":
                    parts.append(
                        f'<tr class="dv-ctx"><td class="dv-num">{old_no}</td>'
                        f'<td class="dv-num">{new_no}</td><td class="dv-sign"> </td>'
                        f'<td class="dv-code">{code}</td></tr>'
                    )
                    old_no += 1
                    new_no += 1
                elif kind == "add":
                    parts.append(
                        f'<tr class="dv-add"><td class="dv-num"></td>'
                        f'<td class="dv-num">{new_no}</td><td class="dv-sign">+</td>'
                        f'<td class="dv-code">{code}</td></tr>'
                    )
                    new_no += 1
                else:
                    parts.append(
                        f'<tr class="dv-del"><td class="dv-num">{old_no}</td>'
                        f'<td class="dv-num"></td><td class="dv-sign">-</td>'
                        f'<td class="dv-code">{code}</td></tr>'
                    )
                    old_no += 1
    parts.append("</tbody></table>")
    return "".join(parts)


def main() -> None:
    timings: dict[str, dict[str, float]] = {}
    for stem in ("small", "medium", "huge"):
        patch = json.loads((OUT / f"fp_{stem}.json").read_text())
        t0 = time.perf_counter()
        markup = render(patch)
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        (OUT / f"html_{stem}.html").write_text(markup)
        timings[stem] = {"serverRenderMs": elapsed, "htmlBytes": len(markup)}
    (OUT / "server_html_timings.json").write_text(json.dumps(timings, indent=1))
    print(json.dumps(timings, indent=1))


if __name__ == "__main__":
    main()
