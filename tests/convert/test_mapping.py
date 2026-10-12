# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""The generated mapping file, and the round trip that makes it worth generating.

Writing a mapping by hand means transcribing every signal, frame and register the
programs use. Every conversion therefore writes the numbering it just used, so the
integrator edits that instead.
"""

import json
from datetime import datetime

from helpers import parse_module
from test_translate import HOME, TOOL, WOBJ, run

from crossarm.convert import ConversionConfig, build_mapping, convert


def config(**kwargs) -> ConversionConfig:
    return ConversionConfig(timestamp=datetime(2026, 1, 1), **kwargs)


BODY = "MoveL pHome,v500,fine,tGrip\\WObj:=wFix;\nSet doGrip;\nWaitDI diReady,1;\nnCount:=nCount+1;"
DATA = HOME + TOOL + WOBJ + "VAR num nCount:=0;"


def mapping_of(result, cfg=None) -> dict:
    return json.loads(build_mapping(result, cfg or config()))


def test_every_allocated_number_is_in_the_mapping():
    data = mapping_of(run(BODY, DATA))
    assert data["registers"] == {"nCount": 1}
    assert data["digital_outputs"] == {"doGrip": 1}
    assert data["digital_inputs"] == {"diReady": 1}
    # Only what the programs actually reference: tool0 and wobj0 are never used here.
    assert data["utools"] == {"tGrip": 1}
    assert data["uframes"] == {"wFix": 1}


def test_names_keep_their_rapid_spelling():
    """Matching is case-insensitive, but the file is read by a human."""
    data = mapping_of(run("Set doGripperClose;"))
    assert list(data["digital_outputs"]) == ["doGripperClose"]


def test_empty_tables_are_left_out_but_limits_are_always_there():
    data = mapping_of(run("Stop;"))
    assert "registers" not in data and "flags" not in data
    assert data["limits"]["UTOOL"] == 10


def test_the_file_explains_itself():
    data = mapping_of(run(BODY, DATA))
    assert "--map" in data["_README"]


def test_the_tool_pin_is_offered_when_the_programs_use_a_tool():
    """Which way round the tool sits is the integrator's choice: the file shows it where it is edited."""
    data = mapping_of(run(BODY, DATA))
    assert data["tool_pin"] == "-x" and "ISO 9409-1" in data["_tool_pin"]
    assert "tool_pin" not in mapping_of(run("Stop;"))
    assert mapping_of(run(BODY, DATA), config(tool_pin="+x"))["tool_pin"] == "+x"


def test_generated_mapping_is_accepted_as_is(tmp_path):
    """The file a conversion writes must be readable by the next conversion."""
    path = tmp_path / "crossarm_mapping.json"
    path.write_text(build_mapping(run(BODY, DATA), config()), encoding="utf-8")
    cfg = ConversionConfig.from_mapping_file(path, timestamp=datetime(2026, 1, 1))
    assert cfg.digital_outputs["DOGRIP"] == 1
    assert cfg.utools["TGRIP"] == 1
    assert cfg.limits["UTOOL"] == 10


def test_editing_the_mapping_changes_the_numbers(tmp_path):
    """The whole point: convert, edit, convert again and get the cell's own numbers."""
    path = tmp_path / "crossarm_mapping.json"
    data = mapping_of(run(BODY, DATA))
    data["digital_outputs"]["doGrip"] = 7
    data["utools"]["tGrip"] = 4
    data["registers"]["nCount"] = 55
    path.write_text(json.dumps(data), encoding="utf-8")

    cfg = ConversionConfig.from_mapping_file(path, timestamp=datetime(2026, 1, 1))
    source = f"MODULE M\n{DATA}\nPROC main()\n{BODY}\nENDPROC\nENDMODULE\n"
    result = convert([parse_module(source)], cfg, routines=["main"], sources={"M": source})
    text = "\n".join(line.text for line in result.programs[0].program.lines if hasattr(line, "text"))
    assert "DO[7]=ON" in text
    assert "UTOOL_NUM=4" in text
    assert "R[55:nCount]=R[55:nCount]+1" in text
    # A second pass over the edited file must be stable, not renumber again.
    assert mapping_of(result, cfg)["digital_outputs"] == {"doGrip": 7}


