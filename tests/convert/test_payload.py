# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""A tool and the part it grips as one FANUC payload: common centre of gravity, inertia about it."""

import math

import pytest

from crossarm.convert.payload import combined
from crossarm.convert.values import Frame, Load
from crossarm.geometry import Pose

UP = (1.0, 0.0, 0.0, 0.0)
# A tool pointing along the flange's x: its z axis is the flange's x (90 degrees about y).
SIDEWAYS = (math.cos(math.pi / 4), 0.0, math.sin(math.pi / 4), 0.0)


def test_the_tool_alone_is_its_own_load():
    tool = Frame(Pose((0, 0, 200), UP), True, "t", Load(3.0, (0, 0, 80), UP, (0.01, 0.02, 0.03)))
    payload = combined(tool, None)
    assert (payload.mass, payload.cog, payload.inertia, payload.products) == (3.0, (0, 0, 80), (0.01, 0.02, 0.03), 0.0)


def test_a_part_on_a_sideways_tool_moves_the_centre_along_the_flange_x():
    tool = Frame(Pose((150, 0, 100), SIDEWAYS), True, "t", Load(2.0, (0, 0, 50), UP, (0.0, 0.0, 0.0)))
    payload = combined(tool, Load(2.0, (0, 0, 50), UP, (0.0, 0.0, 0.0)))  # 50 mm past the TCP, along the tool z
    assert payload.mass == 4.0
    assert payload.cog == pytest.approx((100, 0, 75))  # (0,0,50) and (200,0,100), halfway
    # Two 2 kg points 0.2236 m apart: offsets (+-0.1, 0, +-0.025) m about the centre
    assert payload.inertia == pytest.approx((2 * 2 * 0.025**2, 2 * 2 * (0.1**2 + 0.025**2), 2 * 2 * 0.1**2))
    assert payload.products == pytest.approx(2 * 2 * 0.1 * 0.025)  # the xz product a FANUC schedule leaves out


def test_the_part_s_inertia_axes_turn_with_the_tool():
    tool = Frame(Pose((0, 0, 0), SIDEWAYS), True, "t", None)
    payload = combined(tool, Load(1.0, (0, 0, 0), UP, (0.1, 0.2, 0.3)))
    assert payload.inertia == pytest.approx((0.3, 0.2, 0.1))  # the tool's z is the flange's x
