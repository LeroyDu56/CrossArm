# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""World zones (WZBoxDef, WZLimSup, WZDOSet...) and the ABB's safety options: TODO saying the zone is set up in DCS,
an item of the commissioning checklist per zone with what the RAPID gives, and an action of the analysis; CrossArm
converts no safety function."""

from pathlib import Path

from test_translate import run, todos

from crossarm import pipeline
from crossarm.convert import ConversionConfig, triage
from crossarm.convert.analysis import priority_actions
from crossarm.convert.blockers import Blocker
from crossarm.convert.checklist import checklist_section
from crossarm.convert.world_zones import safety_options

DATA = """CONST pos posLow:=[400,-300,0];
CONST pos posHigh:=[900,300,800];
CONST robtarget pCentre:=[[1200,0,0],[1,0,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
VAR shapedata shPress;
VAR shapedata shFeeder;
VAR shapedata shAxes;
VAR wzstationary wzPress;
VAR wztemporary wzFeeder;
VAR wzstationary wzAxes;"""
BODY = """WZBoxDef \\Inside,shPress,posLow,posHigh;
WZLimSup \\Stat,wzPress,shPress;
WZCylDef \\Inside,shFeeder,pCentre.trans,250,1000;
WZDOSet \\Temp,wzFeeder \\Inside,shFeeder,doInFeeder,1;
WZDisable wzFeeder;
WZLimJointDef \\Outside,shAxes,[[-170,-60,-70,-180,-120,-360],[9E9,9E9,9E9,9E9,9E9,9E9]],[[170,80,70,180,120,360],[9E9,9E9,9E9,9E9,9E9,9E9]];
WZLimSup \\Stat,wzAxes,shAxes;"""


def test_world_zone_statements_stay_todo_saying_dcs():
    result = run(BODY, DATA)
    found = [note for note in result.notes if note.kind == "TODO"]
    assert len(found) == 7 and {note.category for note in found} == {Blocker.SAFETY}
    first = todos(result)[0]
    assert first.startswith("WZBoxDef `shPress`: a world zone is set up on the FANUC in DCS")
    assert "CrossArm converts no safety function" in first and "validate it on the robot" in first
    assert triage.family(Blocker.SAFETY) == triage.SAFETY and Blocker.SAFETY in triage.NO_TP_CAUSES


def test_each_zone_is_a_checklist_item_with_what_the_rapid_gives():
    result = run(BODY, DATA)
    press, feeder, axes = result.world_zones
    assert (press.name, press.shape, press.inside, press.temporary) == ("wzPress", "box", True, False)
    assert press.values == "low corner [400,-300,0]; high corner [900,300,800]"
    assert press.action == "the robot stops before it enters the zone"
    assert feeder.values == "centre of its base [1200,0,0]; radius 250; height 1000"
    assert feeder.action.startswith("doInFeeder set to 1 while the TCP is in the zone")
    assert feeder.temporary and feeder.switched == ("disabled in main l.16",)
    assert (axes.shape, axes.inside) == ("joint range", False)
    assert axes.values == "low joint values [-170,-60,-70,-180,-120,-360]; high joint values [170,80,70,180,120,360]"
    _, _, html = checklist_section(result, ConversionConfig(), set(), identity="t")
    assert "Safety and world zones (DCS)" in html and "CrossArm converts no safety function" in html
    assert "Zone <code>wzPress</code>: inside of a box, the robot stops before it enters the zone" in html
    assert "low corner [400,-300,0]; high corner [900,300,800]" in html
    assert "a DCS zone is switched by a safe input" in html


def test_the_analysis_asks_to_set_up_and_validate_the_safety():
    result = run(BODY, DATA)
    action = next(a for a in priority_actions(result) if a.causes == (Blocker.SAFETY,))
    assert action.title == "Set up the robot's safety and zones in DCS, then validate them"
    assert action.todo == 7 and action.href == "#ck-safety" and action.who == (triage.INTEGRATOR,)
    assert "3 world zones the RAPID sets up (`wzPress`, `wzFeeder`, `wzAxes`)" in action.detail
    assert "CrossArm converts no safety function" in action.detail
    assert not any("DCS" in a.title for a in priority_actions(run("WaitTime 1;")))


def test_safety_options_of_the_system_description():
    options = ["608-1 World Zones", "616-1 PC Interface", "1125-1 SafeMove Basic", "623-1 Multitasking"]
    assert safety_options(options) == ["608-1 World Zones", "1125-1 SafeMove Basic"]


def test_a_backup_listing_safemove_gets_the_dcs_reminder_without_any_zone(tmp_path: Path):
    backup = tmp_path / "CELL_BACKUP"
    (backup / "BACKINFO").mkdir(parents=True)
    (backup / "BACKINFO" / "system.xml").write_text(
        '<S><Options><Option name="1125-1 SafeMove Basic"/><Option name="623-1 Multitasking"/></Options></S>',
        encoding="utf-8")  # fmt: skip
    program = backup / "RAPID" / "TASK1" / "PROGMOD"
    program.mkdir(parents=True)
    (program / "Cell.mod").write_text("MODULE Cell\nPROC main()\nWaitTime 1;\nENDPROC\nENDMODULE\n", encoding="utf-8")
    out = pipeline.run([backup], tmp_path / "out", log=lambda _line: None)
    result = out.tasks[0].result
    assert result.safety_options == ["1125-1 SafeMove Basic"] and not result.world_zones
    action = next(a for a in priority_actions(result) if "DCS" in a.title)
    assert "the ABB system lists `1125-1 SafeMove Basic`" in action.detail and not action.todo
    _, _, html = checklist_section(result, ConversionConfig(), set(), identity="t")
    assert "ABB option <code>1125-1 SafeMove Basic</code>: set up the safety again on the FANUC" in html
