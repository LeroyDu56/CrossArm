# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""The analysis the reports open on: a decision by a fixed rule, what to do first, where the TODO come from."""

import re

import pytest
from test_html_report import CELL, _convert, _Page

from crossarm.convert import ConversionConfig, analysis, build_report
from crossarm.convert.analysis import (
    BLOCKING,
    EMPTY,
    MAX_BLOCKING,
    MIN_CONVERTED,
    NOT_READY,
    READY,
    WORKABLE,
    decide,
    near_limit,
    priority_actions,
    top_causes,
    verdict,
)
from crossarm.convert.blockers import Blocker
from crossarm.convert.coverage import Coverage, Share
from crossarm.convert.html_report import build_html_report
from crossarm.convert.taught import AGAIN, Taught, TaughtPoint
from crossarm.convert.translate import Capacity, ConversionResult, Note

# ---------------------------------------------------------------------------
# The decision: each branch of the rule, at its thresholds
# ---------------------------------------------------------------------------

BLOCKER = (Blocker.CALIBRATION, 4)
PLANNED = [(Blocker.MISSING, 30), (Blocker.VALUE, 5)]


def _decide(percent: float, blocking: int = 0, todo: int = 10, over: tuple[str, ...] = (), programs: int = 5):
    causes = [(f"cause {i}", 1) for i in range(blocking)]
    return decide(programs=programs, percent=percent, todo=todo, blocking=causes, over=list(over),
                  causes=PLANNED + causes)  # fmt: skip


def test_ready_needs_every_instruction_converted_and_nothing_over_the_controller():
    assert _decide(100.0, todo=0).level == READY
    assert _decide(100.0, todo=0, over=("UTOOL",)).level == WORKABLE  # sorted out with the mapping file
    assert "capacity" in _decide(100.0, todo=0, over=("UTOOL",)).sentence
    # No TODO, but routines left out of the conversion: not everything is converted.
    left_out = _decide(95.0, todo=0)
    assert left_out.level == WORKABLE and "not converted (listed under Programs)" in left_out.sentence


def test_workable_from_the_thresholds_on_and_not_ready_below_them():
    assert _decide(MIN_CONVERTED, blocking=MAX_BLOCKING).level == WORKABLE  # both thresholds included
    assert _decide(MIN_CONVERTED - 0.1, blocking=0).level == NOT_READY
    assert _decide(100.0, blocking=MAX_BLOCKING + 1).level == NOT_READY
    assert _decide(90.0).sentence == "Workable with touch-up and planned work: 10 TODO with a known fix, no blocking cause."
    two = _decide(90.0, blocking=2)
    assert two.sentence == ("Workable with touch-up and planned work, plus 2 blocking causes to solve on the FANUC side:"
                            " cause 0, cause 1.")  # fmt: skip


def test_not_ready_names_the_work():
    low = _decide(77.6)
    assert low.sentence == ("Not ready for production without major work on the 22.4 % of the instructions not converted"
                            " (mostly routine or data not in the backup and value not known at conversion time).")  # fmt: skip
    many = _decide(97.0, blocking=MAX_BLOCKING + 2)
    assert many.sentence.startswith(f"Not ready for production without major work on {MAX_BLOCKING + 2} blocking causes"
                                    " (cause 0, cause 1, cause 2 and 2 more)")  # fmt: skip
    both = _decide(50.0, blocking=MAX_BLOCKING + 1)
    assert "not converted" in both.sentence and "blocking causes" in both.sentence
    assert _decide(0.0, programs=0, todo=0).level == EMPTY


def test_the_rule_applied_is_shown_with_the_figures_it_was_applied_to():
    rule = _decide(77.6, blocking=2).rule
    assert rule.startswith("Rule: ready when every instruction is converted; workable when at least")
    assert f"{MIN_CONVERTED:g} %" in rule and f"at most {MAX_BLOCKING} causes are blocking" in rule
    assert rule.endswith("Here: 77.6 % converted, 2 blocking causes.")
    assert _decide(77.6, blocking=2).brief.endswith(f"at most {MAX_BLOCKING} blocking causes (here 2).")


def test_the_thresholds_are_read_from_one_place(monkeypatch):
    monkeypatch.setattr(analysis, "MIN_CONVERTED", 70.0)
    monkeypatch.setattr(analysis, "MAX_BLOCKING", 1)
    assert _decide(75.0, blocking=1).level == WORKABLE and _decide(75.0, blocking=2).level == NOT_READY
    assert "at least 70 %" in _decide(75.0).rule and "at most 1 causes" in _decide(75.0).rule
    page = build_html_report(_convert(CELL), ConversionConfig(), ["cell.mod"], title="t")
    assert "at least 70 % of the RAPID instructions converted and at most 1 blocking causes" in page


