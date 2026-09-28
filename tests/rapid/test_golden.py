# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Golden tests: every tests/fixtures/rapid/<name>.mod has a <name>.expected.json.

Adding a fixture file is enough to add a test. To (re)generate the expected
files after an intentional change, run:

    CROSSARM_UPDATE_GOLDEN=1 pytest tests/rapid/test_golden.py

and review the diff before committing.
"""

import json
import os

import pytest
from helpers import FIXTURES

from crossarm.rapid import parse_file
from crossarm.rapid.to_json import dumps, to_data
from crossarm.rapid.to_pseudo import to_pseudo

SOURCES = sorted((FIXTURES / "rapid").glob("*.mod"))
UPDATE = os.environ.get("CROSSARM_UPDATE_GOLDEN") == "1"


@pytest.mark.parametrize("source", SOURCES, ids=lambda p: p.name)
def test_golden(source):
    result = parse_file(source)
    actual = {
        "encoding": result.encoding,
        "diagnostics": to_data(result.diagnostics),
        "module": to_data(result.module),
    }
    expected_path = source.with_suffix(".expected.json")
    if UPDATE:
        expected_path.write_text(dumps(actual) + "\n", encoding="utf-8", newline="\n")
    assert expected_path.exists(), f"missing {expected_path.name}: run with CROSSARM_UPDATE_GOLDEN=1"
    assert actual == json.loads(expected_path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("source", SOURCES, ids=lambda p: p.name)
def test_pseudo_listing_renders(source):
    module = parse_file(source).module
    lines = to_pseudo(module).splitlines()
    assert f"MODULE {module.name}" in lines[0]
    assert lines[-1].endswith("ENDMODULE")
