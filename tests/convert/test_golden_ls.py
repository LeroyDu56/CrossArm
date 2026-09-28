# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""End-to-end golden test: tests/fixtures/rapid/<name>.mod -> tests/fixtures/fanuc/<name>/*.LS + report.

The expected output is committed so that the result of a conversion can be
read directly on GitHub. Regenerate after an intentional change with:

    CROSSARM_UPDATE_GOLDEN=1 pytest tests/convert/test_golden_ls.py
"""

import os
from datetime import datetime

import pytest
from helpers import FIXTURES

from crossarm.convert import ConversionConfig, build_report, convert
from crossarm.fanuc.ls_writer import write_ls
from crossarm.rapid import parse_file

CASES = ["pick_and_place", "logic_and_io", "hmi_and_groups"]
UPDATE = os.environ.get("CROSSARM_UPDATE_GOLDEN") == "1"


def generate(name: str) -> dict[str, str]:
    source = FIXTURES / "rapid" / f"{name}.mod"
    parsed = parse_file(source)
    config = ConversionConfig(timestamp=datetime(2026, 1, 1, 8, 0, 0))
    result = convert([parsed.module], config, sources={parsed.module.name: parsed.text})
    files = {f"{info.program.name}.LS": write_ls(info.program) for info in result.programs}
    files["crossarm_report.md"] = build_report(result, config, [source.name])
    return files


@pytest.mark.parametrize("name", CASES)
def test_conversion_output_is_stable(name):
    expected_dir = FIXTURES / "fanuc" / name
    actual = generate(name)
    if UPDATE:
        expected_dir.mkdir(parents=True, exist_ok=True)
        for old in expected_dir.iterdir():
            old.unlink()
        for filename, text in actual.items():
            (expected_dir / filename).write_bytes(text.encode("ascii" if filename.endswith(".LS") else "utf-8"))
    expected = {p.name: p.read_bytes().decode("utf-8") for p in sorted(expected_dir.iterdir())}
    assert sorted(actual) == sorted(expected)
    for filename, text in actual.items():
        assert text == expected[filename], filename
