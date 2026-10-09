# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""The analysis's actions can be acted on: each says the TODO it concerns, exactly, and leads to them; who acts;
cosmetic or needed for production; the outlook of what is left; the sentence under the share converted by area;
an external_routines example to paste; and, over the controller's capacity, the numbers to change."""

import json
import re
from datetime import datetime

import pytest
from test_analysis import _result, _with_programs
from test_html_report import CELL, _convert, _review_rows

from crossarm.convert import ConversionConfig, build_report, convert, triage
from crossarm.convert.analysis import Action, priority_actions
from crossarm.convert.blockers import Blocker
from crossarm.convert.coverage import Coverage, Share
from crossarm.convert.external import Candidate
from crossarm.convert.html_report import build_html_report
from crossarm.convert.mapping import build_mapping
from crossarm.convert.source_map import parse_todo_href, todo_href
from crossarm.convert.translate import Allocation, Capacity, ConversionResult, Note
from crossarm.rapid import parse_text

STAMP = datetime(2026, 1, 1)


# ---------------------------------------------------------------------------
# The classes, in one place
# ---------------------------------------------------------------------------


def _blockers() -> list[str]:
    return [value for name, value in vars(Blocker).items() if name.isupper() and isinstance(value, str)]


def test_every_cause_has_a_family_and_a_sentence_for_it():
    for cause in _blockers():
        assert triage.family(cause) in triage.FAMILY_WORDS
        assert triage.family(cause) != triage.OTHER or cause == Blocker.OTHER, cause
    assert triage.family(Blocker.SIGNAL) == triage.IO and triage.family(Blocker.MESSAGE_CUT) == triage.HMI
    assert triage.family(Blocker.CALIBRATION) == triage.CALIBRATION and triage.family(Blocker.VALUE) == triage.DATA
    assert triage.family(Blocker.rapid("ERROR_HANDLER")) == triage.ERRORS
    assert triage.family(Blocker.rapid("GOTO")) == triage.FLOW and triage.family("unheard of") == triage.OTHER


def test_cosmetic_is_only_what_the_operator_reads():
    assert triage.COSMETIC_CAUSES == {Blocker.MESSAGE_VALUE, Blocker.MESSAGE_CUT}
    assert triage.impact([Blocker.MESSAGE_VALUE, Blocker.MESSAGE_CUT]) == triage.COSMETIC
    assert triage.impact([Blocker.MESSAGE_VALUE, Blocker.SIGNAL]) == triage.PRODUCTION
    assert triage.impact([]) == triage.PRODUCTION


def test_the_outlook_never_promises_a_version_or_a_date():
    assert not triage.NO_TP_CAUSES & triage.LATER_CAUSES
    assert Blocker.NO_TP_EQUIVALENT in triage.NO_TP_CAUSES and Blocker.VALUE in triage.LATER_CAUSES
    assert not triage.COSMETIC_CAUSES & (triage.NO_TP_CAUSES | triage.LATER_CAUSES)
    for text in (triage.LATER, triage.LATER_TITLE, triage.NO_TP_TITLE):
        assert not re.search(r"\d", text) and "will" not in text
    no_tp, later = triage.outlook([(Blocker.NO_TP_EQUIVALENT, 5), (Blocker.VALUE, 3), (Blocker.SIGNAL, 2)])
    assert no_tp == [(Blocker.NO_TP_EQUIVALENT, 5)] and later == [(Blocker.VALUE, 3)]  # a known fix: in neither


@pytest.mark.parametrize(("motion", "causes", "sentence"), [
    ((100, 100), [], "Motion fully converted; nothing left TODO."),
    ((100, 97), [(Blocker.SAVED_FRAME, 6), (Blocker.RUNTIME_FRAME, 2), (Blocker.VALUE, 2)],
     "Motion mostly converted (97 %); most of what is left is tool and frame set-up (8 of 10 TODO)."),
    ((100, 85), [(Blocker.SIGNAL, 4)], ("Motion largely converted (85 %); all of what is left is I/O signals and"
                                        " waits (4 TODO).")),
    ((100, 20), [(Blocker.SIGNAL, 4), (Blocker.VALUE, 4), (Blocker.CONDITION, 2)],
     ("Motion only partly converted (20 %); what is left is mostly I/O signals and waits and data known only at"
      " run time (8 of 10 TODO).")),  # a tie: by name
    ((100, 99), [(Blocker.SIGNAL, 3), (Blocker.VALUE, 2), (Blocker.CONDITION, 2), (Blocker.MESSAGE_CUT, 2),
                 (Blocker.MISSING, 2)],
     ("Motion mostly converted (99 %); what is left is spread over 5 families, I/O signals and waits first"
      " (3 of 11 TODO).")),
    (None, [(Blocker.MISSING, 3)], "All of what is left is system routines and functions (3 TODO)."),
    (None, [(Blocker.MISSING, 1), (Blocker.MESSAGE_VALUE, 1)],  # half is not most
     "What is left is operator messages and system routines and functions (2 TODO)."),
    (None, [(Blocker.MISSING, 2), (Blocker.MESSAGE_VALUE, 1), (Blocker.SIGNAL, 1)],
     "What is left is mostly system routines and functions and I/O signals and waits (3 of 4 TODO)."),
    (None, [], ""),
])  # fmt: skip
def test_the_sentence_under_the_areas_says_only_what_the_figures_say(motion, causes, sentence):
    shares = (Share("Motion", *motion),) if motion else (Share("Data", 10, 5),)
    assert triage.business_sentence(Coverage(shares), causes) == sentence


