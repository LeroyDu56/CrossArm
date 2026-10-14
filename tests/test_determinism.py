# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""The same input gives the same bytes, whatever the process: converted under different PYTHONHASHSEED (the order
of a set of names changes with it, and the addresses objects are given with that), every file written is the same.

The programs, the mapping (given back, it must give the same numbers), the reports and the summary compared
between two conversions all depend on it. The fixtures are always converted; a local test corpus too, when there
is one (./abb, or $CROSSARM_RAPID_CORPUS), every backup of it.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from diag_backup import make_backup
from helpers import FIXTURES

ROOT = Path(__file__).resolve().parents[1]
WORKER = Path(__file__).with_name("determinism_worker.py")
SEEDS = ("0", "7", "12345")


def _inputs(tmp_path: Path) -> list[str]:
    found = [str(p) for p in sorted((FIXTURES / "rapid").glob("*.mod"))] + [str(make_backup(tmp_path))]
    corpus = Path(os.environ.get("CROSSARM_RAPID_CORPUS", ROOT / "abb"))
    if corpus.is_dir():  # a local test corpus, not in the repository
        found += [str(p) for p in sorted(corpus.iterdir()) if p.is_dir() and not p.name.startswith(("_", "."))]
    return found


def test_same_bytes_whatever_the_hash_seed(tmp_path):
    inputs = _inputs(tmp_path)
    runs = []
    for seed in SEEDS:  # in parallel: one process per seed
        env = {**os.environ, "PYTHONHASHSEED": seed}
        runs.append(subprocess.Popen([sys.executable, str(WORKER), *inputs], env=env, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True, encoding="utf-8"))  # fmt: skip
    results = []
    for seed, run in zip(SEEDS, runs, strict=True):
        out, err = run.communicate(timeout=600)
        assert run.returncode == 0, f"PYTHONHASHSEED={seed}: {err[-2000:]}"
        results.append(json.loads(out))
    first = results[0]
    assert first, "nothing converted"
    for seed, other in zip(SEEDS[1:], results[1:], strict=True):
        differ = sorted(k for k in set(first) | set(other) if first.get(k) != other.get(k))
        assert not differ, f"PYTHONHASHSEED={SEEDS[0]} and {seed} differ: {differ[:10]}"
