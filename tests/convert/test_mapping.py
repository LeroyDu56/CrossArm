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


def test_a_mapping_that_exceeds_the_controller_is_still_reported(tmp_path):
    """Pinning numbers by hand is exactly when someone goes past the limit."""
    path = tmp_path / "map.json"
    path.write_text('{"_note": "hand written", "utools": {"tGrip": 30}}', encoding="utf-8")
    cfg = ConversionConfig.from_mapping_file(path, timestamp=datetime(2026, 1, 1))
    source = f"MODULE M\n{DATA}\nPROC main()\n{BODY}\nENDPROC\nENDMODULE\n"
    result = convert([parse_module(source)], cfg, routines=["main"], sources={"M": source})
    utool = next(c for c in result.capacity if c.resource == "UTOOL")
    assert utool.over == ("tGrip",)


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
