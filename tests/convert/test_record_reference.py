# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""A record passed by reference (INOUT, VAR) to a routine that changes its num components: each component is
passed as an argument, copied to a register where the routine starts, and read back after the CALL, as a num
passed by reference is."""

from datetime import datetime

from helpers import parse_module

from crossarm.convert import ConversionConfig, convert

RECORD = "RECORD feedcount\n  num parts;\n  num rate;\n  bool empty;\nENDRECORD\n"


def run(main: str, routine: str, data: str = "PERS feedcount rFeedA:=[0,0,FALSE];"):
    source = f"MODULE M\n{RECORD}{data}\nPROC main()\n{main}\nENDPROC\n{routine}\nENDMODULE\n"
    config = ConversionConfig(timestamp=datetime(2026, 1, 1))
    return convert([parse_module(source)], config, sources={"M": source})


def lines(result, name: str) -> list[str]:
    program = next(p.program for p in result.programs if p.program.name == name)
    return [line.text for line in program.lines[1:]]


def todos(result) -> list[str]:
    return [note.message for note in result.notes if note.kind == "TODO"]


COUNT = "PROC CountFeed(INOUT feedcount f)\n  Incr f.parts;\n  f.rate:=f.parts/2;\nENDPROC"


def test_the_changed_components_come_back():
    result = run("CountFeed rFeedA;\nIF rFeedA.parts>3 Stop;", COUNT)
    assert not todos(result)
    assert lines(result, "COUNTFEED") == ["R[2:f.parts]=AR[1]", "R[4:f.rate]=AR[2]", "R[2:f.parts]=R[2:f.parts]+1",
                                          "R[4:f.rate]=R[2:f.parts]/2"]  # fmt: skip
    assert lines(result, "MAIN")[:3] == ["CALL COUNTFEED(R[1:rFeedA.parts],R[3:rFeedA.rate])",
                                         "R[1:rFeedA.parts]=R[2:f.parts]", "R[3:rFeedA.rate]=R[4:f.rate]"]  # fmt: skip


def test_a_record_passed_by_value_and_changed_is_a_copy_not_read_back():
    result = run("CountFeed rFeedA;", COUNT.replace("INOUT ", ""))
    assert not todos(result)
    assert lines(result, "MAIN") == ["CALL COUNTFEED(0,0)"]  # no program changes rFeedA: its values
    assert lines(result, "COUNTFEED")[0] == "R[1:f.parts]=AR[1]"


def test_what_cannot_come_back_says_why():
    flag = run("CountFeed rFeedA;", "PROC CountFeed(INOUT feedcount f)\n  f.empty:=TRUE;\nENDPROC")
    assert any("bool component f.empty" in t and "only num components" in t for t in todos(flag))
    whole = run("ClearFeed rFeedA;", "PROC ClearFeed(VAR feedcount f)\n  f:=[0,0,FALSE];\nENDPROC")
    assert any("used whole" in t for t in todos(whole))
    element = run("CountFeed rFeeds{2};", COUNT, "PERS feedcount rFeeds{2}:=[[0,0,FALSE],[0,0,FALSE]];")
    assert todos(element)
