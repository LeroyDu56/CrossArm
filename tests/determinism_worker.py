# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Run by tests/test_determinism.py in a process of its own (PYTHONHASHSEED set by the test): converts each input
given, without and with --karel, as is and with every move routine accepted, and prints the sha256 of every file written, as JSON. Not a test module.

The conversion log is left out (it holds the clock); the output folder's path is replaced in what is hashed.
"""

import hashlib
import json
import sys
import tempfile
from dataclasses import replace
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crossarm import pipeline
from crossarm.convert import ConversionConfig


def _hash(hashes: dict[str, str], out: Path, prefix: str) -> None:
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name != "crossarm_log.txt":
            data = path.read_bytes().replace(str(out).encode(), b"<out>")
            hashes[f"{prefix}|{path.relative_to(out).as_posix()}"] = hashlib.sha256(data).hexdigest()


def main(inputs: list[str]) -> None:
    hashes = {}
    for number, source in enumerate(inputs):
        for karel in (False, True):
            config = ConversionConfig(timestamp=datetime(2026, 1, 1), karel=karel)
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "out"
                first = pipeline.run([Path(source)], output=out, config=config, log=lambda _: None)
                _hash(hashes, out, f"{number}|{karel}")
            # then with every move routine accepted, the choice the window offers after a conversion
            names = {u.name.upper(): True for t in first.tasks if t.result for u in t.result.move_routines}
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "out"
                pipeline.run([Path(source)], output=out, config=replace(config, move_routines=names), log=lambda _: None)
                _hash(hashes, out, f"{number}|{karel}|moves")
    print(json.dumps(hashes, sort_keys=True))


if __name__ == "__main__":
    main(sys.argv[1:])
