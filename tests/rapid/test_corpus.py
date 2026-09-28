# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Robustness test over a local corpus of RobotWare backups.

The corpus is not in the repository. Point CROSSARM_RAPID_CORPUS at a folder of
RAPID files (searched recursively); by default ./abb is used when present
(it is git-ignored). Without a corpus, these tests are skipped — as on CI.

Only robustness is asserted (no crash, no syntax error): no expected output of
the corpus is written into the repository.
"""

import os
from pathlib import Path

import pytest

from crossarm.cli import iter_rapid_files
from crossarm.rapid import parse_file

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CORPUS = Path(os.environ.get("CROSSARM_RAPID_CORPUS", _REPO_ROOT / "abb"))
FILES = list(iter_rapid_files([_CORPUS])) if _CORPUS.is_dir() else []


@pytest.mark.skipif(not FILES, reason="no RAPID corpus (set CROSSARM_RAPID_CORPUS)")
@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_real_file_parses_without_errors(path):
    result = parse_file(path)
    assert result.module is not None
    assert result.ok, "\n".join(str(d) for d in result.diagnostics)