def test_blocking_causes_are_those_a_fanuc_side_design_solves():
    known = {value for name, value in vars(Blocker).items() if name.isupper()}
    assert known >= BLOCKING  # spelled as the TODO are
    assert {Blocker.CALIBRATION, Blocker.RUNTIME_POSITION, Blocker.INTERRUPT, Blocker.INTERNAL} <= BLOCKING
    # Work to plan: a known fix the report gives.
    for planned in (Blocker.MISSING, Blocker.SIGNAL, Blocker.MOVE_ROUTINE, Blocker.NO_TP_EQUIVALENT, Blocker.HANDLER,
                    Blocker.VALUE, Blocker.CONDITION, Blocker.CALL_ARGS, Blocker.rapid("ERROR_HANDLER")):  # fmt: skip
        assert planned not in BLOCKING


# ---------------------------------------------------------------------------
# A result made by hand: TODO of every kind of action
# ---------------------------------------------------------------------------


def _result() -> ConversionResult:
    result = ConversionResult()
    result.coverage = Coverage((Share("Motion", 100, 90), Share("Error handling", 20, 2)))
    todo = [
        *(Note("MAIN", 10 + i, "TODO", f"routine 'ErrLogX' is not in the backup: add the module — `ErrLogX {i};`",
               Blocker.MISSING) for i in range(6)),
        Note("MAIN", 30, "TODO", "data 'nCycle' is not in the backup: add the module", Blocker.MISSING),
        *(Note(p, 40, "TODO", "SearchL \\Flanks: measured", Blocker.CALIBRATION) for p in ("CALIB", "CHECK")),
        Note("MAIN", 50, "TODO", "ERROR handlers are not supported", Blocker.rapid("ERROR_HANDLER")),
        Note("PICK", 60, "TODO", "Open: files and serial channels: TP reads and writes no file", Blocker.NO_TP_EQUIVALENT),
        Note("PICK", 61, "TODO", "x: sockets: TP has no network messaging", Blocker.NO_TP_EQUIVALENT),
        Note("PICK", 70, "TODO", "condition not convertible: f()", Blocker.CONDITION),
        Note("", None, "WARNING", "an assumption", Blocker.AXIS_CONVENTION),
    ]
    result.notes = todo
    result.capacity = [
        Capacity("UTOOL", 19, 19, 10, over=tuple(f"t{i}" for i in range(9))),
        Capacity("R", 9, 9, 10),  # near
        Capacity("F", 3, 3, 1024),  # fine
        Capacity("UFRAME", 12, 9, 9),  # above, kept in position registers: fits
    ]
    return result


def test_the_top_causes_count_share_and_one_example_each():
    causes = top_causes(_result())
    assert (causes[0].category, causes[0].count) == (Blocker.MISSING, 7)
    assert {(c.category, c.count) for c in causes[1:3]} == {(Blocker.CALIBRATION, 2), (Blocker.NO_TP_EQUIVALENT, 2)}
    assert len(causes) == 5 and round(causes[0].share) == 54  # 7 of the 13 TODO
    assert causes[0].example.rapid_line == 10  # the first of its most common case
    assert [c.blocking for c in causes if c.category in (Blocker.MISSING, Blocker.CALIBRATION)] == [False, True]


def test_priority_actions_come_from_the_blockers_most_unblocking_first():
    actions = priority_actions(_result())
    assert 3 <= len(actions) <= 7
    titles = [a.title for a in actions]
    assert titles[0] == "Bring the numbers within the controller"  # the programs do not load otherwise
    assert "UTOOL 19 needed, 10 held" in actions[0].detail and actions[0].href == "#an-capacity"
    assert titles[1] == "Provide the 2 routines and data the backup does not have"
    assert actions[1].detail.startswith("`ErrLogX`, `nCycle`; 7 TODO.") and actions[1].cause == Blocker.MISSING
    assert titles[2] == "Decide how the FANUC cell gets what the robot measures"
    assert "in `CALIB`, `CHECK`" in actions[2].detail and actions[2].cause == Blocker.CALIBRATION
    errors = next(a for a in actions if a.title == "Redo the error handling on the FANUC side")
    assert "not a CrossArm bug" in errors.detail
    no_tp = next(a for a in actions if a.title == "Redo what TP has nothing for on the FANUC side")
    assert "(files and serial channels, sockets)" in no_tp.detail and "not a CrossArm bug" in no_tp.detail
    assert titles[-1] == "Finish the other 1 TODO by hand"
    # Candidates for external_routines are pointed at.
    result = _result()
    result.provided_candidates = [object()]  # only counted
    assert "1 candidate listed in `crossarm_mapping.json`" in priority_actions(result)[1].detail


def test_at_most_seven_actions_touch_up_last_and_points_to_touch_up_again():
    result = _result()
    result.notes += [Note("MAIN", 80, "TODO", "m", cause) for cause in (Blocker.SIGNAL, Blocker.INTERNAL,
                     Blocker.RUNTIME_POSITION, Blocker.INTERRUPT, Blocker.STATIONARY)]  # fmt: skip
    result.taught = Taught("x", [TaughtPoint(AGAIN, "main", "pPick", 1, "MAIN", 3, 3, "moved")])
    actions = priority_actions(result)
    assert len(actions) == 7
    assert actions[-1].title == "Touch up again the 1 point that changed" and actions[-1].href == "#taught"
    # Little to do: still three things.
    calm = ConversionResult()
    calm.notes = [Note("", None, "WARNING", "w", Blocker.AXIS_CONVENTION)]
    assert len(priority_actions(calm)) == 1  # nothing written: only the warning to check
    assert len(priority_actions(_convert(CELL))) >= 3


