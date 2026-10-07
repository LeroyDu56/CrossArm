# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Markdown report -> standalone HTML page (double-click to read, no tool needed).

Renders only the Markdown subset build_report() produces: headings, paragraphs,
bullet lists, block quotes, tables, `code` and **bold**. Everything is escaped.
"""

import html
import re

CSS = """
:root { --bg: #ffffff; --fg: #1f2328; --muted: #59636e; --line: #d1d9e0; --head: #f6f8fa;
        --code: #eff1f3; --todo: #b35900; --warn: #7d4e00; --accent: #0969da; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #0d1117; --fg: #e6edf3; --muted: #9198a1; --line: #3d444d; --head: #151b23;
          --code: #262c36; --todo: #f0883e; --warn: #d29922; --accent: #4493f8; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg);
       font: 15px/1.55 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
main { max-width: 1100px; margin: 0 auto; padding: 24px 16px 64px; }
h1 { font-size: 1.8em; border-bottom: 1px solid var(--line); padding-bottom: .3em; }
h2 { font-size: 1.35em; border-bottom: 1px solid var(--line); padding-bottom: .25em; margin-top: 2em; }
h3 { font-size: 1.1em; margin-top: 1.6em; }
code { background: var(--code); padding: .1em .35em; border-radius: 4px;
       font: .9em ui-monospace, Consolas, "Courier New", monospace; }
blockquote { margin: 1em 0; padding: .6em 1em; border-left: 4px solid var(--accent);
             background: var(--head); color: var(--fg); }
blockquote p { margin: .2em 0; }
.table-wrap { overflow-x: auto; margin: .8em 0; }
table { border-collapse: collapse; width: 100%; font-size: .92em; }
th, td { border: 1px solid var(--line); padding: 5px 9px; text-align: left; vertical-align: top; }
th { background: var(--head); }
td.kind-TODO { color: var(--todo); font-weight: 600; }
td.kind-WARNING { color: var(--warn); font-weight: 600; }
.muted { color: var(--muted); }
"""


def inline(text: str) -> str:
    out = []
    for i, part in enumerate(re.split(r"`([^`]*)`", text)):  # odd indices are code spans
        if i % 2:
            out.append(f"<code>{html.escape(part)}</code>")
        else:
            escaped = html.escape(part)
            out.append(re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped))
    return "".join(out)


def _cells(row: str) -> list[str]:
    # Split on '|' not preceded by a backslash (build_report escapes pipes inside cells).
    parts = re.split(r"(?<!\\)\|", row.strip().strip("|"))
    return [p.strip().replace("\\|", "|") for p in parts]


def markdown_to_html(markdown: str, title: str) -> str:
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n<style>{CSS}</style>\n</head>\n"
        "<body><main>\n" + markdown_body(markdown) + "\n</main></body>\n</html>\n"
    )


def markdown_body(markdown: str, ids: dict[str, str] | None = None) -> str:
    """The HTML of the Markdown subset, without the page around it. `ids`: heading text -> id, for the
    headings other parts of a page link to."""
    lines = markdown.splitlines()
    body: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            text = line[level:].strip()
            anchor = (ids or {}).get(text)
            attribute = f' id="{html.escape(anchor, quote=True)}"' if anchor else ""
            body.append(f"<h{level}{attribute}>{inline(text)}</h{level}>")
            i += 1
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(_cells(lines[i]))
                i += 1
            header, data = rows[0], [r for r in rows[1:] if not all(set(c) <= {"-", ":"} for c in r)]
            kind_col = header.index("Kind") if "Kind" in header else -1
            html_rows = ["<tr>" + "".join(f"<th>{inline(c)}</th>" for c in header) + "</tr>"]
            for row in data:
                cells = []
                for n, cell in enumerate(row):
                    css = f' class="kind-{html.escape(cell)}"' if n == kind_col else ""
                    cells.append(f"<td{css}>{inline(cell)}</td>")
                html_rows.append("<tr>" + "".join(cells) + "</tr>")
            body.append('<div class="table-wrap"><table>' + "".join(html_rows) + "</table></div>")
        elif line.startswith(">"):
            quote = []
            while i < len(lines) and lines[i].startswith(">"):
                quote.append(inline(lines[i].lstrip("> ").rstrip()))
                i += 1
            body.append("<blockquote><p>" + " ".join(quote) + "</p></blockquote>")
        elif line.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(f"<li>{inline(lines[i][2:])}</li>")
                i += 1
            body.append("<ul>" + "".join(items) + "</ul>")
        elif line.strip() == "_None._":
            body.append('<p class="muted">None.</p>')
            i += 1
        else:
            para = []
            while i < len(lines) and lines[i].strip() and not lines[i].startswith(("#", "|", ">", "- ")):
                para.append(inline(lines[i]))
                i += 1
            body.append("<p>" + " ".join(para) + "</p>")
    return "\n".join(body)