def test_a_number_pinned_past_the_controller_is_a_bank(tmp_path):
    """A frame number past the limit is what a mapping file says for a frame kept in a register bank:
    loaded into the reserved number, as the conversion that wrote it did. Past the limit with no number
    left to load it into, it stays reported."""
    path = tmp_path / "map.json"
    path.write_text('{"_note": "hand written", "utools": {"tGrip": 30}}', encoding="utf-8")
    cfg = ConversionConfig.from_mapping_file(path, timestamp=datetime(2026, 1, 1))
    source = f"MODULE M\n{DATA}\nPROC main()\n{BODY}\nENDPROC\nENDMODULE\n"
    result = convert([parse_module(source)], cfg, routines=["main"], sources={"M": source})
    text = "\n".join(line.text for line in result.programs[0].program.lines if hasattr(line, "text"))
    assert "UTOOL[10]=PR[" in text and "UTOOL_NUM=10" in text and "UTOOL_NUM=30" not in text
    assert next(c for c in result.capacity if c.resource == "UTOOL").over == ()

    tools = {f"t{i}": i for i in range(1, 11)} | {"tGrip": 30}  # every number the controller holds taken
    path.write_text(json.dumps({"utools": tools}), encoding="utf-8")
    cfg = ConversionConfig.from_mapping_file(path, timestamp=datetime(2026, 1, 1))
    result = convert([parse_module(source)], cfg, routines=["main"], sources={"M": source})
    assert next(c for c in result.capacity if c.resource == "UTOOL").over == ("tGrip",)


def test_analog_scales_are_written_for_the_user_to_fill_in(tmp_path):
    """A SetAO needs the FANUC module's counts per RAPID unit: null until the user says, then converted."""
    body, data = "SetAO aoFlow,4.5;\nClkReset ckCycle;", "VAR clock ckCycle;"
    written = mapping_of(run(body, data))
    assert written["analog_outputs"] == {"aoFlow": 1} and written["analog_scales"] == {"aoFlow": None}
    assert written["timers"] == {"ckCycle": 1}
    path = tmp_path / "map.json"
    path.write_text(json.dumps(written), encoding="utf-8")
    assert ConversionConfig.from_mapping_file(path).analog_scales == {}  # null: still not known
    written["analog_scales"]["aoFlow"] = 409.5
    written["timers"]["ckCycle"] = 4
    path.write_text(json.dumps(written), encoding="utf-8")
    cfg = ConversionConfig.from_mapping_file(path, timestamp=datetime(2026, 1, 1))
    result = run(body, data, config=cfg)
    assert [line.text for line in result.programs[0].program.lines[1:]] == ["AO[1]=1843", "TIMER[4]=RESET"]
    assert mapping_of(result, cfg)["analog_scales"] == {"aoFlow": 409.5}


def test_each_routine_s_counter_is_kept_apart_in_the_mapping_file(tmp_path):
    """Two routines counting with i: two registers, MAIN.i and other.i, each pinned when given back."""
    from crossarm.convert.translate import NumberTable

    table = NumberTable({"MAIN.I": 7, "OTHER.I": 3}, 1)
    assert (table.number("i", key="MAIN.i"), table.number("i", key="other.i")) == (7, 3)


def test_a_1_2_mapping_naming_a_counter_by_its_rapid_name_still_pins_it():
    from crossarm.convert.translate import NumberTable

    table = NumberTable({"I": 7}, 1)
    assert table.number("i", key="MAIN.i") == 7  # the first register of that name
    assert table.number("i", key="other.i") == 1  # 7 is taken: another one
    assert table.number("i") == 2  # data named i: never the counter's register a second time



