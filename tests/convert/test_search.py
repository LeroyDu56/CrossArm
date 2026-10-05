# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""SearchL as a skip: the move stops where the input switches, the point found in a position register.

Measured on ROBOGUIDE (search probe, docs/validation.md): `L P[2] ... Skip,LBL[2],PR[k]=LPOS` stops where the
input switches and PR[k] is the TCP there; the input never switching, the robot reaches the point and the
program jumps to LBL[2]. TP's skip condition is a level: a search for a change checks the input first.
"""

from test_translate import HOME, TOOL, WOBJ, run, todos, tp_lines

B = "\\"
DATA = HOME + TOOL + WOBJ + (
    "VAR robtarget pFound;\nVAR num nZ;\n"
    "CONST robtarget pEnd:=[[1100,300,1000],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];\n"
)
START = f"MoveL pHome,v500,fine,tGrip{B}WObj:=wFix;\n"


def search(options: str = f"{B}Stop,", level: str = "", speed: str = "v50", then: str = "") -> list[str]:
    return tp_lines(run(START + f"SearchL {options}diProbe{level},pFound,pEnd,{speed},tGrip{B}WObj:=wFix;\n{then}", DATA))


def warnings(result) -> list[str]:
    return [n.message for n in result.notes if n.kind == "WARNING" and n.category.startswith("search")]


def test_a_search_stopping_on_a_rising_edge_checks_the_input_is_off_then_skips():
    assert search()[3:] == [
        "LBL[1]", "IF (DI[1]=ON),JMP LBL[4]", "SKIP CONDITION DI[1]=ON", "UFRAME_NUM=1", "UTOOL_NUM=1",
        "L P[2] 50mm/sec FINE", "JMP LBL[3]",
        "LBL[4]", "MESSAGE[SearchL l.8: input on]", "PAUSE", "JMP LBL[1]",
        "LBL[2]", "MESSAGE[SearchL l.8: no hit]", "PAUSE", "JMP LBL[1]",
        "LBL[3]"]  # fmt: skip


def test_the_point_found_is_latched_by_the_skip_in_its_position_register():
    result = run(START + f"SearchL {B}PStop,diProbe,pFound,pEnd,v50,tGrip{B}WObj:=wFix;", DATA)
    move = next(line for line in result.programs[0].program.lines if getattr(line, "target", "") == "P[2]")
    assert move.options == "Skip,LBL[2],PR[99]=LPOS"
    assert [a.rapid_name.upper() for a in result.point_registers] == ["PFOUND"]


def test_a_falling_edge_skips_on_off_and_checks_the_input_is_on():
    lines = search(f"{B}SStop,", f"{B}NegFlank")
    assert lines[4:6] == ["IF (DI[1]=OFF),JMP LBL[4]", "SKIP CONDITION DI[1]=OFF"]
    assert "MESSAGE[SearchL l.8: input off]" in lines


def test_a_search_for_a_level_does_not_check_the_input_first():
    """RAPID finds the level at once when the input is at it at the start, as TP's skip condition does."""
    lines = search(f"{B}Stop,", f"{B}LowLevel")
    assert lines[3:5] == ["LBL[1]", "SKIP CONDITION DI[1]=OFF"]
    assert not any(line.startswith("IF ") for line in lines)


def test_a_flying_search_goes_on_to_the_point_once_stopped():
    """\\Sup, or no stop option: RAPID goes on to the point; the FANUC stops at the switch, then moves on."""
    for options in (f"{B}Sup,", ""):
        lines = search(options)
        assert lines[8:11] == ["L P[2] 50mm/sec FINE", "L P[2] 50mm/sec FINE", "JMP LBL[3]"]
    result = run(START + f"SearchL {B}Sup,diProbe,pFound,pEnd,v50,tGrip{B}WObj:=wFix;", DATA)
    assert "does not check for a second switch" in warnings(result)[0]


def test_the_report_says_the_fanuc_comes_back_where_rapid_stays_past_the_switch():
    result = run(START + f"SearchL {B}Stop,diProbe,pFound,pEnd,v50,tGrip{B}WObj:=wFix;", DATA)
    [warning] = warnings(result)
    assert "comes back to it (6.4 mm past at 50 mm/s), RAPID stops past it and stays" in warning
    assert "search by contact, where the tool pushes into the part" in warning
    assert "shows a MESSAGE and pauses; resumed, it searches again" in warning


def test_the_point_found_is_read_as_a_point_known_at_run_time():
    lines = search(then=f"MoveL Offs(pFound,0,0,50),v100,fine,tGrip{B}WObj:=wFix;\nnZ:=pFound.trans.z;")
    assert lines[-6:] == ["PR[98]=PR[99]", "PR[98,3]=PR[98,3]+50", "UFRAME_NUM=1", "UTOOL_NUM=1",
                          "L PR[98] 100mm/sec FINE", "R[1:nZ]=PR[99,3]"]  # fmt: skip


def test_a_search_left_todo_leaves_its_point_unknown():
    result = run(START + f"SearchL diProbe{B}Flanks,pFound,pEnd,v50,tGrip{B}WObj:=wFix;\n"
                 f"MoveL Offs(pFound,0,0,50),v100,fine,tGrip{B}WObj:=wFix;", DATA)  # fmt: skip
    assert todos(result)[0].startswith("SearchL \\Flanks: TP's skip condition waits for one level")
    assert todos(result)[1].startswith("'pFound' is measured on the robot at l.8")


def test_a_search_faster_than_the_skip_records_stays_todo():
    result = run(START + f"SearchL {B}Stop,diProbe,pFound,pEnd,v150,tGrip{B}WObj:=wFix;", DATA)
    assert todos(result)[0].startswith("SearchL at 150 mm/s: the FANUC skip records the position up to 100 mm/s")


def test_a_search_in_a_routine_with_an_error_handler_stays_todo():
    source = START + f"SearchL {B}Stop,diProbe,pFound,pEnd,v50,tGrip{B}WObj:=wFix;\nERROR\nRETRY;"
    result = run(source, DATA)
    assert any(t.startswith("SearchL in a routine with an ERROR handler") for t in todos(result))


def test_a_search_point_that_is_an_array_element_stays_todo():
    data = DATA + "VAR robtarget pHits{2};\n"
    result = run(START + f"SearchL {B}Stop,diProbe,pHits{{1}},pEnd,v50,tGrip{B}WObj:=wFix;", data)
    assert "is kept in a position register when it is a robtarget data of its own" in todos(result)[0]