# ---------------------------------------------------------------------------
# The actions
# ---------------------------------------------------------------------------


def test_each_action_counts_its_todo_exactly_and_says_who_acts():
    result = _result()
    result.notes.append(Note("MAIN", 90, "TODO", "TPWrite showing a value", Blocker.MESSAGE_VALUE))
    actions = priority_actions(result)
    todo = [note for note in result.notes if note.kind == "TODO"]
    for action in actions:
        assert action.who and set(action.who) <= set(triage.WHO), action.title
        if action.causes:
            assert action.todo == sum(1 for note in todo if note.category in action.causes), action.title
            assert set(action.programs) == {n.program for n in todo if n.category in action.causes}
    missing = next(a for a in actions if a.causes == (Blocker.MISSING,))
    assert missing.todo == 7 and missing.who == (triage.BACKUP, triage.INTEGRATOR)
    assert missing.meta == "7 TODO concerned · who acts: ABB backup (add a module) · FANUC integrator"
    measured = next(a for a in actions if a.title.startswith("Decide how the FANUC cell"))
    assert measured.programs == ("CALIB", "CHECK") and measured.todo == 2
    others = next(a for a in actions if a.title.startswith("Finish the other"))
    assert triage.LATER in others.who and others.impact == triage.PRODUCTION  # a condition not convertible
    cosmetic = next(a for a in actions if a.impact == triage.COSMETIC)
    assert cosmetic.todo == 1 and "cosmetic" in cosmetic.meta and "operator message" in cosmetic.title
    karel = Action("t", "d", "#ck-karel", "l", who=(triage.INTEGRATOR, triage.OPTION), option="R632")
    assert karel.who_text == "FANUC integrator · robot option R632"


def test_the_page_leads_each_action_to_exactly_its_todo():
    result = _convert(CELL)
    page = build_html_report(result, ConversionConfig(), ["cell.mod"], title="t")
    rows = _review_rows(page)
    links = re.findall(r'<a class="n" href="([^"]+)">([\d,]+) TODO concerned →</a>', page)
    assert links
    for href, count in links:
        filters = parse_todo_href(href.replace("&amp;", "&"))
        causes, programs = filters["cause"].split("|"), [p for p in filters.get("prog", "").split("|") if p]
        shown = [r for r in rows if r["k"] == "TODO" and r["c"] in causes and (not programs or r["p"] in programs)]
        assert len(shown) == int(count.replace(",", "")), href
    assert "Who acts: FANUC integrator" in page
    # The counts are said as what they are, everywhere: TODO, then warnings.
    todo, warnings = result.todo_count, sum(1 for n in result.notes if n.kind == "WARNING")
    assert f"Items to review ({todo} TODO + {warnings} warning" in page
    assert "' TODO + ' + TOTAL.warn" in page


def test_a_link_filters_on_several_causes_and_programs():
    href = todo_href(cause=("a b", "c"), prog=["P1", "P2"])
    assert href == "#todo&cause=a%20b%7Cc&prog=P1%7CP2"
    assert parse_todo_href(href) == {"cause": "a b|c", "prog": "P1|P2"}
    assert todo_href(cause="x") == "#todo&cause=x"


# ---------------------------------------------------------------------------
# external_routines: an example to paste
# ---------------------------------------------------------------------------


def test_the_external_routines_example_names_a_program_for_the_first_three_candidates():
    result = _with_programs(_result())
    taken = result.programs[0].program.name
    result.provided_candidates = [Candidate(taken, "not in the backup", ("num",)),
                                  Candidate("log-file", "uses files", (), "num"),
                                  Candidate("9lives", "not in the backup"), Candidate("Fourth", "x")]  # fmt: skip
    snippet, count = triage.external_example(result)
    entries = json.loads("{" + snippet + "}")
    assert count == 4 and list(entries) == [taken, "log-file", "9lives"]
    assert entries[taken] == {"program": f"{taken}_2", "arguments": ["num"]}  # not a program written here
    assert entries["log-file"] == {"program": "LOG_FILE", "arguments": [], "returns": "num"}
    assert entries["9lives"]["program"] == "P9LIVES" and all(e["program"] for e in entries.values())
    short = ConversionConfig(program_name_max_length=8)
    assert json.loads("{" + triage.external_example(result, short)[0] + "}")["log-file"]["program"] == "LOG_FILE"
    page = build_html_report(result, ConversionConfig(), ["cell.mod"], title="t")
    assert '<button type="button" class="copy">Copy</button>' in page and "navigator.clipboard" in page
    assert "Selected: press Ctrl+C to copy." in page  # without the clipboard: the text selected
    assert f"&quot;{taken}&quot;: {{&quot;program&quot;: &quot;{taken}_2&quot;" in page
    text = build_report(result, ConversionConfig(), ["cell.mod"])
    assert "   ```json" in text and f'   "{taken}": {{"program": "{taken}_2"' in text
    assert triage.external_example(ConversionResult()) == ("", 0)