HIDDEN = "VAR bool bArmed:=FALSE;\nVAR num nCount:=0;"
HIDING = """PROC main()
  VAR bool bArmed:=TRUE;
  VAR num nCount:=3;
  IF diX=1 bArmed:=FALSE;
  nCount:=nCount+1;
  Side;
  IF bArmed Set doA;
  IF nCount>2 Set doB;
ENDPROC
PROC Side()
  bArmed:=TRUE;
  nCount:=nCount+5;
ENDPROC"""


def convert_hiding(cfg: ConversionConfig):
    source = f"MODULE M\n{HIDDEN}\n{HIDING}\nENDMODULE\n"
    return convert([parse_module(source)], cfg, routines=["main", "Side"], sources={"M": source})


def lines_of(result) -> dict[str, list[str]]:
    return {info.program.name: [getattr(x, "text", "") for x in info.program.lines[1:]] for info in result.programs}


def test_a_routine_s_data_hiding_module_data_has_a_register_and_a_flag_of_its_own(tmp_path):
    """Up to 1.10, main's bArmed / nCount shared the module's F[] / R[]: Side changed what main tested."""
    result = convert_hiding(config())
    lines = lines_of(result)
    assert lines["MAIN"][:2] == ["F[1]=(ON)", "R[1:nCount]=3"]
    assert lines["SIDE"] == ["F[2]=(ON)", "R[2:nCount]=R[2:nCount]+5"]
    assert "IF (F[1]=ON) THEN" in lines["MAIN"] and "IF (R[1:nCount]>2) THEN" in lines["MAIN"]
    written = mapping_of(result)
    assert written["flags"] == {"main.bArmed": 1, "bArmed": 2}
    assert written["registers"] == {"main.nCount": 1, "nCount": 2}
    # Given back, the same numbers; a mapping written before naming them all bArmed / nCount pins the module data.
    path = tmp_path / "map.json"
    path.write_text(json.dumps(written), encoding="utf-8")
    assert lines_of(convert_hiding(ConversionConfig.from_mapping_file(path, timestamp=datetime(2026, 1, 1)))) == lines
    path.write_text(json.dumps({"flags": {"bArmed": 5}, "registers": {"nCount": 7}}), encoding="utf-8")
    lines = lines_of(convert_hiding(ConversionConfig.from_mapping_file(path, timestamp=datetime(2026, 1, 1))))
    assert lines["SIDE"] == ["F[5]=(ON)", "R[7:nCount]=R[7:nCount]+5"]
    assert lines["MAIN"][:2] == ["F[1]=(ON)", "R[1:nCount]=3"]


def test_data_of_the_same_name_in_a_routine_and_one_it_calls_are_kept_apart():
    """main's n survives the call to Side, which counts with its own n; Other never runs inside main: shared."""
    source = """MODULE M
PROC main()
  VAR num n:=5;
  VAR bool b:=TRUE;
  Side;
  IF n>2 AND b Set doA;
ENDPROC
PROC Side()
  VAR num n:=0;
  VAR bool b:=FALSE;
  n:=n+1;
ENDPROC
PROC Other()
  VAR num n:=1;
ENDPROC
ENDMODULE
"""
    result = convert([parse_module(source)], config(), routines=["main", "Side", "Other"], sources={"M": source})
    lines = lines_of(result)
    assert lines["MAIN"][:2] == ["R[1:n]=5", "F[1]=(ON)"] and "IF (R[1:n]>2 AND F[1]=ON) THEN" in lines["MAIN"]
    assert lines["SIDE"] == ["R[2:n]=0", "F[2]=(OFF)", "R[2:n]=R[2:n]+1"]
    assert lines["OTHER"] == ["R[3:n]=1"]
    assert mapping_of(result)["registers"] == {"main.n": 1, "Side.n": 2, "n": 3}

# -- the names of the programs -------------------------------------------------------------------

TEXTS = "VAR string sState:=\"\";"
PROCS = "PROC pick()\nsState:=\"PICK\";\nENDPROC"


