# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""The path to a workable verdict (analysis.workable_path): which blocking causes to solve, how many instructions to
convert besides, what --karel would give; the rule itself unchanged."""

from test_analysis import _with_programs

from crossarm.convert import ConversionConfig, build_report
from crossarm.convert.analysis import (
    MAX_BLOCKING,
    MIN_CONVERTED,
    NOT_READY,
    READY,
    WORKABLE,
    figures_verdict,
    path_to_workable,
    workable_path,
)
from crossarm.convert.blockers import Blocker
from crossarm.convert.coverage import Coverage, Share
from crossarm.convert.html_report import build_html_report
from crossarm.convert.translate import ConversionResult, Note, VerdictFigures

# Blocking causes and their TODO, most first
FIVE = ((Blocker.RUNTIME_FRAME, 21), (Blocker.RUNTIME_POSITION, 12), (Blocker.INTERRUPT, 7),
        (Blocker.MOTION, 3), (Blocker.CALIBRATION, 3))  # fmt: skip
PLANNED = ((Blocker.MISSING, 40),)


def _figures(converted: int, blocking=(), total: int = 1000, planned=PLANNED) -> VerdictFigures:
    causes = tuple(sorted((*blocking, *planned), key=lambda kv: (-kv[1], kv[0])))
    return VerdictFigures(12, converted, total, sum(k for _, k in causes), causes, ())


def test_the_rule_is_unchanged():
    assert (MIN_CONVERTED, MAX_BLOCKING) == (85.0, 3)


def test_no_path_when_workable_or_ready():
    for blocking in ((), FIVE[:2], FIVE[:3]):  # 0, 2, 3 blocking causes
        path = workable_path(_figures(900, blocking))
        assert path.level == WORKABLE and not path.needed and path.text() == ""
        assert path.to_solve == () and path.instructions == 0
        assert path.data()["blocking_causes"] == dict(blocking) and path.data()["causes_to_workable"] == {}
    ready = workable_path(VerdictFigures(3, 50, 50, 0, (), ()))
    assert ready.level == READY and not ready.needed


def test_five_blocking_causes_two_to_solve_the_fewest_todo_first():
    path = workable_path(_figures(900, FIVE))
    assert path.level == NOT_READY and path.needed
    assert path.blocking == tuple(sorted(FIVE, key=lambda kv: (-kv[1], kv[0])))  # most first, ties by name
    # 5 - 3 = 2 to solve: those with the fewest TODO (3 each), then by family, then by name
    assert {c for c, _ in path.to_solve} == {Blocker.MOTION, Blocker.CALIBRATION}
    assert path.instructions == 0
    text = path.text()
    assert text.startswith("Path to workable: solve 2 of the 5 blocking causes (3 are allowed), the fewest TODO first:")
    assert f"{path.to_solve[0][0]}: 3 TODO; {path.to_solve[1][0]}: 3 TODO." in text
    assert "convert" not in text
    assert path.data() == {"blocking_causes": dict(FIVE), "causes_to_workable": dict(path.to_solve),
                           "instructions_to_workable": 0, "verdict_with_karel": None}  # fmt: skip


def test_one_cause_to_solve():
    path = workable_path(_figures(900, FIVE[:4]))
    assert path.to_solve == ((Blocker.MOTION, 3),)
    assert "solve 1 of the 4 blocking causes (3 are allowed), the one with the fewest TODO:" in path.text()


def test_the_share_converted_below_the_threshold_blocks_too():
    path = workable_path(_figures(800, FIVE[:2], total=1000))  # 80 %, 2 blocking causes
    assert path.level == NOT_READY and path.to_solve == ()
    assert path.instructions == 50  # 850 of 1000
    assert path.text() == "Path to workable: convert 50 more of the 1,000 RAPID instructions (85 % at least)."
    both = workable_path(_figures(800, FIVE, total=1000))
    assert both.instructions == 50 and len(both.to_solve) == 2
    assert "Then convert 50 more of the 1,000 RAPID instructions (85 % at least; solving these causes" in both.text()
    # rounded as the share shown is: 85 % of 7 instructions is 5.95, so 6
    assert workable_path(_figures(5, total=7)).instructions == 1
    assert workable_path(_figures(6, total=7)).level == WORKABLE


def test_what_karel_would_give_when_it_changes_the_verdict():
    without = _figures(830, FIVE[:4])  # 83 %, 4 blocking causes: not ready
    with_karel = _figures(872, (FIVE[0], FIVE[1]))  # 87.2 %, 2: workable
    path = workable_path(without, with_karel)
    assert path.karel is not None and path.karel.level == WORKABLE
    assert path.text().endswith("With --karel and the KAREL option R632, the conversion is workable (87.2 %"
                                " converted, 2 blocking causes).")  # fmt: skip
    assert path.data()["verdict_with_karel"] == WORKABLE
    # the same verdict with --karel: nothing said
    same = workable_path(without, _figures(845, FIVE[:4]))
    assert same.karel is None and "--karel" not in same.text()


def test_figures_add_up_as_tasks_do():
    a = VerdictFigures(2, 80, 100, 5, ((Blocker.INTERRUPT, 3), (Blocker.MISSING, 2)), ())
    b = VerdictFigures(3, 90, 100, 4, ((Blocker.MISSING, 4),), ("UTOOL",))
    both = a + b
    assert (both.programs, both.converted, both.total, both.todo) == (5, 170, 200, 9)
    assert both.causes == ((Blocker.MISSING, 6), (Blocker.INTERRUPT, 3)) and both.over == ("UTOOL",)
    assert both.percent == 85.0 and figures_verdict(both).level == WORKABLE


def _not_ready() -> ConversionResult:
    result = ConversionResult()
    result.coverage = Coverage((Share("Motion", 100, 70),))
    result.notes = [Note("MAIN", 10 + i, "TODO", f"cause {cause}", cause)
                    for i, (cause, count) in enumerate(FIVE) for _ in range(count)]  # fmt: skip
    return _with_programs(result)


def test_the_path_is_said_at_the_top_of_the_analysis():
    result = _not_ready()
    path = path_to_workable(result)
    assert path.needed and path.instructions == 15
    text = build_report(result, ConversionConfig(), ["cell.mod"])
    analysis_md = text.split("## Analysis")[1].split("### What to do first")[0]
    lines = analysis_md.strip().splitlines()
    assert lines[0].startswith("- **Not ready") and lines[1] == f"- **{path.text()}**"
    page = build_html_report(result, ConversionConfig(), ["cell.mod"], title="t")
    found = page.split('<p class="path">', 1)[1].split("</p>", 1)[0]
    assert found.startswith("Path to workable: solve 2 of the 5 blocking causes")
    assert found.count('<a href="#todo&amp;cause=') == 2  # each cause to solve leads to its TODO


def test_no_path_in_a_workable_report():
    result = ConversionResult()
    result.coverage = Coverage((Share("Motion", 100, 90),))
    result.notes = [Note("MAIN", 10, "TODO", "x", Blocker.INTERRUPT), Note("MAIN", 11, "TODO", "y", Blocker.MISSING)]
    result = _with_programs(result)
    assert path_to_workable(result).level == WORKABLE and not path_to_workable(result).needed
    assert "Path to workable" not in build_report(result, ConversionConfig(), ["cell.mod"])
    assert '<p class="path">' not in build_html_report(result, ConversionConfig(), ["cell.mod"], title="t")