# ---------------------------------------------------------------------------
# Over the controller's capacity: the numbers to change
# ---------------------------------------------------------------------------


def _tools(count: int) -> str:
    lines = ["MODULE KB"]
    lines += [f"PERS tooldata tB{i}:=[TRUE,[[0,0,{100 + i}],[1,0,0,0]],[1,[0,0,1],[1,0,0,0],0,0,0]];"
              for i in range(1, count + 1)]  # fmt: skip
    lines += ["CONST robtarget p:=[[500,0,500],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];", "PROC main()"]
    lines += [f"  MoveL p,v100,fine,tB{i};" for i in range(1, count + 1)]
    return "\n".join([*lines, "ENDPROC", "ENDMODULE", ""])


def _run(text: str, config: ConversionConfig) -> ConversionResult:
    parsed = parse_text(text, path="kb.mod")
    return convert([parsed.module], config, sources={"KB": text})


def test_more_tools_than_the_controller_holds_get_a_renumbering_that_holds(tmp_path):
    text, used = _tools(12), {n: ("ROBOTPRG",) for n in range(1, 101)}  # every position register used on the robot
    over = _run(text, ConversionConfig(timestamp=STAMP, reserved={"PR": dict(used)}))
    capacity = next(c for c in over.capacity if c.resource == "UTOOL")
    assert capacity.over == ("tB11", "tB12")
    free, raise_limit = triage.renumbering(over, ConversionConfig(timestamp=STAMP, reserved={"PR": dict(used)}))
    assert "Free 4 position registers on the robot (PR[100], PR[99], PR[98], PR[97], used by `ROBOTPRG`" in free.text
    assert free.edit == {} and raise_limit.edit == {"limits": {"UTOOL": 12}}
    # Freeing them: the frames past the limit go to the banks (1.8), and the mapping given back keeps them there.
    left = {n: p for n, p in used.items() if n < 97}
    banked = _run(text, ConversionConfig(timestamp=STAMP, reserved={"PR": left}))
    assert all(c.fits for c in banked.capacity)
    assert sorted(f.bank for f in banked.utools if f.bank is not None) == [97, 98, 99]
    mapping = build_mapping(banked, ConversionConfig(timestamp=STAMP, reserved={"PR": left}))
    (tmp_path / "m.json").write_text(mapping, encoding="utf-8")
    again = ConversionConfig.from_mapping_file(tmp_path / "m.json", timestamp=STAMP)
    again.reserved = {"PR": left}
    assert build_mapping(_run(text, again), again) == mapping
    # Raising the limit: every tool selected directly.
    raised = ConversionConfig(timestamp=STAMP, reserved={"PR": dict(used)})
    raised.limits["UTOOL"] = raise_limit.edit["limits"]["UTOOL"]
    assert all(c.fits for c in _run(text, raised).capacity)
    # Within the controller's capacity once banked: nothing to propose.
    assert triage.renumbering(_run(text, ConversionConfig(timestamp=STAMP)), ConversionConfig()) == []


def test_names_past_the_limit_go_to_the_numbers_free_under_it():
    result = ConversionResult()
    result.registers = [Allocation(1, "nA", True), Allocation(5, "nB", True), Allocation(6, "nC", False),
                        Allocation(7, "nD", False, key="Main.i")]  # fmt: skip
    result.capacity = [Capacity("R", 4, 7, 5, over=("nC", "nD"))]
    config = ConversionConfig(reserved={"R": {2: ("ROBOTPRG",)}})
    (proposal,) = triage.renumbering(result, config)
    assert proposal.edit == {"registers": {"nC": 3, "Main.i": 4}}  # R[2] is taken on the robot
    assert "pin them in `registers`" in proposal.text
    result.capacity = [Capacity("R", 6, 7, 5, over=("nC", "nD"))]
    result.registers += [Allocation(3, "nE", True), Allocation(4, "nF", True)]
    (full,) = triage.renumbering(result, config)
    assert full.edit == {"limits": {"R": 7}} and "No R number under the limit of 5 is free" in full.text


def test_the_reports_show_the_renumbering_under_the_capacity():
    used = {n: ("ROBOTPRG",) for n in range(1, 101)}
    config = ConversionConfig(timestamp=STAMP, reserved={"PR": used})
    result = _run(_tools(12), config)
    page = build_html_report(result, config, ["kb.mod"], title="t")
    box = page.split('id="an-capacity"')[1].split("</div></div>")[0]
    assert "Proposed renumbering" in box and '<code class="edit">{&quot;limits&quot;: {&quot;UTOOL&quot;: 12}}</code>' in box
    text = build_report(result, config, ["kb.mod"])
    assert '- UTOOL: Raise the controller\'s number of UTOOL to 12' in text and 'Edit: `{"limits": {"UTOOL": 12}}`' in text