def convert_on(robot: set[str], cfg: ConversionConfig):
    """main calling pick, both loading a text, converted for a robot that already has the programs `robot`."""
    from crossarm.convert.translate import ControllerScope

    source = f"MODULE M\n{TEXTS}\nPROC main()\nsState:=\"IDLE\";\npick;\nENDPROC\n{PROCS}\nENDMODULE\n"
    return convert([parse_module(source)], cfg, routines=["main", "pick"], sources={"M": source},
                   shared=ControllerScope.from_config(cfg, robot))  # fmt: skip


def names(result) -> list[str]:
    return [info.program.name for info in result.programs]


def test_the_mapping_file_gives_the_name_of_each_program_written():
    data = mapping_of(convert_on(set(), config()))
    assert data["programs"] == {"main": "MAIN", "pick": "PICK", "CROSSARM.TEXT": "CA_TEXT"}
    assert "CROSSARM.TEXT" in data["_programs"]


def test_given_back_the_mapping_file_keeps_the_names_with_or_without_those_programs_on_the_robot(tmp_path):
    """A second conversion would rename CA_TEXT and PICK, programs of the robot by then: the programs already
    loaded call the names the first one gave. Given back its mapping file, it gives the same names, twice."""
    first = convert_on(set(), config())
    assert names(first) == ["MAIN", "PICK", "CA_TEXT"]
    alone = convert_on({"CA_TEXT", "PICK"}, config())  # without the mapping file: renamed, said so
    assert names(alone) == ["MAIN", "PICK_2", "CA_TEXT_2"]
    path = tmp_path / "map.json"
    path.write_text(build_mapping(first, config()), encoding="utf-8")
    for robot in (set(), {"CA_TEXT", "PICK"}, set(), {"CA_TEXT", "PICK"}):
        cfg = ConversionConfig.from_mapping_file(path, timestamp=datetime(2026, 1, 1))
        result = convert_on(robot, cfg)
        assert names(result) == names(first)
        assert "CALL CA_TEXT(1,'IDLE',0)" in [getattr(line, "text", "") for line in result.programs[0].program.lines]
        assert build_mapping(result, cfg) == build_mapping(first, config())
        taken = [n.message for n in result.notes if n.category == "pinned number already used on the controller"]
        assert len(taken) == len(robot)  # each said: replaced on loading, intended if the first conversion loaded it
        assert all("an earlier conversion" in message for message in taken)


def test_a_name_the_mapping_file_gives_is_kept_for_its_program(tmp_path):
    path = tmp_path / "map.json"
    path.write_text(json.dumps({"programs": {"pick": "MAIN", "CROSSARM.TEXT": "TXT"}}), encoding="utf-8")
    result = convert_on(set(), ConversionConfig.from_mapping_file(path, timestamp=datetime(2026, 1, 1)))
    # MAIN is pick's: main, converted first, takes another name rather than MAIN
    assert names(result) == ["MAIN_2", "MAIN", "TXT"]
    assert "CALL TXT(1,'IDLE',0)" in [getattr(line, "text", "") for line in result.programs[0].program.lines]


def test_two_programs_given_one_name_take_a_suffix_for_the_second(tmp_path):
    path = tmp_path / "map.json"
    path.write_text(json.dumps({"programs": {"main": "SAME", "pick": "SAME"}}), encoding="utf-8")
    result = convert_on(set(), ConversionConfig.from_mapping_file(path, timestamp=datetime(2026, 1, 1)))
    assert names(result)[:2] == ["SAME", "SAME_2"]
    assert any("the mapping file gives it SAME" in n.message for n in result.notes)


def test_a_program_name_the_controller_cannot_hold_is_refused(tmp_path):
    import pytest

    path = tmp_path / "map.json"
    for bad in ("1PICK", "PICK-UP", 3, "P" * 40):
        path.write_text(json.dumps({"programs": {"pick": bad}}), encoding="utf-8")
        with pytest.raises(ValueError, match="programs.pick"):
            ConversionConfig.from_mapping_file(path)
