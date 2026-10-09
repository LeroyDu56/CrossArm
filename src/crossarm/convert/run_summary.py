# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""What one conversion of one task came to, in two files written next to its reports, and what changed since the
previous conversion.

    crossarm_summary.json         the machine summary: CrossArm version, date, backup and task, a fingerprint of
                                  the RAPID files read, the options used, the TODO and warnings by cause, the share
                                  converted by area, the decision. The ONLY source of a comparison: a later
                                  conversion reads it, never an HTML report.
    crossarm_report_summary.md    one page to print or send: the decision and its rule, the figures, the causes, what
                                  to do first and who acts, the controller resources near their limit, what --karel
                                  did, the licence; and the comparison, when there is one.

The previous conversion is the crossarm_summary.json found in the output folder before it is overwritten, or else in
the newest earlier output of the same input (crossarm_<name>, crossarm_<name>_2...: pipeline.previous_summaries).
It is compared only if it is a conversion of the same task: the same RAPID files (same fingerprint) say "since the
previous conversion"; other contents of the same files say plainly that the backup changed and how many files
differ, the figures labelled as such; a summary sharing no RAPID file with this one is another backup, never
compared, whatever its name.
"""

import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from crossarm import __version__
from crossarm.convert import analysis, triage
from crossarm.convert.config import ConversionConfig
from crossarm.convert.coverage import MOTION, fmt_percent
from crossarm.convert.translate import ConversionResult

SUMMARY_JSON = "crossarm_summary.json"
SUMMARY_MD = "crossarm_report_summary.md"
FORMAT = 1  # crossarm_summary.json's layout; a later layout adds keys, never redefines one

# The options a conversion records, as the user names them; a difference with the previous one is said.
OPTIONS = {
    "karel": "--karel",
    "map": "a mapping file (--map)",
    "provided_routines": "routines provided (external_routines)",
    "move_routines": "move routines converted (move_routines)",
    "keep_taught": "--keep-taught",
    "fanuc": "the robot's programs (--fanuc)",
    "tp": ".TP export (--tp)",
    "eio": "EIO.cfg",
}


# ---------------------------------------------------------------------------
# The sources' fingerprint
# ---------------------------------------------------------------------------


def file_hashes(paths: Iterable[Path]) -> dict[str, str]:
    """Each RAPID file read -> the SHA-256 of its bytes, by name (with its folder when two files share a name)."""
    paths = [Path(p) for p in paths]
    names = Counter(p.name for p in paths)
    out = {}
    for path in paths:
        name = path.name if names[path.name] == 1 else f"{path.parent.name}/{path.name}"
        out[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return dict(sorted(out.items()))


def fingerprint(files: dict[str, str]) -> str:
    """One hash for the RAPID files read: their names and hashes, sorted."""
    return hashlib.sha256("".join(f"{name}:{digest}\n" for name, digest in sorted(files.items())).encode()).hexdigest()


def files_differ(before: dict[str, str], now: dict[str, str]) -> int:
    """The files added, removed or changed between two conversions."""
    return sum(1 for name in set(before) | set(now) if before.get(name) != now.get(name))


# ---------------------------------------------------------------------------
# crossarm_summary.json
# ---------------------------------------------------------------------------


def build_summary(result: ConversionResult, config: ConversionConfig, *, backup: str, task: str,
                  files: dict[str, str], options: dict[str, object], licensed: bool) -> dict:  # fmt: skip
    """The machine summary of one task's conversion (crossarm_summary.json)."""
    decision = analysis.verdict(result)
    coverage = result.coverage
    todo = Counter(note.category for note in result.notes if note.kind == "TODO")
    warnings = Counter(note.category for note in result.notes if note.kind == "WARNING")
    points, kept, again = analysis.touch_up_counts(result)
    return {
        "format": FORMAT,
        "crossarm": __version__,
        "date": f"{config.timestamp:%Y-%m-%dT%H:%M:%S}",
        "backup": backup,
        "task": task,
        "sources": {"fingerprint": fingerprint(files), "files": files},
        "options": options,
        "verdict": decision.level,
        "blocking_causes": dict(decision.blocking),
        "programs": len(result.programs),
        "programs_ready": result.clean_programs(),
        "todo": result.todo_count,
        "warnings": sum(warnings.values()),
        "todo_by_cause": dict(sorted(todo.items(), key=lambda kv: (-kv[1], kv[0]))),
        "warnings_by_cause": dict(sorted(warnings.items(), key=lambda kv: (-kv[1], kv[0]))),
        "instructions": coverage.total,
        "converted_percent": coverage.percent if coverage.total else None,
        "converted_by_area": {share.area: share.percent for share in coverage.shares},
        "points": points,
        "points_kept": kept,
        "points_again": again,
        "karel_todo": result.karel_todo,
        "licence": "licensed" if licensed else "evaluation",
    }


