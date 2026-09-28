# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""What TP can do with frames, as ROBOGUIDE measured it (tools/make_tp_frame_probe.py).

Why CrossArm computes frames at conversion time instead of writing TP that computes them: TP has no
pose product, no inverse and no angle function, and its PR arithmetic adds component by component.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_tp_frame_probe import RESULT, findings, results

pytestmark = pytest.mark.skipif(not RESULT.exists(), reason="TP frame probe not run on ROBOGUIDE yet")


def test_tp_has_no_pose_product_and_no_angle_function():
    syntax, outcome, _ = results()
    assert syntax["pr_product"] == "loaded"  # loaded...
    assert outcome.endswith("step 6 INTP-202")  # ...but stops the program where it runs
    for case in ("pr_colon", "pr_frame_sum", "pr_times_number", "sin_brackets", "sin_parentheses", "atan2", "sqrt",
                 "sin_in_expression"):  # fmt: skip
        assert syntax[case].startswith("refused ASBN-092"), case
    for case in ("several_operators", "nested_parentheses", "component_copy", "offset_condition_frame",
                 "move_offset", "move_tool_offset", "uframe_from_pr", "pr_from_uframe", "payload"):  # fmt: skip
        assert syntax[case] == "loaded", case


def test_what_the_frame_instructions_compute():
    measured = findings()
    for claim, (mm, deg) in measured.items():
        if claim == "PR+PR is not a composition":
            assert mm > 10, claim
        else:
            assert mm < 0.01 and deg < 0.01, claim
