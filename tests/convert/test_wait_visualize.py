# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""A wait that shows a message on the FlexPendant (\\Visualize and its companions) is the same wait on FANUC:
the message is dropped with a warning, nothing else changes."""

from test_translate import run, todos, tp_lines

from crossarm.convert.translate import Blocker


def warnings(result) -> list[str]:
    return [n.message for n in result.notes if n.kind == "WARNING" and n.category == Blocker.OPTIONS_IGNORED]


def test_the_wait_is_converted_and_the_message_dropped():
    plain = run("WaitDI diPartIn,1;")
    shown = run('WaitDI diPartIn,1\\Visualize\\Header:="Feeder"\\Message:="Waiting for a part"\\Icon:=iconInfo;')
    assert tp_lines(shown) == tp_lines(plain) and not todos(shown)
    (warning,) = warnings(shown)
    assert "\\Visualize \\Header \\Message \\Icon" in warning and "FlexPendant" in warning


def test_with_a_time_limit_and_on_every_wait():
    body = ("WaitDO doClamp,0\\MaxTime:=3\\TimeFlag:=bLate\\Visualize\\MsgArray:=sLines\\VisualizeTime:=2;\n"
            "WaitUntil nCount>2\\Visualize\\Image:=\"part.png\";")  # fmt: skip
    data = 'VAR bool bLate;\nVAR num nCount;\nVAR string sLines{2}:=["a","b"];'
    plain = run("WaitDO doClamp,0\\MaxTime:=3\\TimeFlag:=bLate;\nWaitUntil nCount>2;", data)
    shown = run(body, data)
    assert tp_lines(shown) == tp_lines(plain) and not todos(shown)
    assert len(warnings(shown)) == 2


def test_an_output_set_while_the_message_shows_is_not_dropped():
    result = run("WaitDI diPartIn,1\\Visualize\\UIActiveSignal:=doShown;")
    assert any("UIActiveSignal" in t for t in todos(result))