def write_summary(folder: Path, summary: dict) -> Path:
    path = folder / SUMMARY_JSON
    path.write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def read_summary(path: Path) -> dict | None:
    """An earlier conversion's summary; None when there is none, or it cannot be read as one."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("format"), int) or not isinstance(data.get("sources"), dict):
        return None
    return data


# ---------------------------------------------------------------------------
# Since the previous conversion
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Since:
    """What changed between the previous conversion of a task and this one."""

    same_backup: bool  # the same RAPID files, byte for byte
    files_differ: int  # else: the files added, removed or changed
    version: str  # the previous conversion's CrossArm version and date
    date: str
    todo: tuple[int, int]  # (then, now)
    warnings: tuple[int, int]
    percent: tuple[float | None, float | None]
    gained: tuple[tuple[str, int], ...]  # TODO causes there now and not then, with their TODO now
    lost: tuple[tuple[str, int], ...]  # TODO causes there then and not now, with their TODO then
    options: tuple[str, ...]  # the options that differ, in words ("--karel: now only")

    @property
    def when(self) -> str:
        return f"CrossArm {self.version}, {self.date.replace('T', ' ')[:16]}"

    def figures(self) -> str:
        """'TODO 763 -> 700, warnings 117 -> 117, converted 86.9 % -> 88.0 %'."""
        then, now = self.percent
        parts = [f"TODO {self.todo[0]:,} -> {self.todo[1]:,}", f"warnings {self.warnings[0]:,} -> {self.warnings[1]:,}"]
        if then is not None or now is not None:
            parts.append(f"converted {fmt_percent(then) if then is not None else 'none'} ->"
                         f" {fmt_percent(now) if now is not None else 'none'}")  # fmt: skip
        return ", ".join(parts)

    def causes(self, shown: int = 4) -> str:
        """'causes gone: A (12), B (3); new causes: C (2)', or ''."""
        out = []
        for title, causes in (("causes gone", self.lost), ("new causes", self.gained)):
            if causes:
                more = f" and {len(causes) - shown} more" if len(causes) > shown else ""
                out.append(f"{title}: " + ", ".join(f"{cause} ({n})" for cause, n in causes[:shown]) + more)
        return "; ".join(out)

    def headline(self) -> str:
        """The first words: what is compared with what."""
        if self.same_backup:
            return f"Since the previous conversion ({self.when}), same RAPID files:"
        files = f"{self.files_differ} RAPID file{'s' if self.files_differ != 1 else ''} differ"
        return (f"The backup changed since the previous conversion ({self.when}): {files}. Figures then (other files)"
                " and now:")  # fmt: skip

    def text(self) -> str:
        """One paragraph, as the analysis, the summary and the window say it."""
        out = f"{self.headline()} {self.figures()}."
        causes = self.causes()
        if causes:
            out += f" {causes[0].upper()}{causes[1:]}."
        if self.options:
            out += f" Options differ: {'; '.join(self.options)}."
        return out

    def short(self) -> str:
        """For the window: 'Since the previous conversion: TODO 763 -> 700, converted 86.9 % -> 88.0 %.'"""
        then, now = self.percent
        what = f"TODO {self.todo[0]:,} -> {self.todo[1]:,}"
        if then is not None and now is not None:
            what += f", converted {fmt_percent(then)} -> {fmt_percent(now)}"
        lead = "Since the previous conversion" if self.same_backup else (
            f"Backup changed ({self.files_differ} file{'s' if self.files_differ != 1 else ''} differ) since the previous"
            " conversion")  # fmt: skip
        return f"{lead}: {what}" + (f" (options differ: {'; '.join(self.options)})" if self.options else "") + "."


def _option_change(key: str, then: object, now: object) -> str:
    name = OPTIONS.get(key, key)
    if then == now:
        return ""
    if isinstance(then, bool) or isinstance(now, bool) or then is None or now is None:
        if bool(now) and not bool(then):
            return f"{name}: now only"
        if bool(then) and not bool(now):
            return f"{name}: then only"
        return ""
    return f"{name}: {then} -> {now}"


def _causes(data: dict, key: str) -> dict[str, int]:
    value = data.get(key)
    return {str(k): int(v) for k, v in value.items() if isinstance(v, int)} if isinstance(value, dict) else {}


def compare(previous: dict | None, current: dict) -> Since | None:
    """What changed since `previous` (an earlier crossarm_summary.json); None when it is not the same task of the same
    backup: another task, or no RAPID file in common (another backup, whatever its name)."""
    if not previous or previous.get("task") != current.get("task"):
        return None
    before = previous.get("sources", {}).get("files")
    now = current["sources"]["files"]
    if not isinstance(before, dict) or not before:
        return None
    same = previous.get("sources", {}).get("fingerprint") == current["sources"]["fingerprint"]
    if not same and not set(before) & set(now):
        return None
    then_causes, now_causes = _causes(previous, "todo_by_cause"), _causes(current, "todo_by_cause")
    gained = tuple(sorted(((c, n) for c, n in now_causes.items() if c not in then_causes), key=lambda kv: (-kv[1], kv[0])))
    lost = tuple(sorted(((c, n) for c, n in then_causes.items() if c not in now_causes), key=lambda kv: (-kv[1], kv[0])))
    then_options = previous.get("options") if isinstance(previous.get("options"), dict) else {}
    options = tuple(change for key in OPTIONS
                    if (change := _option_change(key, then_options.get(key), current["options"].get(key))))  # fmt: skip

    def number(data: dict, key: str) -> int:
        value = data.get(key)
        return value if isinstance(value, int) else 0

    def share(data: dict) -> float | None:
        value = data.get("converted_percent")
        return float(value) if isinstance(value, (int, float)) else None

    return Since(
        same_backup=same, files_differ=0 if same else files_differ(before, now),
        version=str(previous.get("crossarm", "?")), date=str(previous.get("date", "?")),
        todo=(number(previous, "todo"), current["todo"]), warnings=(number(previous, "warnings"), current["warnings"]),
        percent=(share(previous), current["converted_percent"]), gained=gained, lost=lost, options=options,
    )  # fmt: skip


def newest(summaries: Iterable[dict]) -> dict | None:
    """The most recent of earlier summaries, by the date they were written."""
    dated = [s for s in summaries if isinstance(s.get("date"), str)]
    return max(dated, key=lambda s: s["date"]) if dated else None


# ---------------------------------------------------------------------------
# crossarm_report_summary.md
# ---------------------------------------------------------------------------


def summary_markdown(result: ConversionResult, config: ConversionConfig, summary: dict, *, licence_line: str = "",
                     since: Since | None = None) -> str:  # fmt: skip
    """One page: the decision, the figures, the causes, what to do first, the resources near their limit, --karel."""
    decision = analysis.verdict(result)
    coverage = result.coverage
    points, kept, again = analysis.touch_up_counts(result)
    warnings = summary["warnings"]
    lines = [
        f"# CrossArm summary: {summary['backup']}, {summary['task']}",
        "",
        f"CrossArm {__version__} · {config.timestamp:%Y-%m-%d %H:%M}" + (f" · {licence_line}" if licence_line else ""),
        "",
        f"**{decision.level.upper()}**: {decision.sentence}",
        "",
        f"_{decision.rule}_",
        "",
    ]
    figures = []
    if coverage.total:
        figures.append(f"- **{fmt_percent(coverage.percent)}** of the {coverage.total:,} RAPID instructions converted"
                       + "".join(f"; {share.area.lower()} {fmt_percent(share.percent)}"
                                 for share in coverage.shares if share.area == MOTION) + ".")  # fmt: skip
    figures.append(f"- **{result.clean_programs()} of {len(result.programs)}** programs ready as is (no TODO).")
    figures.append(f"- **{result.todo_count:,} TODO** to finish by hand, {warnings:,} warning{'s' if warnings != 1 else ''}"
                   " to check.")  # fmt: skip
    if points:
        figures.append(f"- {points - kept:,} point{'s' if points - kept != 1 else ''} to touch up on the robot"
                       + (f" ({kept:,} kept as touched up, {again:,} to touch up again)" if kept or again else "") + ".")  # fmt: skip
    if since is not None:
        figures.append(f"- {since.text()}")
    sentence = analysis.business(result)
    if sentence:
        figures.append(f"- {sentence}")
    lines += [*figures, ""]

    causes = analysis.top_causes(result)
    if causes:
        lines += ["## Where the TODO come from", "", "| Cause | Family | TODO | Share | |", "|---|---|---:|---:|---|"]
        lines += [f"| {c.category} | {triage.family(c.category)} | {c.count} | {c.share:.0f} % |"
                  f" {'blocking' if c.blocking else ''} |" for c in causes]  # fmt: skip
        left = len(summary["todo_by_cause"]) - len(causes)
        if left > 0:
            lines.append(f"\n{left} other cause{'s' if left > 1 else ''}: see the report.")
        lines.append("")
    actions = analysis.priority_actions(result, config)
    if actions:
        lines += ["## What to do first", ""]
        for n, action in enumerate(actions, 1):
            meta = f" _{action.meta}._" if action.meta else ""
            lines.append(f"{n}. **{action.title}**{meta}")
        lines.append("")
    near = analysis.near_limit(result.capacity)
    if near:
        lines += ["## Controller capacity near or over the limit", ""]
        lines += [f"- {c.resource}: {c.used} used, limit {'—' if c.limit is None else c.limit}:"
                  f" {analysis.capacity_status(c)}" for c in near]  # fmt: skip
        lines.append("")
    karel = analysis.karel_use(result)
    if karel:
        lines += ["## --karel", "", karel, ""]
    elif result.karel_todo:
        lines += ["## --karel", "", (f"Not used: {result.karel_todo} TODO would be converted with --karel (the robot"
                                     " needs the KAREL option, R632)."), ""]  # fmt: skip
    lines += ["---", "", ("The detail: `crossarm_report.html` (open it in a browser), `crossarm_report.md`;"
                          " the figures for a later comparison: `crossarm_summary.json`.")]  # fmt: skip
    return "\n".join(lines) + "\n"
