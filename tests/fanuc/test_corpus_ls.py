# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Parser and writer vs a local corpus of FANUC exports (not in the repository).

Scans $CROSSARM_FANUC_CORPUS (default ./fanuc, git-ignored) for .LS files. Every
one that is a TP program must come back byte for byte through parse_ls then
write_ls: header, /APPL, every instruction with its own padding, /POS. Files that
are not TP programs (a backup also holds listings such as alarm histories) must be
refused with LSFormatError, never half-read. No value from the corpus is written in
this repository. Skipped when the corpus is absent, e.g. on CI.
"""

import os
from pathlib import Path

import pytest

from crossarm.fanuc.ls_parser import LSFormatError, parse_ls
from crossarm.fanuc.ls_writer import write_ls

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CORPUS = Path(os.environ.get("CROSSARM_FANUC_CORPUS", _REPO_ROOT / "fanuc"))

FILES = sorted(p for p in _CORPUS.rglob("*") if p.suffix.lower() == ".ls") if _CORPUS.is_dir() else []


@pytest.mark.skipif(not FILES, reason="no FANUC corpus (set CROSSARM_FANUC_CORPUS)")
@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_real_export_round_trips_or_is_refused(path):
    text = path.read_bytes().decode("ascii", errors="strict")
    if not text.startswith("/PROG"):
        with pytest.raises(LSFormatError):
            parse_ls(text)
        return
    assert write_ls(parse_ls(text)) == text