def test_controller_capacity_shows_only_what_is_over_or_near_its_limit():
    near = near_limit(_result().capacity)
    assert [c.resource for c in near] == ["UTOOL", "R", "UFRAME"]
    page = build_html_report(_with_programs(_result()), ConversionConfig(), ["cell.mod"], title="t")
    box = page.split('id="an-capacity"')[1].split("</div></div>")[0]
    assert "UTOOL" in box and "over by 9: t0, t1, t2, t3 and 5 more" in box and "<td>F</td>" not in box
    assert "kept in position registers" in box
    fine = build_html_report(_convert(CELL), ConversionConfig(), ["cell.mod"], title="t")
    assert "every resource well within its limit" in fine and "near or over the limit" not in fine


def _with_programs(result: ConversionResult) -> ConversionResult:
    real = _convert(CELL)
    result.programs = real.programs
    result.rapid_sources = real.rapid_sources
    return result


# ---------------------------------------------------------------------------
# The page and the Markdown report
# ---------------------------------------------------------------------------


def test_the_page_opens_on_the_analysis_and_every_link_of_it_leads_somewhere():
    result = _convert(CELL)
    page = build_html_report(result, ConversionConfig(), ["cell.mod"], title="t")
    parsed = _Page()
    parsed.feed(page)
    assert parsed.loads == [] and set(parsed.links) <= parsed.ids
    sections = re.findall(r'<section id="([^"]+)">', page)
    assert sections[0] == "analysis" and sections[1] == "summary"
    analysis_html = page.split('<section id="analysis">')[1].split("</section>")[0]
    decision = verdict(result)
    assert decision.sentence in analysis_html and decision.rule in analysis_html
    assert "What to do first" in analysis_html and "Where the TODO come from" in analysis_html
    assert "Converted by area" in analysis_html
    assert 'href="#ck-fold"' in analysis_html and 'href="#review"' in analysis_html and 'href="#code"' in analysis_html
    assert "directly executable" in analysis_html  # the notice of the Markdown report, after the decision
    assert '<a href="#L-MAIN-12">MAIN l.12</a>' in analysis_html  # the example of a cause, linked to its line


def test_the_checklist_is_folded_and_still_printed_and_ticked():
    page = build_html_report(_convert(CELL), ConversionConfig(), ["cell.mod"], title="t")
    section = page.split('<section id="checklist">')[1].split("</section>")[0]
    fold = re.search(r"<details[^>]*id=\"ck-fold\"[^>]*>", section)[0]
    assert "open" not in fold  # folded by default
    assert section.index('id="ck-fold"') < section.index('<div id="ck" data-key=') < section.index("</details>")
    assert "beforeprint" in page and "ck-sum" in page


def test_the_analysis_escapes_what_comes_from_the_backup():
    result = _with_programs(_result())
    result.notes.append(Note("<b>P</b>", 3, "TODO", "<script>alert(1)</script> — `x`", "<i>cause</i>"))
    page = build_html_report(result, ConversionConfig(), ["<s>.mod"], title="t")
    analysis_html = page.split('<section id="analysis">')[1].split("</section>")[0]
    assert "<script>alert" not in page and "<b>P</b>" not in page and "<i>cause</i>" not in page
    assert "&lt;i&gt;cause&lt;/i&gt;" in analysis_html


def test_many_sources_are_folded_in_the_header():
    sources = [f"m{i}.mod" for i in range(30)]
    page = build_html_report(_convert(CELL), ConversionConfig(), sources, title="t")
    header = page.split("</header>")[0]
    assert "and 27 more" in header and "Every source file (30)" in header and "<code>m29.mod</code>" in header


def test_the_markdown_report_opens_on_the_analysis_too():
    result = _with_programs(_result())
    text = build_report(result, ConversionConfig(), ["cell.mod"])
    assert text.index("directly executable") < text.index("## Analysis") < text.index("## Summary")
    analysis_md = text.split("## Analysis")[1].split("## Summary")[0]
    assert f"- **{verdict(result).sentence}**" in analysis_md and "- Rule: ready when" in analysis_md
    assert "1. **Bring the numbers within the controller**: UTOOL 19 needed" in analysis_md
    assert "(Controller capacity.)" in analysis_md
    assert "| UTOOL | 19 | 10 | over by 9" in analysis_md and "| F |" not in analysis_md


@pytest.mark.parametrize("level", [READY, WORKABLE, NOT_READY, EMPTY])
def test_every_level_has_a_headline_for_the_window(level):
    sample = {READY: _decide(100.0, todo=0), WORKABLE: _decide(90.0, blocking=1), NOT_READY: _decide(10.0),
              EMPTY: _decide(0.0, programs=0, todo=0)}[level]  # fmt: skip
    assert sample.level == level and sample.headline.endswith(".") and len(sample.headline) < 110
